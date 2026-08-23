# 🚀 MLOps Evolution Roadmap: 단일 노드 기반 비용 효율적 MLOps 파이프라인 고도화

**문서 경로:** `docs/planning/MLOps_Evolution_Roadmap.md`  
**작성 목적:** 코어 AI 알고리즘의 튜닝이나 모델 자체의 구조 개조(Research)를 지양하고, 완성된 모델을 어떻게 안정적이고 효율적으로 서빙(Serving)할 것인가에 집중한다. 대규모 트래픽 수용, 시스템 안정성 확보, 데이터 및 모델의 생애주기 관리(Lifecycle Management) 등 **백엔드 및 MLOps 엔지니어링 역량**을 증명할 수 있는 프로덕션 레벨 아키텍처로의 발전 방향을 정의한다.

---

## 1. 1단계: 비동기 분산 서빙 및 작업 영속화 (Model Serving & Persistence)
**우선순위:** 매우 높음 (현재 아키텍처의 가장 큰 시스템 병목 해소)  
**도입 기술:** Celery, Redis, SQLite (또는 경량 PostgreSQL), SSE (Server-Sent Events)  

**현재 상태 및 한계:** FastAPI 내부에서 `asyncio.Semaphore(1)`를 통해 추론을 제어하고 있어 트래픽 유입 시 서버 블로킹 위험이 있으며, 재시작 시 작업 상태가 유실되는 무상태(Stateless) 결함이 존재한다[cite: 1].

*   **메시지 브로커 및 Task Queue 분리 (서빙 안정성):** 
    *   FastAPI는 HTTP 요청을 받아 메시지 브로커(Redis)에 작업을 Enqueue하고 즉시 `202 Accepted`를 반환하는 API Gateway 역할로 책임을 축소한다[cite: 1].
    *   무거운 GPU 연산(Demucs, CREPE)은 독립된 Celery Worker 컨테이너로 위임하여, 단일 GPU 환경에서도 OOM 없이 순차적으로 대기열(Queue)을 소화하도록 시스템을 격리한다[cite: 1].
*   **작업 상태 추적 및 DB 영속화:** 
    *   단순 임시 파일 덤프를 폐기하고, 가벼운 RDBMS(SQLite/PostgreSQL)를 도입하여 작업의 생명주기(`PENDING` $\rightarrow$ `PROCESSING` $\rightarrow$ `COMPLETED` $\rightarrow$ `FAILED`)를 영구 저장한다[cite: 1]. 
    *   워커 컨테이너가 OOM으로 강제 종료되더라도 서버 기동 시 고아 프로세스를 `FAILED`로 처리하는 자가 치유(Self-healing) 및 복구 로직을 백엔드 단에 구현한다[cite: 1].
*   **SSE 기반 상태 스트리밍:** 
    *   주기적 Polling이 유발하는 네트워크 및 DB 조회 낭비를 배제하고, FastAPI `StreamingResponse`를 통해 Celery Task 상태를 클라이언트에 단방향 푸시(SSE)하는 효율적인 통신 프로토콜을 구축한다[cite: 1].

---

## 2. 2단계: 데이터 컨트랙트 및 API 페이로드 최적화 (Data Contracts)
**우선순위:** 높음 (시스템 분리 및 프론트엔드 연동을 위한 규격화)  
**도입 기술:** Pydantic (Data Validation)

**현재 상태 및 한계:** 데이터 추출 규격이 파편화되어 있고 서버가 시각적 렌더링까지 강제 제어하고 있어, 향후 워커-API 서버 간 분리 시 직렬화 오버헤드가 발생할 위험이 크다[cite: 1].

*   **표준화된 DTO 및 직렬화 오버헤드 방어:** 
    *   대량의 부동소수점 데이터 응답 시 발생하는 페이로드 팽창을 막기 위해, Pydantic `@field_validator`로 모든 숫자 데이터를 밀리초 단위로 강제 반올림 처리하여 네트워크 트래픽을 최적화한다[cite: 1].
*   **Unquantized 타임스탬프 반환 및 서버 경량화:** 
    *   서버 단의 강제 양자화(Grid Snapping) 및 악보 문자열 생성 로직을 제거한다[cite: 1]. 
    *   서버는 밀리초 단위의 순수 원시 데이터(Raw Unquantized Time)와 모델의 예측 신뢰도(Confidence)만 반환하며, 시각적 렌더링 및 박자 스냅 연산은 클라이언트(프론트엔드)로 오프로딩하여 서버 CPU 부하를 절감한다[cite: 1].

---

## 3. 3단계: 파이프라인 캡슐화 및 실험 추적 (DataOps & Model Registry)
**우선순위:** 높음 (재현성 확보 및 MLOps 파이프라인 자산화)  
**도입 기술:** MLflow, DVC (Data Version Control)  

**현재 상태 및 한계:** 100GB 규모의 데이터 버전 관리가 불가능하며, JSON 파일 기반의 결과 저장으로는 버전별 성능 변화를 시계열적으로 비교하거나 배포를 자동화하기 어렵다[cite: 1].

*   **DVC 기반 데이터 리니지 (Data Lineage) 구축:**
    *   비용 발생이 없는 Google Drive를 DVC의 Remote Storage로 연동하여 대용량 오디오 데이터셋의 형상(Version)을 관리한다[cite: 1].
    *   전처리부터 평가까지의 과정을 `dvc.yaml`로 캡슐화하여, 단일 명령어(`dvc repro`)만으로 환경 제약 없이 파이프라인을 완벽히 재현(Reproducibility)하는 DataOps 뼈대를 완성한다[cite: 1].
*   **MLflow 기반 모델 레지스트리 및 모니터링:** 
    *   평가 스크립트 실행 시 F1-Score, SDR 등의 추론 지표와 산출물(`.wav`, `.mid`)을 MLflow Tracking Server에 자동 기록한다[cite: 1].
    *   향후 모델이 업데이트될 경우 최적 가중치(`.pt`)를 Model Registry에 등록하고, Celery Worker 컨테이너 기동 시 `Production` 태그가 붙은 모델을 동적으로 로드하는 서빙 배포(CD) 체계를 마련한다[cite: 1].

---

## 4. 4단계: 시스템 강건성 검증을 위한 품질 게이트 (Automated CI)
**우선순위:** 보통 (백엔드 코드 수정에 따른 안정성 보장)  
**도입 기술:** GitHub Actions  

**현재 상태 및 한계:** 백엔드 서빙 코드나 파이프라인 로직 수정 시, 기존에 잘 동작하던 추론 프로세스가 붕괴하는 현상(Regression)을 사전에 감지할 수 없다[cite: 1].

*   **CPU 기반 Smoke Test CI 구축:**
    *   GitHub Actions 무료 러너의 컴퓨팅 한계(CPU Only)를 고려하여, 10초 미만의 초경량 샘플 오디오(마이크로 데이터셋) 테스트 환경을 구축한다.
    *   `main` 브랜치에 PR 생성 시, 전체 서빙 파이프라인이 에러 없이 동작하여 최종 JSON DTO를 정상 반환하는지, 베이스라인 점수가 극단적으로 붕괴하지 않는지 확인하는 현실적 수준의 품질 게이트(Quality Gate)를 자동화한다.

---

## 5. 아키텍처 트레이드오프 (의도적 배제 사항)
개인 프로젝트 수준의 한정된 자원 환경에서 오버엔지니어링을 방지하고, "문제 해결의 실용성과 백엔드 인프라의 효율성"을 어필하기 위해 내린 기술 도입 배제 근거이다.

*   **5.1. Kubernetes (K8s) 클러스터 도입 배제:** 
    *   단일 노드(Single GPU) 환경에서 K8s Control Plane 구동은 과도한 CPU/RAM 오버헤드를 유발하여 실제 추론 워커에 할당될 자원을 갉아먹는다. 클라우드 관리형 클러스터(EKS/GKE) 유지 비용을 회피하고, `Docker Compose`와 `Redis/Celery`의 조합만으로도 충분히 비동기 큐잉 및 로드 분산(Scale-out) 아키텍처를 시스템적으로 증명할 수 있다고 판단했다.
*   **5.2. 클라우드 관리형 MLOps 서비스 배제:** 
    *   AWS SageMaker, GCP Vertex AI 등 고비용 클라우드 플랫폼의 도입을 배제한다. 특정 벤더에 종속(Lock-in)되지 않고, 오픈소스 스택(MLflow, DVC, Redis)을 로컬 컨테이너로 자체 오케스트레이션함으로써 예산 0원(Zero-cost) 환경 내에서 백엔드 및 MLOps 인프라를 주도적으로 설계하는 능력을 입증한다.
