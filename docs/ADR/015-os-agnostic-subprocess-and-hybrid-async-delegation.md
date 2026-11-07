# [ADR-015] OS 독립적 서브프로세스 격리와 하이브리드 비동기 위임 아키텍처

* **Status:** Accepted
* **Date:** 2026-09-01 (Retroactively Documented for Phase 4.5)
* **Category:** Backend-Infra / Concurrency
* **Related Documents:** [Backend_devlog.md](../devlogs/Backend_devlog.md)

## 1. Context (배경)

FastAPI 프레임워크 기반으로 서버를 구동할 때, 딥러닝 추론 파이프라인(Demucs 등)의 실행 방식을 두고 심각한 인프라 종속적 오류와 메모리 관리 문제가 연이어 발생했다.

1.  **VRAM 누수 (Direct Import의 한계):** 초기에는 성능을 위해 `demucs.separate`를 메모리 내로 직접 임포트(Direct Import)하여 실행했다. 그러나 파이썬의 가비지 컬렉터(GC)가 GPU에 할당된 텐서 자원을 제때 회수하지 못해, 서버가 장기 가동될수록 VRAM 누수(Memory Leak)가 누적되어 OOM이 발생하는 치명적 결함이 나타났다.
2.  **OS 이벤트 루프 충돌 (Async Subprocess의 한계):** VRAM의 완벽한 회수(OS 레벨 프로세스 종료)를 위해 비동기 서브프로세스(`asyncio.create_subprocess_exec`) 방식을 도입했다. 하지만 로컬 개발 환경인 Windows OS에서 Uvicorn이 사용하는 기본 이벤트 루프(`SelectorEventLoop`)가 비동기 서브프로세스 생성을 지원하지 않아 `NotImplementedError`를 뱉으며 파이프라인이 붕괴되는 현상이 발생했다.

## 2. Decision (결정)

운영체제(OS) 환경에 구애받지 않으면서도 메모리 누수와 메인 루프 블로킹을 모두 방지하기 위해, **동기식 프로세스 호출을 비동기 스레드 풀에 위임하는 하이브리드 아키텍처(Hybrid Async Delegation)**를 채택한다.

1.  **OS 레벨 격리 (Subprocess Isolation):** Demucs 추론은 반드시 별도의 터미널 셸 프로세스로 격리하여 실행한다. 프로세스가 종료되면 OS 차원에서 VRAM이 100% 강제 반환되도록 구조화한다.
2.  **플랫폼 비종속적 동기 호출:** OS 호환성 충돌을 일으키는 `asyncio.create_subprocess_exec`를 폐기하고, 플랫폼 비종속적이고 안정적인 파이썬 표준 라이브러리의 동기(Sync) 함수인 `subprocess.run`을 사용한다.
3.  **비동기 스레드풀 위임 (Event Loop Unblocking):** 무거운 동기 함수인 `subprocess.run`이 FastAPI의 단일 이벤트 루프를 블로킹하지 못하도록, `loop.run_in_executor(None, func)`를 사용하여 백그라운드 스레드 풀(Threadpool)로 연산을 오프로딩(Offloading)한다.

## 3. Rationale (의사결정 근거)

### 3.1. OS 호환성과 런타임 안정성의 동시 달성
Windows, Linux, macOS 등 어떤 환경에서든 FastAPI를 띄울 수 있어야 프로덕션 배포 전 로컬 테스트가 원활해진다. `subprocess.run`은 모든 OS에서 가장 안정적으로 동작하는 서브프로세스 생성 수단이다. 이를 스레드풀에 넘기는 방식은 코드가 약간 복잡해지더라도(동기-비동기 브릿징), 호환성 에러를 원천 차단하는 가장 확실한 엔지니어링 접근이다.

### 3.2. 완벽한 메모리 가비지 컬렉션(GC) 보장
파이썬 내부의 `gc.collect()`나 `torch.cuda.empty_cache()`에 의존하는 것은 한계가 있다. 무거운 CNN/Transformer 모델은 실행 자체가 독립된 프로세스(PID)에서 이루어지고, 작업 완료 후 해당 PID가 OS에 의해 완전히 사멸(Kill)되게 만드는 것만이 100% 확실한 VRAM 누수 방어책이다.

## 4. Consequences (결과)

* **Positive:**
    * Windows 로컬 환경과 Linux Docker 환경 모두에서 에러 없이 동일하게 동작하는 인프라 독립성을 획득했다.
    * OOM 누수 문제가 완전히 해결되었으며, 추론이 진행되는 수십 초 동안에도 API 서버는 다른 클라이언트의 헬스 체크나 폴링 요청을 정상적으로 처리(Non-blocking)할 수 있게 되었다.
* **Negative & Limitations:**
    * 서브프로세스 생성(OS 커널 오버헤드) 및 스레드 컨텍스트 스위칭으로 인해, 직접 임포트(Direct Import) 방식에 비해 매 요청마다 미세한 지연 시간(약 1~2초)이 추가로 발생한다. (이는 서버 생존성을 위해 감수한 트레이드오프이다.)
