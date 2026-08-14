# 🎸 Bass Source Separation & Automatic Transcription Pipeline (Macro Roadmap)

이 로드맵은 과도한 백엔드 인프라(Celery, Redis) 및 프론트엔드 실시간 통신(SSE, WebSocket) 도입으로 인한 기술 부채를 의도적으로 배제하고, '오디오 디지털 신호 처리(DSP) 및 데이터 엔지니어링' 본연의 가치 증명에 집중하여 작성되었습니다. 클린 아키텍처(Clean Architecture) 원칙을 적용하여 현재의 단일 노드(FastAPI) 제약 사항을 수용하되, 코어 알고리즘의 유연성을 보장하는 거시적(Macro) 발전 단계를 정의합니다.

---

### Phase 1. 기준점 설정 및 인프라 평가 (Baseline & Infrastructure)
> **Status:** Completed
> **Goal:** 객관적인 음원 분리 성능의 기준을 확립하고, 제한된 환경을 위한 단일 노드 아키텍처 뼈대를 구축한다.

*   **Baseline 모델 확립:** 종합 분리 성능이 우수한 `htdemucs` 4-Stem 모델을 도입하고, 추론 완료 후 CPU 단에서 트랙을 합산하여 MR(Bassless)을 생성하는 구조를 확립했습니다.
*   **컨테이너화 (Dockerization):** `python:3.10-slim` 기반 환경에 `ffmpeg` 등 시스템 의존성을 캡슐화하여 OS별 환경 변수 누락 및 DLL 초기화 에러를 회피했습니다.
*   **API 뼈대 구축:** FastAPI 프레임워크를 도입하여 오디오 파일 업로드 및 디스크 I/O를 처리하는 라우터를 구현했습니다. (클라우드 스토리지 연동 없이 로컬 파일 시스템을 활용하는 무상태 구조 수용)

### Phase 2. 자동 채보 및 피치 트래킹 (Deep Learning Transcription)
> **Status:** Completed
> **Goal:** 딥러닝 알고리즘과 도메인 특화 필터를 결합하여 베이스 오디오에서 기본 주파수(f0)를 일관되게 추출한다.

*   **Deep Learning Pitch Tracking:** `torchcrepe` 알고리즘을 도입하고, 베이스 5현의 대역폭을 고려하여 하한선(`fmin`)을 40Hz로 고정해 인덱싱 슬라이스 오류를 억제했습니다.
*   **Onset-Bounded Segmental Filtering:** 정적 트렌드가 장기 옥타브 에러에 동화되는 현상을 완화하기 위해, 타격점(Onset) 기준으로 오디오를 격리된 조각(Segment)으로 나누어 중앙값을 산출하는 파티션 필터를 도입했습니다.
*   **Wobble Tolerance Buffer:** 배음 간섭으로 인한 서스테인 파편화를 억제하고자 50ms 지연 버퍼를 파서(Parser)에 신설했습니다. 단, 3반음 이하의 변화는 슬라이드로 간주하여 예외 처리했습니다.

### Phase 3. 클린 아키텍처 및 시스템 안정화 (Clean Architecture & Stability)
> **Status:** Completed
> **Goal:** 인프라 확장을 보장하는 디렉토리 격리 원칙을 수립하고, 단일 노드 환경에서의 추론 안정성을 방어한다.

*   **코어 로직 격리 (Decoupling):** 파이프라인 엔진(`core/pipeline.py`)을 순수 함수형으로 설계하고 불변 데이터 클래스(`NoteEvent`)를 도입하여 상태 오염을 제어했습니다.
*   **Task Sandbox 격리:** 파일 I/O 충돌을 방지하기 위해 고유 `task_id` 기반의 샌드박스 디렉토리 할당 및 개별 가비지 컬렉션 구조를 적용했습니다.
*   **동시성 제어 및 VRAM 회수:** 분산 작업 큐(Celery) 도입을 유보하고 `asyncio.Semaphore(1)`를 통한 GPU 직렬화를 채택했습니다. OOM 발생 시 배치 사이즈를 절반으로 줄여 재시도하는 동적 백오프(Dynamic Backoff) 로직을 구축했습니다.
*   **Pydantic DTO 설계:** 응답 스키마에 부동소수점 3자리 제한을 강제하여 직렬화 페이로드를 억제하고 신뢰도(Confidence) 메타데이터를 보존했습니다.

### Phase 4. 리듬 양자화 및 운지법 최적화 (Quantization & Smart Fingering)
> **Status:** Completed
> **Goal:** 추출된 주파수 및 시간 배열을 실제 연주자의 물리적 한계를 고려한 형태(타브/MIDI)로 정규화한다.

*   **Smart Fingering Model (Viterbi):** 동적 계획법(HMM)을 통해 수평/수직 이동, 하이 프렛 도약 비선형 페널티 등을 수식화하여 최적의 프렛-현 경로를 산출합니다.
*   **동적 격자 평가 (Dynamic Grid Snapping):** 16분음표 격자의 기계적 스냅을 넘어, 오차 제곱합(SSE) 기반으로 박자별 3연음과 16분음표 중 더 적합한 해상도를 동적으로 평가해 그루브를 보존합니다.
*   **출력 계층 다각화:** 텍스트 기반 ASCII 악보 렌더링(복잡한 UI 렌더링 기술 부채 수용)을 지원하며, 양자화를 배제해 물리적 리듬(Micro-timing)을 보존한 표준 `.mid` 파일 추출 로직을 병행 구축했습니다.

### Phase 5. 평가 프레임워크 구축 및 시각화 (Evaluation & Visualization)
> **Status:** Completed
> **Goal:** 주관적 튜닝을 탈피하기 위한 데이터 전처리 기반을 마련하고, 도메인 정규화를 통해 객관적 평가 기준을 정립한다.

*   **2-Pass 스트리밍 추출 (DataOps):** 100GB 규모의 Slakh2100 데이터셋 처리 시 스토리지 부족을 회피하기 위해, 아카이브를 직접 풀지 않고 메타데이터 스캔 후 FFmpeg로 즉시 추출/변환하는 파이프라인을 확립했습니다.
*   **도메인 정규화 및 위상 동기화:** 벤치마크 평가 시 발생하던 정답지(GT)의 1옥타브 편향을 물리 주파수로 정규화하고, 분리 모델을 거치며 발생하는 위상 지연(Latency Shift)을 상호상관도로 동기화했습니다.
*   **Streamlit 대시보드 구축:** SSE 통신 구축을 보류하고 단순 HTTP Polling 방식을 채택하여 서버 자원 고갈을 방지하면서 분석 결과를 직관적으로 검증하는 MVP UI를 연동했습니다.

---

### Phase 6. 향후 과제: 평가 지표 정착 및 MLOps 고도화 (Future Works)
> **Status:** Planned
> **Goal:** 객관적인 데이터(Baseline)를 기반으로 시스템의 실질적 유용성을 검증하고, 오디오 도메인 특화 모델 파인튜닝 로드맵을 가동한다.

**우선순위 1: Baseline F1-Score 도출 및 오답 분류 체계화**
*   도메인이 정규화된 정량 평가기(`evaluator.py`)를 Slakh2100 합성 데이터셋에 가동하여 양자화 전후의 Onset-Pitch F1-Score 기준점(Baseline)을 측정합니다.
*   False Positive(노이즈 오인), False Negative(노트 증발) 등 지배적 오답 유형(Taxonomy)을 분류하여 후속 알고리즘 개선의 근거로 활용합니다.

**우선순위 2: 리얼 월드 데이터셋 교차 검증 (Real-world Cross Validation)**
*   합성 데이터(Slakh2100) 평가가 가지는 과적합 위험 및 앰프 험(Hum), 프렛 버즈(Fret buzz) 대응력 부재 한계를 방어하기 위해 수행합니다.
*   소규모의 실제 어쿠스틱/일렉트릭 베이스 연주 소스를 별도로 수집 및 주석 처리하여, 합성 데이터 환경과의 체감 성능 괴리를 교차 검증합니다.

**우선순위 3: 표준 악보 직렬화 엔진 구축 (Standard Notation Export)**
*   단순 ASCII 텍스트 콘솔 출력을 넘어 `MusicXML`(`.xml`) 또는 `GuitarPro`(`.gp5`) 형식의 파일을 생성하는 직렬화 계층을 신설합니다.
*   이 과정에서 원본의 리듬을 보존하려는 기조와 악보 가독성을 확보하려는 기조 간의 트레이드오프를 조율하는 '음악적 평탄화(Musical Smoothing)' 휴리스틱을 연구합니다.

**우선순위 4: 데이터 증강(Data Augmentation) 및 파인튜닝 파이프라인**
*   사전 학습 모델(Demucs)이 특수 환경(드롭 튜닝, 강한 킥 드럼 잔향 등)에서 겪는 간섭(Bleeding) 한계를 극복하기 위한 중장기 과제입니다.
*   `librosa` 등을 활용해 타 악기 트랙을 프로그래매틱하게 믹싱/변형하는 파이프라인을 구축하여 모델의 노이즈 강건성을 높입니다.
