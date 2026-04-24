# [DataOps Spec] Slakh2100 데이터셋 가공 및 평가 프로토콜

* **Document Stage:** Phase 8 (Quantitative Evaluation Framework)
* **Target Dataset:** Synthesized Lakh (Slakh) Dataset 2100 - `Redux` Version

## 1. 목적 및 철학 (Purpose & Philosophy)

본 프로젝트의 채보 알고리즘(CREPE 파라미터, Viterbi 최적화 등)은 Phase 6까지 개발자의 주관적 청감과 소수의 데모 음원에 의존해 튜닝되었다. 이는 필연적으로 특정 주법에 대한 과적합(Overfitting)과 수확 체감을 유발한다.

이 문서는 AI가 산출한 **미디 노트(MIDI Note) 변환 성능을 객관적으로 검증**하고, 향후 Demucs 모델의 **베이스 특화 파인튜닝(Fine-Tuning)을 위한 정량적 베이스라인(Baseline)을 구축**하기 위해 공식 Slakh2100 데이터셋의 전처리 규격과 평가 프로토콜을 정의한다.

## 2. 데이터셋 규격 및 선정 (Dataset Specification)

* **버전 선정:** `Slakh2100-redux` (총 1,710 트랙)
* **선정 사유:** 원본(`orig`) 버전에 존재하는 MIDI 파일 중복 버그(동일한 악보가 여러 곡의 다른 신스로 렌더링된 현상)를 완벽히 제거한 클린 버전이다. 평가 지표의 신뢰성(Data Leakage 방지)을 위해 반드시 Redux 버전을 사용한다.
* **오디오 규격:** 44.1kHz, 16-bit, Mono

## 3. 전처리 파이프라인 (Data Preprocessing)

평가 스크립트(`src/run_eval.py`)가 자동화된 순회를 할 수 있도록, 코랩(Colab) 환경에서 `scripts/prepare_slakh.py`를 구동하여 곡당 다음 4개의 파일을 추출 및 믹스다운한다.

### 3.1. 추출 및 변환 로직
1. **`bass_gt.wav` (SDR 정답):** `metadata.yaml` 기준 MIDI Program Number 32~39(Electric Bass) 또는 43(Contrabass)인 스템을 식별하여 `.flac`에서 `.wav`로 무손실 디코딩한다.
2. **`bass_gt.mid` (F1-score 정답):** 위에서 식별된 베이스의 원본 MIDI 악보를 추출한다.
3. **`mix.wav` (E2E 소스):** 원본 혼합 음원(`mix.flac`)을 WAV로 변환하여 저장한다.

### 3.2. 음향적 무결성 확보 (Acoustic Consistency)
* **`bassless_mr.wav` (템포 맵 검증용):** 베이스를 제외한 나머지 스템을 병합할 때 단순 합산 시 발생하는 클리핑을 막기 위해, 임의의 정규화(Peak Normalization)를 금지한다.
* 반드시 공식 메타데이터에 명시된 게인 값을 사용하여 **$Audio = (\sum Stem_{other}) \times overall\_gain$** 공식을 적용, 원본 믹스와 100% 동일한 음압을 보장한다.

## 4. 정량 평가 프로토콜 (Evaluation Protocol)

### 4.1. 모듈 격리 평가 (Isolated Mode)
Demucs의 분리 에러가 채보 점수에 미치는 영향을 배제하고, 순수 '음정 추적 및 양자화기 알고리즘'의 성능만 측정한다.
* **입력 데이터:** `bass_gt.wav`
* **측정 지표:** `mir_eval` (Onset, Pitch F1-Score)
* **실행:** `python src/run_eval.py --mode trans --isolated`

### 4.2. 도메인 특화 허용 오차 (Bass-Specific Tolerance)
베이스 기타 특유의 긴 파장(Low Frequency)과 느린 어택(Slow Transient) 물리 특성을 반영하여, `mir_eval`의 Onset 일치 허용 오차를 **표준 50ms에서 100ms(`--onset_tolerance 0.1`)로 확장**하여 적용한다. 이는 MIR 학계의 베이스 채보 논문 표준을 따른다.

### 4.3. 양자화 A/B 테스팅 (Raw vs Quantized)
하나의 평가 루프 내에서 양자화기 통과 전(물리적 밀리초 보존)과 후(16분음표 격자 강제 스냅)의 F1-Score를 동시 산출한다. 이를 통해 격자 스냅 알고리즘이 실제 연주의 Micro-timing을 얼마나 훼손하거나 혹은 음악적으로 보정해 주는지 격차(Delta)를 추적한다.

## 5. 시스템 한계 및 향후 계획 (Limitations & Roadmap)

* **합성 데이터의 한계 (Lack of Transients):** Slakh2100은 가상 악기(VSTi)로 렌더링된 데이터이므로, 실제 베이시스트의 핑거링 노이즈, 슬랩 타격음, 앰프 험(Hum) 등의 물리적 노이즈가 결여되어 있다.
* **MLOps 파인튜닝 로드맵:** 본 데이터셋 측정으로 얻은 초기 F1-Score를 베이스라인으로 고정한다. 이후 실제 연주 DI(Direct Injection) 소스와 노이즈를 데이터 증강(Augmentation) 기법으로 합성하여 Demucs 모델을 전이 학습(Transfer Learning)시키고, 점수의 상승폭을 증명한다.
