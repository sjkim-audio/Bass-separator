# [Devlog] 베이스 채보 파이프라인 정량 평가 프레임워크 구축기

**문서 경로:** `docs/devlogs/evaluation_devlog.md`  
**작성 목적:** 주관적 청감에 의존하던 알고리즘 튜닝을 탈피하고, 향후 MLOps 전이 학습(Transfer Learning) 및 알고리즘 고도화의 기준점이 될 정량적 평가 프레임워크의 설계 철학과 노트북 구성, 그리고 핵심 트러블슈팅 내역을 기록한다.

---

## 1. 평가 프레임워크 설계 철학 및 핵심 지표

본 프레임워크는 오디오 음원 분리(Separation)와 미디 채보(Transcription)라는 두 가지 복합적인 파이프라인의 성능을 각각 격리하여 측정하고, 최종적으로 결합된 상태의 성능을 객관적으로 정량화하기 위해 설계되었다.

### 1.1. 평가 지표 세트 (Evaluation Metrics)

**A. 음원 분리 지표 (Separation Metrics - `museval` 적용)**
*   **SDR (Signal-to-Distortion Ratio):** 분리된 베이스 트랙의 전반적인 품질.
*   **SIR (Signal-to-Interference Ratio):** 드럼이나 기타 등 타 악기의 간섭(Bleeding) 억제력.
*   **SAR (Signal-to-Artifacts Ratio):** Demucs 알고리즘 처리에 의해 발생한 인공적 노이즈 정도.

**B. 채보 지표 (Transcription Metrics - `mir_eval` 적용)**
*   **핵심 KPI:** `Onset_Pitch_F1` (어택 시점과 음정이 동시에 일치하는 비율).
*   **베이스 특화 오차 허용 (Tolerance):** `100ms (onset_tolerance=0.1)`. 베이스 기타 특유의 느린 어택(Slow Transient)과 저역대 파장 특성을 반영하여 학계 표준(50ms)보다 완화된 기준을 적용.
*   **Offset 지표 배제:** 앰프 잔향 및 감쇠(Decay) 특성으로 인해 GT와 실제 물리적 종료 시점의 불일치가 심하므로, 평가 신뢰성을 위해 Offset 관련 지표는 채택하지 않음.

### 1.2. 평가 모드 및 A/B 테스팅 전략

*   **Isolated vs. E2E 평가:**
    *   `Isolated Mode`: 정답 베이스 오디오(`bass_gt.wav`)를 직접 입력하여 순수 DSP/채보 알고리즘의 성능만 격리 측정.
    *   `E2E Mode`: 믹스 오디오(`mix.wav`)를 입력하여 Demucs의 분리 손실이 최종 채보 F1-Score에 미치는 영향을 종합 측정.
*   **Raw vs. Quantized 교차 검증:** 평가 루프 내에서 양자화기 통과 전(물리적 시간 보존)과 후(16분음표 격자 강제 스냅)의 F1-Score를 동시 산출하여, Grid Snap 알고리즘이 실제 연주의 Micro-timing을 훼손하는지 혹은 리듬을 교정하는지 그 효용성을 증명.

---

## 2. 데이터Ops 및 평가 노트북 워크플로우 (Colab 환경)

### Phase 0: 데이터 전처리 (`01_data_prep/01_prepare_slakh2100.ipynb`)
*   **데이터셋:** Slakh2100-redux (MIDI 중복 누수 방지를 위한 클린 버전).
*   **음향 무결성 보존:** 단순 오디오 합산 시 발생하는 클리핑을 방지하기 위해 공식 `metadata.yaml`의 `overall_gain`을 수학적으로 적용한 `bassless_mr.wav` 생성.
*   **I/O 최적화:** 무거운 `librosa` 리샘플링을 배제하고 `soundfile` 기반의 온더플라이(On-the-fly) FLAC to WAV 디코딩을 채택하여 수천 곡의 전처리 시간을 획기적으로 단축.

### Phase 1: 기준점 측정 (`04_evaluation/01_baseline_performance_test.ipynb`)
*   **역할:** `slakh_eval` 데이터셋 대상 비동기(`nest_asyncio`) 배치 평가 수행 및 CSV 결과 도출.

### Phase 2: 자동 최적화 (`04_evaluation/02_Hyperparameter_Optimization.ipynb`)
*   **역할:** `Optuna`를 활용해 검증 셋(Validation) 기준 최고 F1-Score를 내는 파라미터(Onset Tolerance, Viterbi Penalty 등)의 자동 탐색.
*   **통제 변인:** 과적합(Overfitting) 방지를 위해 소수 곡 튜닝을 금지하고, 최소 50곡 이상의 무작위 검증 셋을 강제 할당.

### Phase 3: 정성 분석 (`04_evaluation/03_Error_Analysis_and_Visualization.ipynb`)
*   **역할:** 수치 뒤에 가려진 에러의 원인 시각화. GT(Ground Truth)와 예측 악보를 피아노 롤 평면 위에 중첩(Overlap)하여 옥타브 에러, 가짜 노트(Ghost Note) 발생 구간을 추적.

---

## 3. 핵심 트러블슈팅 및 아키텍처 결정 사항 (ADR 요약)

### 3.1. GT MIDI 강제 단선율화 (Monophonic Flattening) 
*   **이슈:** Slakh2100의 GT 악보는 다성부(Polyphony, 더블 스탑 및 레가토)를 포함하나, 파이프라인의 CREPE 모델은 단선율 전용 아키텍처임.
*   **결과:** 모델이 주선율을 완벽히 추적해도 겹친 노트로 인해 부당한 '미검출(False Negative)' 페널티가 발생.
*   **해결:** `evaluation.py`의 `load_midi_to_mir_eval`에 **최종 입력음 우선(Last-Note Priority)** 로직 적용. 겹치는 노트 발생 시 선행 노트를 강제 절단하거나 하위 피치를 삭제하여 GT를 단선율로 평탄화. 알고리즘의 순수 피치 추적 능력을 왜곡 없이 측정 가능해짐.

### 3.2. E2E 평가 시 위상 지연(Latency Shift) 보정 
*   **이슈:** Demucs 모델의 STFT/Conv 연산 구조 패딩으로 인해 출력된 `bass_est.wav`에 원본 대비 수십 ms의 위상 지연 발생.
*   **결과:** 100ms의 타이트한 오차 범위 내에서 시스템 딜레이가 채보 점수를 억울하게 깎아내림.
*   **해결:** 상호상관도(Cross-correlation) 기반의 `align_audio` 함수를 분리 모델 평가(`run_separation_evaluation`)에 삽입하여 시간차를 수학적으로 보정.

### 3.3. Raw vs Quantized 평가 데이터 오염(Data Contamination) 교정
* **이슈:** 초기 평가 로직에서 양자화기(`RhythmicQuantizer`)를 통과한 데이터를 `test_quantized=False` 옵션만 주어 Raw 평가에 재사용함. 양자화기 내부의 '노트 병합(Merging)' 로직이 이미 적용된 상태로 평가되어, 순수 피치 트래커의 성능이 과대/과소평가되는 가짜 베이스라인(False Baseline) 현상 발견.
* **해결:** 코어 파이프라인(`src/core/pipeline.py`)의 반환 시그니처를 수정하여 양자화 전 단계의 데이터(`fingered_events`)를 외부로 노출시키고, 평가 모듈이 이를 분리 주입하도록 E2E 데이터 흐름을 교정함.

### 3.4. 파이프라인 결함 은폐(Masking) 방지 로직 구축
* **이슈:** `TranscriptionEvaluator` 내부에서 노트를 파싱할 때 지속 시간(Duration)이 0 이하일 경우 예외 처리로 50ms를 할당하는 로직이 존재함. 이로 인해 상위 모듈(Parser, Quantizer)에서 꼬리 절단(Truncation) 오류가 발생해도 콘솔에 에러가 노출되지 않고 정상 수치로 채점되는 관측성 결여 문제 발견.
* **해결:** `duration <= 0` 인 엣지 케이스 발생 시 `logging.warning`을 강제로 출력하도록 수정하여, 잠재적인 파이프라인 버그(시간 역전 등)를 개발자가 즉시 인지하고 추적할 수 있는 안전장치 확립.

---

## 4. 시스템 한계점 및 향후 과제 (Limitations & Future Work)

1.  **폴리포니(Polyphony) 정보의 영구적 소실:** 단선율 평탄화 적용으로 알고리즘 측정의 왜곡은 막았으나, 연주자의 의도적인 화음 연주 및 서스테인 뉘앙스는 평가 단계에서 측정할 수 없다. 이는 향후 다성부 피치 트래커(Polyphonic Pitch Tracker) 도입 전까지 유지되는 아키텍처 한계다.
2.  **합성 데이터의 강건성(Robustness) 검증 불가:** 정량 평가는 가상 악기(VSTi)로 렌더링된 Slakh 데이터에 한정된다. 실제 베이스 연주 특유의 물리적 노이즈(프렛 버즈, 슬랩 어택, 앰프 노이즈) 대응력은 확인할 수 없다.
3.  **Next Step:** 본 프레임워크에서 도출된 E2E F1-Score를 '베이스라인'으로 동결한다. 향후 실제 DI 소스와 노이즈를 결합한 데이터 증강(Data Augmentation) 기법으로 Demucs 파인튜닝을 수행하고, F1-Score의 상승폭을 증명해야 한다.
