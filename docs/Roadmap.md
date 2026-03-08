# 🎸 Bass Source Separation & Automatic Transcription Pipeline (Clean MVP Roadmap)



특히 클린 아키텍처(Clean Architecture) 원칙을 강제하여, 현재의 단일 노드(FastAPI) 구조가 향후 거대한 비동기 인프라로 진화(Scale-out)할 때 코드를 폐기하지 않고 100% 재사용할 수 있도록 설계되었다.

---

### Phase 1. 기준점 설정 및 인프라 평가 (Baseline & Infrastructure)
> **Status:** Completed
> **Goal:** 객관적인 분리 성능 기준을 확립하고, 모델 서빙을 위한 단일 노드 아키텍처 뼈대를 구축한다.

- [x] **Baseline 모델 확립:** 종합 성능이 우수한 `htdemucs` 4-Stem 기본 모델을 최종 채택 및 합산 후처리 로직 적용.
- [x] **컨테이너화 (Dockerization):** `python:3.10-slim` 기반 환경에 `ffmpeg` 등 시스템 의존성을 캡슐화하여 OS별 DLL 충돌 에러(`WinError 1114`) 원천 차단.
- [x] **API 뼈대 구축:** FastAPI 프레임워크를 도입하여 오디오 파일 업로드 및 디스크 I/O 처리 라우터 구현.

### Phase 2. 자동 채보 및 피치 트래킹 (Deep Learning Transcription)
> **Status:** Completed
> **Goal:** 딥러닝 알고리즘을 활용해 분리된 베이스 오디오에서 기본 주파수(f0)를 정밀하게 추출한다.

- [x] **Deep Learning Pitch Tracking:** `torchcrepe` 알고리즘을 도입하여 베이스 음역대(40~500Hz)에 특화된 고해상도 피치 추출.
- [x] **Robust Signal Processing:** `librosa.onset` 및 주파수 필터를 결합하여 음악적 맥락(어택 보존, 배음 제어)을 반영한 스마트 옥타브 보정 함수 도입.
- [x] **Scalable Inference:** 제한된 GPU VRAM 내에서 대용량 오디오를 안정적으로 처리하는 30초 단위 분할 추론(Chunking) 최적화.

### Phase 3. 클린 아키텍처 및 데이터 컨트랙트 (Clean Architecture & Data Contract) [진행 중 🚀]
> **Status:** In Progress
> **Goal:** 인프라 확장을 보장하는 디렉토리 격리 원칙을 수립하고, 완벽한 데이터 직렬화 규격 및 서버 방어 로직을 구현한다.



- [ ] **코어 로직 격리 (Decoupling):** 파이프라인 엔진(`core/audio_engine.py`)을 순수 함수로 설계하여 FastAPI(`api/routers.py`)와의 의존성을 완벽히 끊어낸다. 코어 로직 내에서는 프레임워크 예외(`HTTPException`) 대신 순수 파이썬 예외(`ValueError` 등)만 발생시키도록 강제한다.
- [ ] **Pydantic DTO 설계:** `TranscriptionResponse` 스키마 작성. MLOps 메타데이터(모델 버전), 모델 신뢰도(Confidence Score), 부동소수점 3자리 제한(밀리초 해상도)을 강제하여 데이터 페이로드 최적화.
- [ ] **Semaphore 기반 동시성 제어:** FastAPI 런타임에 `asyncio.Semaphore(1)`를 적용하여, 다중 업로드 시 모델 추론을 강제 직렬화(Sequential Execution)함으로써 단일 노드 서버의 다운을 완벽히 방어.
- [ ] **BackgroundTasks 및 상태 저장소 구축:** 무거운 DSP 연산을 백그라운드 스레드로 넘기고 `UUID(task_id)`와 HTTP 202(Accepted)를 즉시 반환. 완료된 데이터는 로컬 파일 시스템(`outputs/{task_id}.json`)에 직렬화하여 저장(Storage Interface).

### Phase 4. 타브 생성 및 운지법 최적화 (Smart Fingering & Export)
> **Status:** Pending
> **Goal:** 추출된 주파수 배열을 실제 연주자의 물리적 한계를 고려한 타브 악보 및 MIDI로 변환한다.

- [ ] **Smart Fingering Model (Viterbi):** 동적 계획법(HMM)을 도입하여 손의 수평/수직 이동 비용(Cost)을 최소화하는 최적의 프렛-현(Fret-String) 맵핑 도출.
- [ ] **Unquantized MIDI Export:** 16분음표 강제 양자화를 배제하고, 추출된 밀리초 단위의 미세한 리듬(Micro-timing)과 다이내믹스를 온전히 보존한 표준 `.mid` 파일 생성.
- [ ] **ASCII Tablature Rendering:** 클라이언트의 요청이 있을 때만 정량적 16분음표 격자로 스냅(Snap)하여 시각적 가독성을 확보하는 가로형 텍스트 악보 렌더링.

### Phase 5. 도메인 시각화 및 배포 (Visualization & Deployment)
> **Status:** Planned
> **Goal:** 분석된 오디오 데이터를 직관적으로 검증하고 시각화한다.

- [ ] **Streamlit 대시보드 구축:** 파이썬 기반의 웹 UI를 통해 오디오 업로드 및 Polling 인터페이스 구현. 3초 주기로 `GET /status/{task_id}`를 호출하여 서버 디스크에 해당 파일이 생성되었는지 상태를 확인.
- [ ] **오디오 도메인 시각화:** 반환된 JSON DTO를 파싱하여 Librosa 기반의 스펙트로그램(Spectrogram), 피아노 롤(Piano Roll), Confidence 분포도를 화면에 렌더링.
- [ ] **문서화:** 전체 아키텍처 한계 방어 논리 및 의존성 분리(Decoupling) 최적화 과정(ADR) 문서화.

### Phase 6. 데이터 중심 성능 개선 (DataOps & Fine-tuning) (Optional)
> **Status:** Planned
> **Goal:** 커스텀 데이터를 합성하고 실험 과정을 체계적으로 관리하여 모델 성능의 한계를 파악한다.

- [ ] **Data Augmentation:** Python(`librosa`, `audiomentations`)을 이용한 타 악기 노이즈 믹싱, Pitch Shift, Time Stretch 자동화 파이프라인 구축.
- [ ] **Training-Serving Skew 방어:** 훈련 데이터 생성 시 서빙 환경과 동일한 Sample Rate 변환 전처리 모듈 강제.
- [ ] **Experiment Tracking:** 로컬 환경에서 MLflow 연동을 통해 하이퍼파라미터 추적 및 모델 파인튜닝 지표(SDR, SIR) 로깅.
