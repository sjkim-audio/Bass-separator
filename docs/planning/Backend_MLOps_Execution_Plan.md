# 🚀 Backend & MLOps Execution Plan (백엔드 인프라 및 MLOps 실행 계획서)

**작성 목적:** 단일 스크립트 형태의 AI 파이프라인을 비동기 상태 추적과 데이터 영속성(Persistence)이 보장되는 상용 서비스 레벨로 고도화하기 위한 아키텍처 변경 계획 및 마일스톤을 정의한다. 무분별한 오버엔지니어링을 경계하면서도, 트래픽 병목 해소와 **API 서버의 생존성(Survivability)**을 보장하는 실용적인 엔지니어링 표준을 수립한다.

---

## 1. 아키텍처 현황 및 개편 목표

### 1.1. 현재 상태의 한계
*   **동시성 병목:** FastAPI 내부에서 `asyncio.Semaphore(1)`를 통해 추론을 제어하고 있어 트래픽 유입 시 서버 블로킹 및 무한 대기(Starvation) 위험이 존재한다.
*   **무상태(Stateless) 결함:** 분석 완료된 데이터가 도커 내부의 로컬 경로에 임시 저장되어, 컨테이너 재시작 시 작업 상태 및 데이터가 영구적으로 유실된다.

### 1.2. 아키텍처 개편 목표 (Design Objectives)
*   **비동기 분산 서빙 및 API 생존성 확보:** 무거운 GPU 추론으로 인한 메모리 초과(OOM)가 발생하더라도 메인 웹 서버가 다운되지 않도록 프로세스를 물리적으로 격리한다.
*   **상태 추적 및 데이터 영속성:** RDBMS를 도입하여 백그라운드 AI 추론의 진행 상태(대기 $\rightarrow$ 처리 중 $\rightarrow$ 완료/실패)를 영구 기록하고 추적한다.
*   **관측성(Observability) 및 네트워크 최적화:** APM 관점의 로깅 체계를 도입하고, 클라이언트와의 통신 프로토콜을 최적화하여 서버 자원 낭비를 방어한다.

---

## 2. 단계별 구현 로드맵 (Action Plan)

### Phase 1: 비동기 작업 큐 및 RDBMS 영속성 구축 (Core Infrastructure)
단일 노드 아키텍처에서 발생하는 I/O 병목 및 데이터 증발을 차단하고, 서버의 생존성을 확보하는 최우선 인프라 작업이다.

*   **기술 스택:** Celery, Redis, PostgreSQL, SQLAlchemy 2.0 (Async), asyncpg, Alembic
*   **메시지 브로커 분리 (Celery 채택 방어 논리):** 단일 노드의 인프라 복잡도가 증가한다는 단점에도 불구하고, FastAPI 내부의 `BackgroundTasks` 대신 **Celery와 Redis를 도입**한다. 이는 무거운 GPU 연산 중 OOM 크래시가 발생할 경우 API 서버 전체가 다운되는 치명적 약점을 방어하고, 추론 워커와 API Gateway를 물리적으로 격리하여 서비스의 생존성(Survivability)을 완벽히 보장하기 위함이다.
*   **비동기 ORM 및 트랜잭션 관리:** `SQLAlchemy 2.0` 및 `asyncpg`를 활용하여 FastAPI의 이벤트 루프 블로킹을 방지하며 DB 트랜잭션을 관리한다. `Alembic`을 도입하여 스키마 형상 관리를 자동화한다.
*   **상태 전이 테이블 (State Transition):** `transcription_tasks` 테이블을 신설하여 4단계 라이프사이클(`PENDING` $\rightarrow$ `PROCESSING` $\rightarrow$ `COMPLETED` $\rightarrow$ `FAILED`)을 기록한다.
*   **자가 치유 (Self-healing) 로직:** 워커가 강제 종료될 경우, 서버 기동 시(`Lifespan` 이벤트) 고아 프로세스(`PROCESSING`)를 DB에서 검색하여 `FAILED`로 일괄 롤백하는 상태 정합성 복구 로직을 구현한다.

### Phase 2: 클라이언트 동기화 및 페이로드 최적화 (Network & Data Contracts)
프론트엔드와 백엔드의 강결합을 끊어내고 직렬화(Serialization) 오버헤드를 방어한다.

*   **기술 스택:** FastAPI StreamingResponse (SSE), Pydantic
*   **상태 동기화 프로토콜 (SSE 도입):** 클라이언트가 주기적으로 상태를 묻는 폴링(Polling) 방식은 불필요한 DB 트랜잭션과 CPU I/O 낭비를 유발한다. 서버 부하를 최소화하기 위해 **Server-Sent Events (SSE)** 아키텍처를 도입하여, Celery 작업 상태가 갱신될 때마다 클라이언트에 단방향으로 이벤트를 푸시(Push)함으로써 네트워크 리소스를 극도로 최적화한다.
*   **DTO 직렬화 방어:** 대량의 부동소수점 데이터 응답 시 발생하는 페이로드 팽창을 막기 위해, Pydantic `@field_validator`로 모든 숫자 데이터를 밀리초 단위로 강제 반올림 처리한다.
*   **책임 분리 (렌더링 오프로딩):** 서버 단의 무거운 ASCII 악보 문자열 생성 로직을 걷어내고, 밀리초 단위의 순수 기호 데이터(`NoteEvent` DTO)만 반환하여 시각적 렌더링 부하는 프론트엔드로 위임한다.

### Phase 3: DataOps 및 관측성 확보 (DataOps & Observability)
DSP 알고리즘 튜닝이 동결(Freeze)됨에 따라, 하이퍼파라미터 트래킹 모델 레지스트리(MLflow) 도입은 가용 VRAM 낭비로 판단하여 배제한다. 대신 인프라 관점의 로깅 및 데이터 리니지로 노선을 전환한다.

*   **기술 스택:** DVC (Data Version Control), Python `logging`
*   **DVC 기반 데이터 리니지 구축:** Google Drive를 DVC의 Remote Storage로 연동하여 100GB 규모 오디오 데이터셋의 형상(Version)을 관리한다. 전처리부터 평가까지의 과정을 `dvc.yaml`로 캡슐화하여 100% 재현성(Reproducibility)을 보장한다.
*   **시스템 모니터링 (APM 로깅):** 추론 소요 시간, VRAM 피크 점유율, 구간별 예외(Exception) 발생 빈도를 DB 및 파일 시스템에 정량적으로 로깅하는 관측성 체계를 구축한다.
*   **모델 핫스왑 아키텍처 준비:** 향후 분리 모델(Demucs $\rightarrow$ BS-RoFormer) 교체 시 하위 파이프라인 수정 없이 무중단(Hot-swap) 적용이 가능하도록 어댑터 패턴(Adapter Pattern) 인터페이스를 사전 설계한다.

### Phase 4: 시스템 강건성 검증을 위한 자동화 CI (Quality Gate)
백엔드 로직 수정이 AI 추론 파이프라인을 붕괴시키는 회귀(Regression)를 사전에 방어한다.

*   **기술 스택:** GitHub Actions
*   **CPU 기반 Smoke Test 파이프라인:** GitHub Actions 무료 러너의 한계(CPU Only)를 고려하여, 10초 미만의 초경량 더미 오디오 샘플 테스트 환경을 구축한다.
*   **PR 품질 게이트:** `main` 브랜치 병합 전 전체 서빙 파이프라인이 에러 없이 JSON DTO를 정상 반환하는지 자동 검증하는 실무적 수준의 CI 파이프라인을 도입한다.

---

## 3. 잠재적 병목 및 방어 전략 (Limitations & Mitigations)

### 3.1. 비동기 커넥션 풀 고갈 (Connection Pool Exhaustion)
*   **위험:** 트래픽 집중 시 반환되지 않은 DB 커넥션 릭(Leak)으로 인한 장애 위험.
*   **대응:** 세션을 전역 변수로 두지 않고 FastAPI 의존성 주입(`yield`)을 활용하여 요청 종료 시 세션이 Pool로 자동 `Close` 되도록 강제한다. SQLAlchemy 세션에 `expire_on_commit=False`를 적용하여 비동기 트랜잭션 충돌을 방어한다.

### 3.2. 단일 노드 인프라의 한계
*   **위험:** 분산 워커를 도입하더라도 GPU가 1개인 물리적 노드의 한계로 인해 절대적인 처리량(Throughput) 상한이 존재함.
*   **대응:** Kubernetes(EKS/GKE)와 같은 다중 노드 오케스트레이션은 주니어 포트폴리오 수준에서 오버엔지니어링으로 판단하여 의도적으로 배제한다. 현 아키텍처 내에서 워커 격리(Celery)와 SSE 통신을 통해 단일 노드 자원을 한계점까지 최적화하는 데 집중한다.
