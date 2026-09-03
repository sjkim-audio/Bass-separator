# 🚀 Backend & MLOps Execution Plan (백엔드 인프라 및 MLOps 실행 계획서)

**작성 목적:** 단일 스크립트 형태의 AI 파이프라인을 비동기 상태 추적과 데이터 영속성(Persistence)이 보장되는 상용 서비스 레벨로 고도화하기 위한 아키텍처 변경 계획 및 마일스톤을 정의한다[cite: 1, 3]. 코어 AI 알고리즘의 튜닝이나 구조 개조(Research)를 지양하고 완성된 모델의 안정적인 서빙(Serving)에 집중하여[cite: 2], 백엔드 및 MLOps 엔지니어링 역량을 증명할 수 있는 프로덕션 레벨 아키텍처를 구축한다[cite: 2]. 무분별한 기술 도입을 경계하면서도 시스템 복잡도를 제어하고[cite: 3], 트래픽 병목 해소와 **API 서버의 생존성(Survivability)**을 보장하는 실용적인 엔지니어링 표준을 수립한다.

---

## 1. 아키텍처 현황 및 개편 목표

### 1.1. 현재 상태의 한계
*   **동시성 병목:** FastAPI 내부에서 `asyncio.Semaphore(1)`를 통해 추론을 제어하고 있어 트래픽 유입 시 서버 블로킹 및 무한 대기(Starvation) 위험이 존재한다[cite: 1, 2, 3].
*   **무상태(Stateless) 결함:** 분석 완료된 데이터가 도커 내부의 로컬 경로에 임시 저장되어, 컨테이너 재시작 시 작업 상태 및 데이터가 영구적으로 유실된다[cite: 1, 2, 3].

### 1.2. 아키텍처 개편 목표 (Design Objectives)
*   **비동기 분산 서빙 및 API 생존성 확보:** 무거운 GPU 추론으로 인한 메모리 초과(OOM)가 발생하더라도 메인 웹 서버가 다운되지 않도록 프로세스(API Gateway와 추론 워커)를 물리적으로 격리한다[cite: 1, 3].
*   **상태 추적 및 데이터 영속성:** RDBMS를 도입하여 백그라운드 AI 추론의 진행 상태(대기 $\rightarrow$ 처리 중 $\rightarrow$ 완료/실패)를 영구 기록하고 추적한다[cite: 1, 3].
*   **관측성(Observability) 및 네트워크 최적화:** APM 관점의 로깅 체계를 도입하고[cite: 1, 3], 클라이언트와의 통신 프로토콜을 최적화하여 서버 자원 낭비를 방어한다.

---

## 2. 단계별 구현 로드맵 (Action Plan)

### Phase 1: 비동기 작업 큐 및 RDBMS 영속성 구축 (Core Infrastructure)
단일 노드 아키텍처에서 발생하는 I/O 병목 및 데이터 증발을 차단하고[cite: 1, 3], 서버의 생존성을 확보하는 최우선 인프라 작업이다.

*   **기술 스택:** Celery, Redis, PostgreSQL, SQLAlchemy 2.0 (Async), asyncpg, Alembic, Docker Compose[cite: 1, 2, 3].
*   **메시지 브로커 분리 (Celery 채택 방어 논리):** 단일 노드의 인프라 복잡도가 증가한다는 단점에도 불구하고, FastAPI 내부의 `BackgroundTasks` 대신 **Celery와 Redis를 도입**한다. 이는 무거운 GPU 연산 중 OOM 크래시가 발생할 경우 API 서버 전체가 다운되는 치명적 약점을 방어하고, 추론 워커와 API Gateway를 물리적으로 격리하여 서비스의 생존성(Survivability)을 완벽히 보장하기 위함이다[cite: 1, 2].
*   **인프라 및 물리적 데이터 영속성 (IaC):** Docker Compose를 활용해 PostgreSQL 컨테이너를 구성하고, **볼륨(Volume) 마운트**를 명시적으로 설정하여 DB 컨테이너 재시작 시에도 데이터가 초기화되지 않도록 물리적인 영속성을 보장한다[cite: 3].
*   **비동기 ORM 및 트랜잭션 경계 설정:** `SQLAlchemy 2.0` 및 `asyncpg`를 활용하여 FastAPI의 이벤트 루프 블로킹을 방지한다[cite: 1, 3]. 코어 AI 추론 파이프라인(`src/core/pipeline.py`) 내부의 데이터 변경 시 `try-except-finally` 블록으로 DB 트랜잭션 경계를 명확히 하고, 에러 발생 시 안전하게 롤백(Rollback) 되도록 처리한다[cite: 3]. 커넥션 관리는 `async_sessionmaker`를 활용한다[cite: 3].
*   **상태 전이 테이블 (State Transition):** `transcription_tasks` 테이블을 신설하여 4단계 라이프사이클(`PENDING` $\rightarrow$ `PROCESSING` $\rightarrow$ `COMPLETED` $\rightarrow$ `FAILED`)을 기록한다[cite: 1, 2, 3]. 상태 전이 시 **메타데이터(BPM, 검출 노트 수, 악보/MIDI 파일 경로 등)** 및 실패 시의 **예외 트레이스백(Traceback)**을 `JSONB` 형태로 함께 저장하여 로그 분석 및 데이터 자산화를 수행한다[cite: 3].
*   **자가 치유 (Self-healing) 로직:** 워커가 강제 종료될 경우, 서버 기동 시(`Lifespan` 이벤트) 고아 프로세스(`PROCESSING`)를 DB에서 검색하여 `FAILED`로 일괄 롤백하는 상태 정합성 복구 로직을 구현한다[cite: 1, 2, 3].

### Phase 2: 클라이언트 동기화 및 페이로드 최적화 (Network & Data Contracts)
프론트엔드와 백엔드의 강결합을 끊어내고 직렬화(Serialization) 오버헤드를 방어한다[cite: 1, 3].

*   **기술 스택:** FastAPI StreamingResponse (SSE), Pydantic[cite: 1, 2].
*   **상태 동기화 프로토콜 (SSE 도입):** 클라이언트가 주기적으로 상태를 묻는 폴링(Polling) 방식은 불필요한 DB 트랜잭션과 CPU I/O 낭비를 유발한다[cite: 2]. 서버 부하를 최소화하기 위해 **Server-Sent Events (SSE)** 아키텍처를 도입하여, Celery 작업 상태가 갱신될 때마다 클라이언트에 단방향으로 이벤트를 푸시(Push)함으로써 네트워크 리소스를 극도로 최적화한다[cite: 2].
*   **DTO 직렬화 방어:** 대량의 부동소수점 데이터 응답 시 발생하는 페이로드 팽창을 막기 위해, Pydantic `@field_validator`로 모든 숫자 데이터를 밀리초 단위로 강제 반올림 처리한다[cite: 1, 2].
*   **책임 분리 (렌더링 오프로딩 및 원시 데이터 반환):** 서버 단의 무거운 ASCII 악보 문자열 생성 및 **강제 양자화(Grid Snapping) 로직을 걷어낸다**[cite: 2]. 밀리초 단위의 순수 원시 데이터(Unquantized Time)와 모델의 **예측 신뢰도(Confidence)**만을 `NoteEvent` DTO로 반환하며[cite: 2], 박자 스냅 연산 및 시각적 렌더링 부하는 프론트엔드로 전면 위임한다[cite: 1, 2].

### Phase 3: DataOps 및 관측성 확보 (DataOps & Observability)
DSP 알고리즘 튜닝이 동결(Freeze)됨에 따라, 하이퍼파라미터 트래킹 모델 레지스트리(MLflow) 도입은 가용 VRAM 낭비로 판단하여 배제한다[cite: 1]. 대신 인프라 관점의 로깅 및 데이터 리니지로 노선을 전환한다.

*   **기술 스택:** DVC (Data Version Control), Python `logging`[cite: 1].
*   **DVC 기반 데이터 리니지 구축:** Google Drive를 DVC의 Remote Storage로 연동하여 100GB 규모 오디오 데이터셋의 형상(Version)을 관리한다[cite: 1, 2]. 전처리부터 평가까지의 과정을 `dvc.yaml`로 캡슐화하여 100% 재현성(Reproducibility)을 보장한다[cite: 1, 2].
*   **시스템 모니터링 (APM 로깅):** 추론 소요 시간, VRAM 피크 점유율, 구간별 예외(Exception) 발생 빈도를 DB 및 파일 시스템에 정량적으로 로깅하는 관측성 체계를 구축한다[cite: 1].
*   **모델 핫스왑 및 서빙 배포(CD) 체계:** 향후 모델(Demucs $\rightarrow$ BS-RoFormer) 교체 시 하위 파이프라인 수정 없이 무중단 적용이 가능하도록 어댑터 패턴을 설계한다. 이를 바탕으로 Celery 워커 기동 시 **특정 태그(Production)가 부여된 최적 가중치 모델을 동적으로 로드**하는 자동 배포 체계를 마련한다[cite: 2].

### Phase 4: 시스템 강건성 검증을 위한 자동화 CI (Quality Gate)
백엔드 로직 수정이 AI 추론 파이프라인을 붕괴시키는 회귀(Regression)를 사전에 방어한다[cite: 1, 2].

*   **기술 스택:** GitHub Actions[cite: 1, 2].
*   **CPU 기반 Smoke Test 파이프라인:** GitHub Actions 무료 러너의 한계(CPU Only)를 고려하여, 10초 미만의 초경량 더미 오디오 샘플 테스트 환경을 구축한다[cite: 1, 2].
*   **PR 품질 게이트:** `main` 브랜치 병합 전 전체 서빙 파이프라인이 에러 없이 JSON DTO를 정상 반환하는지, **베이스라인 점수가 극단적으로 붕괴하지 않는지** 검증하는 실무적 수준의 CI 파이프라인을 도입한다[cite: 1, 2].

---

## 3. 잠재적 병목 및 방어 전략 (Limitations, Edge Cases & Mitigations)

이 아키텍처가 지닌 기술적 한계 및 향후 발생할 수 있는 엣지 케이스와 그 대응 방안이다.

*   **3.1. 클라우드 관리형 MLOps 서비스 배제 (의도적 설계):** AWS SageMaker, GCP Vertex AI 등 고비용 클라우드 플랫폼의 도입을 의도적으로 배제한다[cite: 2]. 특정 벤더에 종속(Lock-in)되지 않고, 오픈소스 스택을 로컬 컨테이너로 오케스트레이션하여 **예산 0원(Zero-cost) 환경 내에서의 인프라 통제력**을 증명하는 것을 우선한다[cite: 2].
*   **3.2. 단일 노드 인프라의 처리량 상한:** 분산 워커(Celery)를 도입하여 API 생존성을 확보했으나, GPU가 1개인 물리적 노드의 한계로 인해 절대적인 동시 처리량(Throughput) 상한은 동일하게 존재한다[cite: 1]. Kubernetes(EKS/GKE)와 같은 다중 노드 오케스트레이션 확장은 리소스 오버헤드를 유발하므로 주니어 포트폴리오 수준에서는 배제하되[cite: 1, 2], 메모리 회수 매커니즘 최적화를 통해 단일 노드 내 성능을 극대화한다.
*   **3.3. Celery 워커 내부의 비동기 ORM 충돌 위험:** Celery는 동기식 실행 모델이므로, Task 내부에서 `asyncpg` 호출 시 이벤트 루프 충돌(RuntimeError)이 발생할 수 있다. 워커 내부 로직은 동기식 DB 드라이버(`psycopg2`)를 분리 사용하거나 별도의 이벤트 루프 래퍼(Wrapper) 코루틴을 구축하여 시스템을 격리한다.
*   **3.4. 비동기 커넥션 풀 고갈 (Connection Pool Exhaustion):** 트래픽 집중 시 반환되지 않은 DB 커넥션 릭(Leak)으로 인한 장애 위험이 있다[cite: 1, 3]. 세션을 전역 변수로 두지 않고 FastAPI 의존성 주입(`yield`)을 활용하여 요청 종료 시 세션이 자동 `Close` 되도록 강제하며, `expire_on_commit=False`로 비동기 트랜잭션 충돌을 방어한다[cite: 1, 3].
*   **3.5. SSE 역방향 프록시(Reverse Proxy) 버퍼링 문제:** Nginx 등을 배포 환경 리버스 프록시로 적용 시, 버퍼링 설정으로 인해 SSE 이벤트 스트리밍이 지연 전송되는 현상이 발생한다. 인프라 배포 시 Nginx 설정 파일에 `proxy_buffering off;` 구문을 명시적으로 추가하여 방어한다.
*   **3.6. 브라우저 연결 제한 (HTTP/1.1 한계):** HTTP/1.1 환경에서는 단일 도메인 최대 SSE 연결 수가 6개로 제한된다. 다중 탭 동시 채보 시 블로킹(Pending)될 수 있으므로, 향후 Uvicorn과 프록시 서버에 HTTP/2 프로토콜을 활성화하는 설계 여지를 둔다.
