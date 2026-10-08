# [ADR-017] DB 커넥션 풀 보호를 위한 단명 세션(Short-lived Session) 패턴 및 연산 격리

* **Status:** Accepted
* **Date:** 2026-09-26 (Retroactively Documented for Phase 9)
* **Category:** Backend-Infra / Database
* **Related Documents:** [SQL_Integration_devlog.md](../devlogs/SQL_Integration_devlog.md)

## 1. Context (배경)

Phase 9에서 데이터 영속성을 위해 PostgreSQL과 비동기 ORM(`SQLAlchemy 2.0` + `asyncpg`)을 도입했다[cite: 1]. 
API 라우터에서 작업의 상태(PENDING, PROCESSING, SUCCESS, FAILED)를 기록하기 위해 DB 세션을 사용하게 되는데, 초기 구상에서는 하나의 API 요청 라이프사이클 전체를 단일 DB 세션으로 묶어 처리하는 방식을 고려했다.

하지만 본 프로젝트의 핵심 도메인인 오디오 분리(Demucs) 및 피치 추적(CREPE) 연산은 짧게는 수십 초에서 길게는 수 분이 소요되는 무거운 작업이다. 
딥러닝 워커 스레드가 실행되는 동안 DB 커넥션을 닫지 않고 유지(Hold)할 경우, 다중 요청 유입 시 커넥션 풀(`pool_size=5`)이 순식간에 고갈되어 후속 클라이언트들이 DB 타임아웃 에러를 겪거나 데드락(Deadlock)에 빠지는 치명적인 인프라 장애가 예상되었다[cite: 1].

## 2. Decision (결정)

DB 세션의 점유 시간을 최소화하고 코어 연산을 보호하기 위해 **단명 세션(Short-lived Session) 패턴** 및 **DB-연산 책임 격리** 아키텍처를 채택한다[cite: 1].

1. **상태 기록 시점 분리:** API 루프 내에서 DB 세션을 한 번만 여는 것이 아니라, 1) 작업 수락(PENDING), 2) 추론 시작 전(PROCESSING), 3) 추론 완료 후(SUCCESS/FAILED) 등 DB 업데이트가 필요한 찰나의 순간에만 `async with AsyncSessionLocal() as db:`를 열어 상태를 커밋하고 **즉시 커넥션을 풀에 반환(Close)**한다[cite: 1].
2. **코어 파이프라인의 DB 무관성(Agnosticism):** `loop.run_in_executor`를 통해 넘겨지는 딥러닝 연산 컨텍스트 내부로는 어떠한 DB 세션 객체나 ORM 모델도 전달하지 않는다. 오직 파일 경로(String) 등 순수 원시 데이터만 넘겨, 코어 파이프라인(`pipeline.py`)이 데이터베이스의 존재를 전혀 모른 채 연산에만 집중하도록 격리한다[cite: 1].

## 3. Rationale (의사결정 근거)

### 3.1. 커넥션 풀(Connection Pool) 생존성 보장
데이터베이스 커넥션은 웹 서버에서 가장 값비싸고 제한적인 자원 중 하나다. 연산(CPU/GPU)을 기다리며 유휴 상태(Idle)로 커넥션을 붙잡고 있는 것은 전형적인 안티 패턴(Anti-pattern)이다. 트랜잭션을 잘게 쪼개어 단명 세션으로 관리함으로써 제한된 풀 사이즈 내에서도 수많은 비동기 폴링 및 상태 업데이트 요청을 병목 없이 처리할 수 있다.

### 3.2. 완벽한 도메인 결합도 최소화 (Decoupling)
AI 알고리즘 모듈(`src/core/pipeline.py`)은 오디오를 받아 악보 데이터를 뱉는 순수 도메인 로직에만 충실해야 한다. 이 계층이 ORM 기술 스택(SQLAlchemy)과 격리됨으로써, 향후 DB 엔진을 변경하거나 파이프라인만 따로 떼어내어 다른 서비스(Celery Worker 등)로 이식할 때 코드 수정 비용이 발생하지 않는다.

## 4. Consequences (결과)

* **Positive:** 
    * 긴 추론 시간에도 불구하고 DB 커넥션 릭(Leak)이나 풀 고갈 현상이 원천 차단되었다[cite: 1].
    * 웹 서버(FastAPI)와 인프라(DB), 그리고 AI 도메인의 역할 분리(SoC)가 명확해졌다[cite: 1].
* **Negative & Limitations:** 
    * 단일 태스크의 전체 상태 전이를 처리하기 위해 `app/main.py` 내부에서 DB 세션을 열고 닫는 보일러플레이트 코드(`async with ...`)가 3~4번 중복 발생하여 코드의 길이는 다소 길어졌다[cite: 1]. (이는 인프라 안정성을 위해 수용한 트레이드오프다.)
