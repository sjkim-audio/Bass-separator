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
*   **프로세스 실행 모델에 맞춘 DB 커넥션 풀 이원화 (`QueuePool` vs `NullPool`):** 상시 구동되는 단일 이벤트 루프를 가진 FastAPI 서버는 커넥션 풀링(`pool_size=5`, `pool_pre_ping=True`)을 유지하여 조회 응답 속도를 극대화한다. 반면, 동기식 Celery 워커는 태스크마다 `asyncio.run()`을 통해 이벤트 루프를 새로 생성하고 닫으므로, 이전 루프에 바인딩된 커넥션 재사용 충돌을 원천 차단하기 위해 워커 프로세스에서는 `NullPool`을 동적으로 할당한다.
*   **컨테이너 간 파일 시스템 볼륨 정합성:** API 서버가 업로드받은 임시 오디오 파일(`app/temp_uploads`)과 워커가 생성하는 결과물(`outputs`)은 물리적으로 분리된 컨테이너 간에 공유되어야 한다. 이를 위해 `docker-compose.yml`에서 두 디렉토리를 공유 볼륨으로 마운트한다.

## 3. 작업 수명주기 및 데이터 흐름 (Decoupled FSM)

프로세스 분리 후 작업 데이터는 다음 흐름에 따라 처리된다.

1.  **작업 수락 및 큐 발행 (FastAPI -> PostgreSQL & Redis):**
    *   클라이언트가 `/api/v1/transcribe`로 오디오를 업로드하면, FastAPI는 임시 폴더에 파일을 기록하고 PostgreSQL에 `status=PENDING` 레코드를 생성한다.
    *   FastAPI는 직접 연산을 수행하는 대신, Celery 브로커(Redis)로 `(task_id, temp_file_path)` 메시지만 발행(`.delay()`)하고 즉시 `202 Accepted`를 반환한다.
2.  **작업 소비 및 추론 수행 (Redis -> Celery Worker):**
    *   독립 프로세스로 대기 중인 Celery Worker가 Redis에서 작업을 하나 가져온다.
    *   워커는 단명 세션(Short-lived Session)을 열어 DB 상태를 `PROCESSING`으로 갱신한 뒤 즉시 닫는다.
    *   워커 내부에서 Demucs 분리 및 CREPE 채보 파이프라인을 수행한다.
3.  **결과 영속화 및 리소스 정리 (Celery Worker -> PostgreSQL):**
    *   추론이 완료되면 워커가 다시 DB 세션을 열어 `status=SUCCESS` 및 `result_metadata`를 기록(또는 예외 발생 시 `status=FAILED` 및 `error_log` 기록)하고 커밋한다.
    *   임시 업로드 파일을 삭제하고, 지연 실행 태스크(`worker.cleanup_sandbox`)를 브로커에 발행하여 1시간 뒤 샌드박스 폴더가 삭제되도록 스케줄링한다.

## 4. 실행 체크리스트 (Implementation Roadmap)

단계적 전진 원칙에 따라 다음 순서로 구현 및 검증을 진행한다.

- [x] **Step 1: 브로커/워커 인프라 뼈대 및 엔트리포인트 구성**
  - `requirements.txt`에 `celery>=5.3.0`, `redis>=5.0.0` 패키지 추가.
  - `docker-compose.yml`에 `redis` 서비스 및 `--pool=solo` 기반 `worker` 서비스 추가, 공유 볼륨(`temp_uploads`, `outputs`, `crepe_cache`) 매핑.
  - `app/worker.py` 신설: 환경 변수 기반 브로커 바인딩(로컬 `localhost` / 도커 `redis` 이원화), `task_ignore_result=True`, `task_acks_late=True` 설정 및 `worker.ping` 헬스체크 태스크 구현.
- [x] **Step 1-2: 런타임 의존성 정규화 및 환경 변수 단일화 (Pre-flight Hardening)**
  - WSL2 기본 Python 3.14의 C-확장 패키지 빌드 실패 해결을 위해 `uv` 기반 Python 3.10 가상환경 재구축.
  - 폐기된 `museval` 의존성을 제거하고 `mir_eval>=0.7` 및 `numpy<2.0.0` 상한선 고정 반영.
  - `.env.example` 추가 및 `python-dotenv`(`load_dotenv(override=False)`) 도입으로 로컬(`.env`)과 컨테이너(`docker-compose.yml`) 간 DB/브로커 접속 정보 단일화.
- [x] **Step 2: 파이프라인 태스크 이관 및 동기-비동기 브릿지 구현**
  - `app/main.py`의 `run_pipeline_task` 로직을 `app/worker.py`의 Celery 태스크(`worker.run_pipeline_task`)로 이관.
  - `app/database/core.py`에 워커 프로세스 감지(`IS_CELERY_WORKER` 및 `sys.argv`) 기반 `NullPool` 분기 적용 및 코루틴 종료 시 `await engine.dispose()` 호출로 이벤트 루프 바인딩 충돌 방어.
  - `asyncio.run()` 종료 시 증발하는 코루틴 타이머를 대체하기 위해 `worker.cleanup_sandbox` 지연 태스크(`apply_async(countdown=3600)`) 도입.
- [ ] **Step 3: FastAPI 라우터 디커플링 및 자가 치유(Self-healing) 보강**
  - `app/main.py`에서 `BackgroundTasks`, `gpu_semaphore`, 코어 파이프라인 직접 임포트를 제거하고 Celery 태스크 발행(`.delay()`)으로 교체.
  - 워커 강제 종료로 인해 `PROCESSING` 상태에서 멈춘 고아 레코드를 서버 기동 시 `FAILED`로 복구하는 Lifespan 자가 치유 로직 추가.

## 5. 핵심 트러블슈팅 및 인프라 정합성 교정

*   **`asyncio.run()` 반복 실행 시 `asyncpg` 이벤트 루프 바인딩 충돌 방어:**
    *   **이슈:** 동기식 Celery 태스크가 매 작업마다 `asyncio.run()`을 호출하면 매번 새 이벤트 루프가 생성되고 닫힌다. 이때 SQLAlchemy `AsyncEngine`의 커넥션 풀(`QueuePool`)에 남아 있던 이전 커넥션은 이미 닫힌 과거 이벤트 루프에 묶여 있어, 두 번째 작업 진입 시 `RuntimeError: Task got Future attached to a different loop` 크래시를 유발한다.
    *   **해결:** `app/database/core.py`에서 실행 컨텍스트가 Celery 워커(`IS_CELERY_WORKER=true` 또는 `celery` CLI 엔트리포인트)인 경우 커넥션을 풀에 남기지 않는 `NullPool`을 사용하도록 동적 분기하고, 태스크 코루틴의 `finally` 블록에 `await engine.dispose()`를 명시하여 루프 폐쇄 직전 잔여 리소스를 완벽히 해제했다.
*   **코루틴 기반 TTL 타이머의 조기 취소(Premature Cancellation) 방어:**
    *   **이슈:** 기존 FastAPI 환경에서는 상시 구동되는 Uvicorn 이벤트 루프 위에 `asyncio.create_task(ttl_cleanup)`를 띄웠으나, 워커의 `asyncio.run()`은 메인 코루틴 종료와 동시에 미완료된 백그라운드 태스크를 모두 강제 취소(Cancel)하므로 1시간 대기 타이머가 작동하지 않고 증발한다.
    *   **해결:** 샌드박스 삭제 로직을 독립된 Celery 태스크(`worker.cleanup_sandbox`)로 분리하고, 추론 태스크의 `finally` 블록에서 `apply_async(args=[...], countdown=3600)`로 지연 발행하여 ADR-016의 Queue-Aware TTL 동작을 온전히 보존했다.
*   **환경 변수 관리 파편화 해소 (`.env` SSOT 구축):**
    *   **이슈:** `app/database/core.py`와 `alembic/env.py`가 `os.getenv`만 사용하여 터미널 세션마다 `export DATABASE_URL`을 수동 입력하지 않으면 로컬 DB 계정 불일치(`InvalidPasswordError`)가 발생했다.
    *   **해결:** `python-dotenv`를 도입하고 `load_dotenv(override=False)`를 적용하여, 로컬 WSL2 환경에서는 루트의 `.env` 파일을 자동 참조하고 Docker 배포 환경에서는 컨테이너 주입 환경 변수가 우선권을 갖도록 일원화했다.
*   **Python 3.14 호환성 단절 및 레거시 의존성(`museval`) 정리:**
    *   **이슈:** WSL2 Ubuntu의 최신 Python 3.14 환경에서는 `numba`/`llvmlite`(`librosa` 의존성) 및 C-확장 오디오 패키지의 사전 컴파일 Wheel이 존재하지 않아 `pip install` 시 소스 빌드 에러가 발생했다. 또한 코드에서 이미 `mir_eval`로 대체된 `museval`이 `requirements.txt`와 `evaluator.py` 임포트문에 남아 있었다.
    *   **해결:** `uv` 패키지 매니저를 사용해 프로젝트 표준인 **Python 3.10 격리 가상환경**을 재구축하고, 미사용 `museval` 제거 및 `numpy<2.0.0` 상한선 고정으로 MIR 라이브러리와의 호환성을 확립했다.

## 6. 아키텍처 한계점 및 트레이드오프 (Trade-offs & Limitations)

*   **`NullPool` 적용에 따른 TCP 연결 오버헤드:** 워커 프로세스에서 `NullPool`을 사용함에 따라 DB 상태를 갱신할 때마다 TCP 핸드셰이크가 새로 발생(회당 약 2~5ms 소요)한다. 그러나 단일 추론 작업당 DB 트랜잭션은 총 2회(`PROCESSING`, `SUCCESS/FAILED`)뿐이며 전체 AI 추론 시간이 수십 초에 달하므로, 10ms 미만의 오버헤드를 감수하고 이벤트 루프 충돌 크래시를 원천 차단하는 것이 엔지니어링 관점에서 타당하다.
*   **`countdown` 지연 태스크의 브로커 인메모리 점유:** `apply_async(countdown=3600)`로 발행된 샌드박스 클린업 메시지는 실행 시점까지 1시간 동안 워커 및 Redis 메모리에 대기 상태로 머무른다. 현재는 삭제할 경로 문자열(`str`) 하나만 페이로드로 가지므로 메모리 점유율이 무시할 수 있는 수준이나, 향후 대규모 트래픽 환경으로 확장될 경우 주기적 스케줄러(Celery Beat) 기반의 배치 스캔 방식으로 전환해야 한다.
