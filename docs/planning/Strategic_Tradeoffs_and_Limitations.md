# ⚖️ Strategic Trade-offs & System Limitations

> **Document Purpose:**
> 본 문서는 프로젝트 개발 과정에서 발견된 시스템적 한계와, 의도적으로 수용한 인프라/프론트엔드 기술 부채(Technical Debt)를 기록합니다. 본 프로젝트의 핵심 목표는 **'오디오 DSP(Digital Signal Processing) 기반의 정밀한 데이터 추출과 커스텀 음원을 활용한 AI 모델 파인튜닝'**에 있으므로, 오버엔지니어링을 방지하고 도메인 로직에 리소스를 집중하기 위해 내린 아키텍처 의사결정의 근거를 명시합니다.

---

## 1. Backend & Infrastructure (전략적 축소 영역)

거대한 분산 시스템 지식에 매몰되는 것을 방지하기 위해 백엔드는 '안전한 단일 노드(Single Node) MVP' 수준으로 제한했습니다.



### 1.1. 동시성 제어: Semaphore vs Distributed Task Queue
* **현재 상태:** FastAPI 라우터에 `asyncio.Semaphore(1)`를 적용하여 다중 요청 시 GPU 추론(Demucs, CREPE)을 1열로 세워 순차 처리(직렬화)합니다.
* **시스템 한계 (Flaw):** 서버의 메모리 초과(OOM)는 완벽히 방어하지만, 처리량(Throughput)이 극도로 제한됩니다. 다수의 사용자가 동시에 긴 오디오를 업로드할 경우, 후순위 사용자는 앞선 작업이 끝날 때까지 무한 대기(Starvation)를 겪게 됩니다.
* **발전 방향 (Future Work):** 트래픽이 임계치를 넘을 경우, FastAPI 코드는 API Gateway 역할만 수행하도록 두고 무거운 연산 블록(`core/pipeline.py`)을 **Celery + Redis(또는 RabbitMQ)** 기반의 백그라운드 워커(Worker) 노드로 스케일 아웃(Scale-out)해야 합니다.

### 1.2. 상태 영속성: 로컬 파일 시스템 vs Cloud Object Storage
* **현재 상태:** 분석 완료된 JSON DTO 및 MIDI 결과물을 도커 컨테이너 내부의 로컬 경로(`outputs/{task_id}.json`)에 저장하고 있습니다.
* **시스템 한계 (Flaw):** 휘발성 저장소(Ephemeral Storage)의 특성상 서버가 재시작되거나 컨테이너 이미지가 교체될 경우, 기존에 분석해둔 모든 유저의 데이터가 영구적으로 유실됩니다. 서버가 무상태(Stateless) 구조를 갖추지 못했습니다.
* **발전 방향 (Future Work):** 로컬 파일 시스템 대신 **AWS S3** 또는 **GCP Cloud Storage**로 결과물을 업로드하고, 클라이언트에게는 Presigned URL을 반환하도록 스토리지 인터페이스(`storage/file_manager.py`)를 교체해야 합니다.

### 1.3. 통신 프로토콜: HTTP Polling vs SSE/WebSocket
* **현재 상태:** 클라이언트(Streamlit)가 3초마다 `GET /status/{task_id}`를 호출하여 작업 완료 여부를 묻는 단순 HTTP Polling 방식을 사용합니다.
* **시스템 한계 (Flaw):** 불필요한 HTTP 연결 수립/해제 오버헤드가 발생하며 네트워크 트래픽을 낭비합니다.
* **발전 방향 (Future Work):** 단방향 실시간 상태 스트리밍이 가능한 **SSE (Server-Sent Events)** 구조로 개편하여 네트워크 효율을 최적화해야 합니다.

---

## 2. Audio DSP & AI Model (코어 도메인 발전 영역)

오디오 데이터 엔지니어링의 완성도를 높이기 위해 향후 직접적으로 개선해 나갈 핵심 영역입니다.



### 2.1. 사전 학습 모델 의존 및 파인튜닝 (Fine-Tuning) 부재
* **현재 상태:** Demucs의 사전 학습된 가중치(`htdemucs`)를 그대로 사용하여 베이스를 분리하고 있습니다.
* **알고리즘 한계 (Flaw):** 일반적인 팝/락 음원에서는 성능이 우수하나, 드롭 튜닝(Drop D 등)된 메탈 베이스나 킥 드럼의 주파수 대역이 베이스와 완전히 겹치는 특수 환경에서는 간섭(Bleeding)이 발생합니다.
* **발전 방향 (Future Work):** 직접 연주하여 녹음한 베이스 DI(Direct Injection) 소스와 드라이브 이펙터 소스, 타 악기(MR) 트랙을 프로그래매틱하게 믹싱 및 증강(Time-stretch, Pitch-shift)하는 자동화 데이터 파이프라인을 구축해야 합니다. 생성된 커스텀 Mixture-Stem 쌍을 바탕으로 **Demucs 모델을 파인튜닝(Transfer Learning)**하여 베이스 분리 한계를 돌파하는 것이 1차 목표입니다. 
* **설계 방어 (Mitigation):** 단, 베이스 특화 데이터로만 학습할 경우 기존 분리 능력(보컬, 드럼 등)을 잃는 **파국적 망각(Catastrophic Forgetting)** 현상이 발생할 수 있습니다. 이를 방지하기 위해 손실 함수(Loss Function)에 규제항(Regularization Term)을 추가하거나, 기존 훈련 데이터(MusDB18)의 일부를 커스텀 데이터와 섞어(Replay) 학습시키는 전략을 반드시 병행해야 합니다.



### 2.2. Viterbi 운지법 수학 모델의 경험적 파라미터 (Heuristic Weights)
* **현재 상태:** Viterbi HMM 디코더의 손가락 이동 비용(Cost)과 하이 프렛 도약 페널티(`max(0, f2 - 7)**1.5`) 수식이 개발자의 경험적 수치(Heuristics)에 의존하고 있습니다.
* **알고리즘 한계 (Flaw):** 연주자의 손 크기나 베이스 기타의 넥 스케일(34인치 vs 30인치)에 따른 물리적 차이를 완벽히 일반화하지 못합니다.
* **발전 방향 (Future Work):** 최종적으로는 역강화학습(IRL) 도입을 목표로 하지만, 현실적인 중간 단계로서 Optuna 등을 활용한 **베이지안 최적화(Bayesian Optimization)**나 **유전 알고리즘(Genetic Algorithm)**을 도입합니다. 검증된 타브 악보 데이터셋(Ground Truth)과 모델 출력 간의 **편집 거리(Levenshtein Distance)**를 최소화하는 방향으로 최적의 전이 비용 가중치($W_f, W_s$)를 자동 탐색하도록 고도화해야 합니다.

### 2.3. ASCII 렌더러의 데이터 표현 한계
* **현재 상태:** 16분음표 격자 단위로 콘솔에 `print`되는 고정 폭 ASCII 텍스트 악보를 사용하고 있습니다.
* **알고리즘 한계 (Flaw):** 3연음(Triplet)이나 슬랩의 고스트 노트 등 16분음표 해상도를 벗어나는 미세한 리듬이 하나의 격자에 중첩될 경우, 문자열 길이 제한(3글자)으로 인해 시각적 덮어쓰기나 절삭 현상이 발생합니다.
* **발전 방향 (Future Work):** 백엔드는 강제 양자화를 배제한 밀리초(ms) 단위의 **Unquantized MIDI 데이터**와 모델의 **예측 신뢰도(Confidence)** 추출에 집중합니다. 렌더링의 책임은 가변 폭을 지원하는 프론트엔드(Canvas/SVG)로 전면 이관하며, 클라이언트는 전달받은 Confidence 점수를 바탕으로 고스트 노트의 투명도(Opacity)를 조절하는 등 불확실한 구간을 시각적으로 처리하도록 역할을 명확히 분리합니다.

---

## 3. DevOps & Quality Assurance



* **정량적 회귀 테스트(Quantitative Regression Test) 시스템 구축:** 일반적인 웹 백엔드의 로직 단위 테스트(`pytest`)만으로는 Audio DSP와 AI 파이프라인의 무결성을 증명할 수 없습니다. 
* 코어 알고리즘(CREPE 파라미터, 필터링, 보정 로직 등)을 리팩토링할 때 기존 성능이 훼손되지 않았음을 검증하기 위해, 사전에 구축된 10곡의 Golden Dataset에 대해 `run_eval.py`를 자동 실행하는 CI/CD 파이프라인을 구축해야 합니다. 이를 통해 **SDR(분리 품질)**과 **피치 정확도(F1-score)**가 이전 커밋 대비 하락하지 않았음을 수치적으로 보장하는 것이 핵심 안정화 과제입니다.
