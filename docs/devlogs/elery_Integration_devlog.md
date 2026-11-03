# [Devlog] Phase 9-2: Celery + Redis 기반 분산 작업 큐 및 추론 워커 격리

본 문서는 Phase 9-1에서 구축한 PostgreSQL 비동기 영속성 계층 위에, API Gateway(FastAPI)와 GPU 추론 워커(Celery Worker)를 물리적으로 분리하여 시스템 생존성(Survivability)을 확보하는 과정을 기록한다.

## 1. 도입 배경 및 시스템 한계점

Phase 9-1을 통해 작업 상태의 RDBMS 영속화는 달성했으나, 연산 실행 구조에는 여전히 단일 프로세스 모놀리식 아키텍처의 한계가 남아 있었다.

*   **API 서버와 추론 연산의 운명 공동체화 (SPOF):** `app/main.py` 내부에서 FastAPI의 `BackgroundTasks`와 `asyncio.Semaphore(1)`를 사용해 Demucs 및 CREPE 추론을 구동하고 있다. 만약 대용량 오디오 처리 중 GPU VRAM OOM이나 C++ 백엔드 세그멘테이션 폴트(SIGSEGV)로 프로세스가 죽으면, 단순 추론 실패에 그치지 않고 **웹 서버(Uvicorn) 전체가 다운**되어 다른 모든 사용자의 접속과 상태 조회까지 마비된다.
*   **인메모리 세마포어의 한계:** `asyncio.Semaphore(1)`는 단일 프로세스 메모리 내에서만 유효하므로, 향후 API 서버 워커 수를 늘리거나 추론 노드를 스케일아웃(Scale-out)할 경우 동시성 제어가 무력화된다.

이를 해결하기 위해 인메모리 메시지 브로커인 **Redis**와 분산 작업 큐 프레임워크인 **Celery**를 도입하여, 웹 요청 처리와 무거운 딥러닝 연산을 별도의 OS 프로세스(및 컨테이너)로 완전히 격리한다.

## 2. 아키텍처 설계 원칙

기존에 확립한 하이브리드 스토리지 및 단명 세션 원칙(ADR-017)을 훼손하지 않도록 다음과 같은 설계 원칙을 수립한다.

*   **PostgreSQL 단일 진실 공급원 (SSOT) 유지:** Celery의 기본 기능인 `result_backend`를 활성화하면 대용량 채보 결과(DTO)가 Redis 인메모리와 PostgreSQL 양쪽에 중복 저장되어 메모리를 낭비한다. 따라서 Redis는 순수 **메시지 브로커(Message Broker)**로만 사용하고(`task_ignore_result=True`), 모든 작업 상태(`PENDING`, `PROCESSING`, `SUCCESS`, `FAILED`)와 결과 메타데이터의 영속화는 기존과 동일하게 PostgreSQL이 전담한다.
*   **CUDA 안전성을 위한 단일 순차 실행 풀 (`--pool=solo`):** Celery의 기본 실행 모델인 `prefork`는 OS의 `fork()` 시스템 콜을 사용한다. 그러나 PyTorch와 CUDA 런타임은 포크된 자식 프로세스에서의 컨텍스트 재초기화를 지원하지 않아 데드락이나 `RuntimeError`를 유발한다. 이를 방어하고 기존 `Semaphore(1)`과 동일한 단일 GPU 직렬화 효과를 얻기 위해, 워커를 프로세스 포크가 없는 `--pool=solo` 및 `worker_prefetch_multiplier=1` 옵션으로 구동한다.
*   **컨테이너 간 파일 시스템 볼륨 정합성:** API 서버가 업로드받은 임시 오디오 파일(`app/temp_uploads`)과 워커가 생성하는 결과물(`outputs`)은 물리적으로 분리된 컨테이너 간에 공유되어야 한다. 이를 위해 `docker-compose.yml`에서 두 디렉토리를 공유 볼륨으로 마운트한다.

## 3. 작업 수명주기 및 데이터 흐름 (Decoupled FSM)

프로세스 분리 후 작업 데이터는 다음 흐름에 따라 처리된다.

1.  **작업 수락 및 큐 발행 (FastAPI -> PostgreSQL & Redis):**
    *   클라이언트가 `/api/v1/transcribe`로 오디오를 업로드하면, FastAPI는 임시 폴더에 파일을 기록하고 PostgreSQL에 `status=PENDING` 레코드를 생성한다.
    *   FastAPI는 직접 연산을 수행하는 대신, Celery 브로커(Redis)로 `(task_id, temp_file_path)` 메시지만 발행(`.delay()`)하고 즉시 `202 Accepted`를 반환한다.
2.  **작업 소비 및 추론 수행 (Redis -> Celery Worker):**
    *   독립 프로세스로 대기 중인 Celery Worker가 Redis에서 작업을 하나 가져온다.
    *   워커는 단명 세션(Short-lived Session)을 열어 DB 상태를 `PROCESSING`으로 갱신한 뒤 닫는다.
    *   워커 내부에서 Demucs 분리 및 CREPE 채보 파이프라인을 수행한다.
3.  **결과 영속화 및 리소스 정리 (Celery Worker -> PostgreSQL):**
    *   추론이 완료되면 워커가 다시 DB 세션을 열어 `status=SUCCESS` 및 `result_metadata`를 기록(또는 예외 발생 시 `status=FAILED` 및 `error_log` 기록)하고 커밋한다.
    *   임시 업로드 파일을 삭제하고 샌드박스 TTL 정리 스케줄을 등록한다.

## 4. 실행 체크리스트 (Implementation Roadmap)

단계적 전진 원칙에 따라 다음 순서로 구현 및 검증을 진행한다.

- [x] **Step 1: 브로커/워커 인프라 뼈대 및 엔트리포인트 구성**
  - `requirements.txt`에 `celery>=5.3.0`, `redis>=5.0.0` 패키지 추가.
  - `docker-compose.yml`에 `redis` 서비스 및 `--pool=solo` 기반 `worker` 서비스 추가, 공유 볼륨(`temp_uploads`, `outputs`, `crepe_cache`) 매핑.
  - `app/worker.py` 신설: 환경 변수 기반 브로커 바인딩(로컬 `localhost` / 도커 `redis` 이원화), `task_ignore_result=True`, `task_acks_late=True` 설정 및 `worker.ping` 헬스체크 태스크 구현.
- [ ] **Step 2: 파이프라인 태스크 이관 및 동기-비동기 브릿지 구현**
  - `app/main.py`의 `run_pipeline_task` 로직을 `app/worker.py`의 Celery 태스크로 이관.
  - 동기식 Celery 워커 컨텍스트 내부에서 비동기 파이프라인(`separate_and_generate_stems`)과 비동기 ORM(`AsyncSessionLocal`)을 안전하게 구동하기 위한 이벤트 루프 브릿지 구성.
- [ ] **Step 3: FastAPI 라우터 디커플링 및 자가 치유(Self-healing) 보강**
  - `app/main.py`에서 `BackgroundTasks`, `gpu_semaphore`, 코어 파이프라인 직접 임포트를 제거하고 Celery 태스크 발행(`.delay()`)으로 교체.
  - 워커 강제 종료로 인해 `PROCESSING` 상태에서 멈춘 고아 레코드를 서버 기동 시 `FAILED`로 복구하는 Lifespan 자가 치유 로직 추가.
