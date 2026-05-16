# [DataOps Spec] Slakh2100 데이터셋 가공 및 평가 프로토콜 (v1.2)

* **Document Stage:** Phase 8 (Quantitative Evaluation Framework)
* **Target Dataset:** Synthesized Lakh (Slakh) Dataset 2100 - `Redux` Version
* **Last Updated:** 2026-05-15

## 1. 목적 및 철학 (Purpose & Philosophy)

본 문서는 베이스 채보 파이프라인의 성능을 정량화하기 위한 **'Golden Dataset'**의 구축 규격을 정의한다.
* **객관성 확보:** 개발자의 주관적 판단을 배제하고 `mir_eval` 표준 지표에 기반한 성능 평가 체계 구축.
* **재현성 유지:** 동일한 전처리 파라미터(`overall_gain`, `resampling`)를 적용하여 실험 간 비교 가능성 확보.
* **데이터 누수 차단:** 학습(Train)과 평가(Test) 데이터 간의 MIDI 중복을 원천 차단하여 모델의 일반화 성능 검증.

## 2. 데이터셋 규격 및 선정 (Dataset Specification)

### 2.1. 버전 및 분할 (Splits)
* **Target:** `Slakh2100-redux` (총 1,710 트랙)
* **선정 근거:** `orig` 버전에 존재하는 MIDI 중복 버그(Data Leakage)를 제거한 유일한 클린 버전.
* **배분 현황:** * **Train:** 1,289 tracks (향후 파인튜닝용)
    * **Validation:** 270 tracks (Optuna 하이퍼파라미터 튜닝용)
    * **Test:** 151 tracks (최종 성능 벤치마크 및 리드미 게재용)

### 2.2. 오디오 규격 (Audio Standards)
* **Format:** 무손실 리니어 PCM (WAV)
* **Sample Rate:** 44,100 Hz (CD Quality 유지)
* **Bit Depth:** 16-bit
* **Channels:** Mono (모든 분석 및 모델 입력은 모노를 표준으로 함)

## 3. 전처리 파이프라인 (Data Preprocessing)

### 3.1. 베이스 트랙 식별 및 추출 (Feature Extraction)
`metadata.yaml`의 `program_num`을 기반으로 베이스 기타 트랙을 엄격히 격리한다.
* **추출 대상:** * `32~39`: Electric Bass 계열 (Finger, Pick, Fretless, Slap 등)
    * `43`: Contrabass (Acoustic Bass)
* **예외 처리:** 한 곡 내에 베이스 트랙이 2개 이상 존재할 경우, 변수 통제를 위해 해당 트랙은 평가 세트에서 제외한다.

### 3.2. 음향적 무결성 및 믹스다운 수학 (Gain Management)
단순 합산 시 발생하는 디지털 클리핑을 방지하기 위해 공식 `overall_gain`을 적용한다.
* **믹스다운 공식:** $Audio_{final} = (\sum Stem_{other}) \times overall\_gain$
* **원칙:** 임의의 Peak Normalization을 금지하여 원본 Slakh 믹스와의 음압(Loudness) 일치성을 확보한다.

## 4. 정량 평가 프로토콜 (Evaluation Protocol)

### 4.1. 정답 MIDI 평탄화 (Monophonic Flattening)
CREPE 트래커의 단선율(Monophonic) 제약을 고려하여, 다성부(Polyphony)가 포함된 정답 MIDI를 가공한다.
* **로직:** **Last-Note Priority (후입 우선 원칙)**
    * 노트 오버랩 발생 시, 뒤에 연주된 노트가 앞 노트를 강제로 종료(Truncate)시킨다.
    * 동시 타현(화음)의 경우, 가장 높은 피치의 노트만 남기고 나머지는 삭제한다.

### 4.2. 채보 성능 지표 (Transcription Metrics)
`mir_eval.transcription` 모듈을 사용하며, 다음 세부 지표를 핵심 KPI로 설정한다.
* **허용 오차:** Onset $\pm$ 100ms (`--onset_tolerance 0.1`)
* **핵심 지표:**
    * **Precision:** 모델이 예측한 노트 중 실제 정답과 일치하는 비율 (가짜 노트/고스트 노트 억제력).
    * **Recall:** 실제 정답 중 모델이 찾아낸 비율 (미검출 방지력).
    * **F1-Score:** Precision과 Recall의 조화 평균 (파이프라인의 종합 점수).

### 4.3. 음원 분리 지표 (Separation Metrics)
`museval (BSSEval v4)`을 사용하여 Demucs 모델의 성능을 측정한다.
* **SDR (Signal-to-Distortion Ratio):** 전체적인 분리 품질.
* **SIR (Signal-to-Interference Ratio):** 타 악기의 간섭(Bleeding) 정도.

## 5. 분석 및 로드맵 (Roadmap)

* **A/B 테스팅:** 양자화(Quantization) 전/후의 점수를 비교하여, 리듬 격자 스냅이 음악적 정확도에 미치는 영향 분석.
* **에러 분석:** 옥타브 에러 발생 빈도를 수치화하여 Viterbi HMM의 전이 확률(Transition Probability) 조정 근거로 활용.
* **데이터 증강 계획:** 향후 실제 연주 노이즈(프렛 버즈 등)를 Slakh 데이터에 합성하여 모델의 강건성(Robustness) 테스트를 수행할 예정.
