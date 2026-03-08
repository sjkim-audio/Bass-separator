# 🖥️ Backend & Infrastructure Pipeline (DevLog)

> **Status:**
> Phase 1 Completed (Local CLI & Subprocess Execution)
> Phase 2 Completed (FastAPI & Docker Containerization)
> Phase 3 Completed (End-to-End API Integration & Pydantic Schema)
> Phase 4 Completed (Single-node Concurrency Control & Polling)
> Phase 5 Planned (Distributed Task Queue for Scale-out)

## 1. Overview
이 프로젝트는 완성된 오디오 전사(Transcription) 파이프라인을 다수의 클라이언트(웹/앱)가 호출할 수 있도록 **FastAPI 기반의 RESTful API 서버로 전환**하고, 안정적인 서비스 구동을 위한 **Docker 인프라 환경**을 구축하는 과정을 기록합니다.

초기(Phase 1)에는 파이썬 `subprocess`를 통해 터미널 명령어로 모델을 구동했으나, 이는 매 요청마다 파이썬 인터프리터를 새로 적재하는 막대한 오버헤드와 Windows OS 특유의 DLL 충돌(WinError 1114)을 유발하는 한계가 있었습니다. 이를 해결하기 위해(Phase 2) **FastAPI** 프레임워크를 도입하고, 시스템 의존성을 완벽히 격리하는 **Docker(Linux) 컨테이너** 아키텍처로 전면 이관했습니다. 

현재(Phase 3, 4)는 CLI용으로 설계된 파이프라인을 객체 지향적으로 완벽히 분리(`src/core/pipeline.py`)하고, HTTP 통신에 적합한 JSON/DTO 구조로 리팩토링함과 동시에 **다중 사용자 접속 시 발생하는 서버 다운(OOM) 현상을 비동기 폴링과 세마포어로 완벽히 방어**하는 데 성공했습니다.

---

## 2. Server Architecture Evolution

서버 아키텍처는 성능 병목과 확장성 한계를 극복하기 위해 다음과 같이 진화했습니다.

### Step 1: Subprocess to Direct Import (Phase 1 -> 2)
- **Problem:** 기존 CLI 모델은 외부 셸 명령을 호출하여(Demucs) 결과를 디스크에 쓰고 다시 읽어오는 방식이었습니다.
- **Optimization:** FastAPI 메모리 내에서 `demucs.separate.main`을 직접 호출(Direct Import)하는 단일 프로세스 구조로 변경하여, I/O 오버헤드를 줄이고 프로세스 컨텍스트 스위칭 비용을 제거했습니다.

### Step 2: Threadpool Offloading (Event Loop Unblocking)
- **Problem:** 무거운 PyTorch 추론 함수를 비동기 라우터(`async def`) 내에서 실행하여, 연산이 진행되는 수십 초 동안 Uvicorn의 단일 이벤트 루프가 완전히 마비(Blocked)되는 치명적 결함이 존재했습니다.
- **Optimization:** 스타렛(Starlette) 엔진이 CPU-Bound 연산(Demucs, CREPE)을 **외부 스레드풀(Background Threadpool)**로 자동 오프로딩하도록 아키텍처를 교정하여, 모델 추론 중에도 헬스 체크나 다른 클라이언트의 요청을 정상 처리하도록 구성했습니다.

### Step 3: API Response Normalization & Validation (Phase 3)
- **Problem:** 기존 렌더러는 악보를 콘솔에 직접 출력(`print()`)하여 HTTP Body로 응답할 수 없었으며, `float64` 기반의 오디오 분석 데이터(시간, 신뢰도 등)가 무한 소수점으로 직렬화되어 네트워크 페이로드가 팽창하는 문제가 있었습니다.
- **Optimization:** Pydantic `TranscriptionResponse` DTO를 도입하고, `@field_validator`를 사용해 모든 부동소수점 데이터를 **밀리초 해상도(소수점 3자리)로 강제 반올림**하여 직렬화 비용과 응답 크기를 최소화했습니다.

### Step 4: Asynchronous Polling & Concurrency Control (Phase 4)
- **Problem:** 단일 노드(FastAPI)에서 무거운 딥러닝 연산을 처리할 때, 복수의 클라이언트가 동시에 파일을 업로드하면 GPU VRAM과 시스템 메모리가 즉시 고갈(OOM)되며 서버가 다운되는 현상이 발생했습니다.
- **Optimization:** 1. 라우터에 `asyncio.Semaphore(1)`를 적용하여 GPU 추론 파이프라인 실행을 강제로 직렬화(Sequential)했습니다.
  2. 요청 수락 시 즉시 **HTTP 202(Accepted)와 `task_id`를 반환**하고, 연산은 백그라운드로 넘기는 **비동기 폴링(Polling) 아키텍처**로 개편하여 장시간 연결(Timeout) 및 서버 마비를 원천 차단했습니다.

---

## 3. Challenges & Solutions (Troubleshooting)

서버 및 인프라 구축 과정에서 발생한 주요 문제점과 해결 방안입니다.

| Issue | Cause | Solution |
| :--- | :--- | :--- |
| **Phase 1~2 (Infra & FastAPI Base)** | | |
| **`[WinError 1114]` DLL 초기화 실패** | Windows 환경에서 PyTorch와 C++ 기반 오디오 라이브러리(`ffmpeg`, `libsndfile` 등)의 환경 변수 및 DLL 충돌. | 로컬 OS 의존성을 탈피하고, `python:3.10-slim` 기반의 독립된 **Docker Linux 컨테이너**로 서버 구동 환경을 전면 격리. |
| **Storage Leak (임시 파일 누적)** | API 응답 완료 후에도 업로드된 원본 WAV와 Demucs가 처리한 임시 오디오 파일이 디스크에 지속적으로 누적됨. | FastAPI의 **`BackgroundTasks`**와 `finally` 블록을 활용하여, 파이프라인 종료 시 원본/임시 파일을 안전하게 `os.remove` 하도록 삭제 파이프라인 구축. |
| **Phase 3~4 (Architecture & E2E Integration)** | | |
| **NameError 및 네임스페이스 오염** | 레거시 코드(`src.main`)와 신규 아키텍처가 `app/main.py`에 혼재되어 동일 함수명 충돌 및 파이프라인 단절 에러 발생. | API 컨텍스트와 코어 로직의 의존성을 완벽히 격리. `src/core/pipeline.py`를 단일 진실 공급원(SSOT)으로 신설하여 객체 지향적으로 메서드 체이닝을 복원함. |
| **프론트엔드 UI 확장성 한계** | API가 텍스트(`\n`이 포함된 문자열) 악보만 반환할 경우, 클라이언트 단에서 인터랙티브 UI(하이라이팅, 수정 등) 구성이 불가능함. | **Pydantic DTO**를 도입하여 시각적 악보 텍스트(`ascii_tab`)와 개별 `BassNoteEvent` 객체 배열(시간, 프렛, 격자 인덱스, **Confidence**)을 함께 JSON으로 직렬화하여 반환. |
| **단일 노드 다중 요청 OOM 다운** | 제한된 VRAM 환경에서 2개 이상의 Demucs/CREPE 프로세스가 동시 실행되어 할당량을 초과함. | **Semaphore**를 통한 락(Lock) 획득 구조와 `outputs/{task_id}.json` 형태의 **상태 영속화(Persistence)** 저장소를 구축하여 안전한 큐잉(Queueing) 달성. |
| **API Response Data Drop (DTO 누락)** | 백엔드 파이프라인에서 타브 악보와 BPM을 정상 연산했으나, 최종 응답 모델(`TranscriptionResponse`)에 필드가 정의되지 않아 클라이언트 전달 과정에서 증발함. | DTO 최상단 루트에 `bpm` 및 `ascii_tab` 필드를 명시적으로 추가하여, 프론트엔드가 JSON 파싱 후 즉시 화면에 렌더링할 수 있도록 **데이터 컨트랙트(Data Contract) 복원 및 확장**. |
---

## 4. Future Works (Roadmap)

다음 단계의 백엔드 목표입니다.

- [x] **Pydantic Schema & DTO:** E2E 파이프라인 결과를 캡슐화한 `TranscriptionResponse` 모델 구현 및 float 최적화 적용.
- [x] **Renderer Return Refactoring:** `TabRenderer`가 콘솔 출력이 아닌 렌더링된 문자열을 병합 충돌 없이 반환하도록 수정.
- [x] **E2E Pipeline Integration:** `src/core/pipeline.py` 분리 및 `app/main.py` 라우터와 완벽한 연결.
- [x] **Single-node Concurrency (Phase 4):** `Semaphore` 및 `BackgroundTasks`를 활용한 단일 노드 기반 비동기 폴링 큐 구축.
- [ ] **Distributed Task Queue (Phase 5):** 단일 노드의 한계(스레드 블로킹)를 넘어, 다수의 Worker 노드로 스케일 아웃(Scale-out)이 가능하도록 **Celery + Redis** 기반의 분산 비동기 큐잉 시스템 전환.
- [ ] **Cloud Storage Integration:** 임시 파일 저장소를 로컬 디스크에서 AWS S3 또는 GCP Bucket 기반 스트리밍 처리로 고도화하여 무상태(Stateless) 서버 달성.
