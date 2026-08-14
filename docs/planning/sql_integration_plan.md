# E2E 채보 파이프라인 비동기 상태 관리 및 데이터 영속성 도입 계획서

**작성 목적:** 단일 스크립트 형태의 AI 파이프라인을 비동기 상태 추적과 데이터 영속성(Persistence)이 보장되는 시스템으로 고도화하기 위한 아키텍처 변경 계획 및 마일스톤을 정의한다. 시스템의 복잡도를 제어하면서도 데이터의 라이프사이클을 온전히 관리할 수 있는 엔지니어링 표준을 수립한다.

---

## 1. 도입 배경 및 시스템 목표

무거운 딥러닝 추론(Demucs, CREPE)을 수행하는 현재 파이프라인은 동기적 요청 시 클라이언트의 HTTP 연결 타임아웃을 유발할 위험이 존재한다. 이를 구조적으로 해결하고, 시스템의 관측성(Observability)을 확보하기 위해 관계형 데이터베이스(RDBMS)를 도입한다.

### 1.1. 설계 목표 (Design Objectives)
*   **비동기 상태 추적(State Management):** 클라이언트에게 작업 ID(Task ID)를 즉시 반환하고, 백그라운드에서 실행되는 AI 추론의 진행 상태(대기 → 처리 중 → 완료/실패)를 DB에 기록하여 폴링(Polling) 기반의 안정적인 응답 처리 지원.
*   **데이터 영속성 보장(Data Persistence):** 추출된 메타데이터(BPM, 검출 노트 수, 소요 시간, 악보/MIDI 파일 경로 등)를 영구 저장하여, 향후 통계 모델링 및 분석을 위한 데이터 자산화.
*   **Infrastructure as Code (IaC):** Docker Compose를 활용한 컨테이너 기반 인프라 구축으로 개발 환경의 일관성과 통제력 확보.

### 1.2. 시스템 복잡도 제어 (Complexity Control)
본 파이프라인은 단일 노드(Single Node) 환경에서 동작하므로, 무분별한 기술 도입(오버엔지니어링)을 경계하고 목적에 부합하는 적정 기술을 채택한다.
*   **배제 대상 1 (클라우드 관리형 DB):** 불필요한 네트워크 지연 및 운영 비용 방지를 위해 로컬 컨테이너 기반 데이터베이스로 한정.
*   **배제 대상 2 (분산 메시지 큐):** Redis/Celery 등의 수평적 확장(Scale-out) 도구는 단일 노드 아키텍처에서 불필요한 복잡도를 야기하므로 보류. 기존 FastAPI의 `BackgroundTasks`와 세마포어(Semaphore) 조합을 활용한 동시성 제어 구조 유지.

---

## 2. 아키텍처 및 기술 스택

파이썬 기반 비동기 백엔드 표준에 입각하여 I/O 병목을 원천 차단하는 기술 스택을 구성한다.

| 분류 | 기술 스택 | 선정 사유 |
| :--- | :--- | :--- |
| **Database** | **PostgreSQL** (Docker) | 트랜잭션 무결성 확보 및 JSONB 등 유연한 데이터 타입 지원. |
| **ORM** | **SQLAlchemy 2.0 (Async)** | 파이썬 객체와 DB 테이블 매핑. 최신 2.0 문법 채택으로 완벽한 타입 힌팅 및 비동기 지원. |
| **DB Driver** | **asyncpg** | 동기식 DB 드라이버 사용 시 발생하는 이벤트 루프 블로킹(AI 추론 마비) 방어. |
| **Migration** | **Alembic** | 정적 테이블 생성을 지양하고, 향후 알고리즘 고도화에 따른 스키마 형상 관리(Version Control) 적용. |

---

## 3. 작업 라이프사이클 및 상태 전이 (State Transition)

`transcription_tasks` 테이블을 중심으로 다음 4단계의 상태 전이 시나리오를 설계한다.

1.  **`PENDING` (대기):** 오디오 파일 업로드 즉시 FastAPI가 고유 해시와 함께 레코드를 `INSERT`하고 `task_id`를 반환.
2.  **`PROCESSING` (처리 중):** 백그라운드 워커가 세마포어를 통과하여 VRAM에 모델을 로드하고 추론을 시작하는 시점에 상태를 `UPDATE`.
3.  **`COMPLETED` (완료):** E2E 채보 파이프라인의 모든 렌더링이 종료되면 산출물(Tab, MIDI 경로) 및 채보 메타데이터를 `UPDATE`.
4.  **`FAILED` (실패):** OOM(Out of Memory) 또는 파싱 단계의 치명적 에러 발생 시, 예외(Exception)를 포착하여 상태를 변경하고 에러 트레이스백을 DB에 기록.

---

## 4. 단계별 구현 계획 (Action Plan)

### Phase 1: 컨테이너 인프라 및 환경 구축
*   `docker-compose.yml` 작성: PostgreSQL 15+ 컨테이너 구성 및 볼륨(Volume) 마운트를 통한 물리적 데이터 영속성 보장.
*   패키지 의존성 업데이트: `requirements.txt`에 `asyncpg`, `sqlalchemy`, `alembic` 추가.

### Phase 2: 데이터베이스 스키마 및 비동기 ORM 설계
*   `TranscriptionTask` 엔티티 모델링 (`src/database/models.py`).
*   `Alembic` 비동기(Async) 템플릿 환경 구성 및 초기 마이그레이션 스크립트 베이스라인 구축.
*   `async_sessionmaker`를 활용한 커넥션 풀 설정 및 FastAPI 생명주기에 맞춘 의존성 주입(`get_db`) 제너레이터 구현 (`src/database/session.py`).

### Phase 3: 비동기 I/O 파이프라인 결합
*   API 라우터(`src/api.py`) 수정: `BackgroundTasks`와 연계하여 작업 위임 및 `task_id` 응답 로직 추가.
*   코어 파이프라인(`src/core/pipeline.py`) 내부 트랜잭션 처리: `try-except-finally` 블록 내부에 상태 변경 SQL 트랜잭션(`session.commit()`) 안전하게 결합.

### Phase 4: 폴링(Polling) API 및 프론트엔드 연동
*   클라이언트 상태 조회 전용 API 엔드포인트(`GET /tasks/{task_id}`) 구축.
*   Streamlit 프론트엔드에 비동기 폴링 루프를 연동하여 작업 진행도(Progress) 동기화 및 최종 산출물 다운로드 인터페이스 구현.

---

## 5. 예상 한계점 및 시스템 방어 전략 (Limitations & Mitigations)

데이터베이스 이식 시 파생될 수 있는 시스템 병목과 상태 불일치 문제를 사전에 차단하기 위한 엔지니어링 방어 전략이다.

### 5.1. 비동기 커넥션 풀 고갈 (Connection Pool Exhaustion)
*   **문제:** 비동기 환경에서 트래픽이 일시적으로 집중될 경우, 반환되지 않은 커넥션 릭(Leak)으로 인해 DB 연결 가능 수를 초과하여 시스템 장애 유발 가능성 존재.
*   **방어 전략:** 
    *   세션을 전역 변수로 관리하지 않고, FastAPI의 의존성 주입(`yield`)을 통해 HTTP 요청 종료 시점에 세션이 풀(Pool)로 자동 반환(`Close`)되도록 컨텍스트 관리를 강제함.
    *   SQLAlchemy 세션 생성 시 `expire_on_commit=False` 속성을 명시하여, 비동기 트랜잭션 종료 후 지연 로딩(Lazy-loading)으로 인한 컨텍스트 충돌 에러 차단.

### 5.2. 고아 프로세스 및 상태 불일치 (Orphan Tasks & Inconsistency)
*   **문제:** VRAM 한계로 인해 파이썬 프로세스가 강제 종료(OOM Kill)될 경우, DB에는 `PROCESSING` 상태로 영구히 남게 되는 고아 프로세스 발생.
*   **방어 전략:** 시스템 재시작 시 구동되는 `Lifespan` 이벤트(`@app.on_event("startup")`)에 자가 치유(Self-healing) 로직을 결합. 서버 기동 시 DB에 남아있는 모든 `PROCESSING` 상태의 태스크를 검색하여 `FAILED`로 일괄 롤백(Rollback) 처리함으로써 상태 정합성을 복구함.
