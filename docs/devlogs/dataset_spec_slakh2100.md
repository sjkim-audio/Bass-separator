# [DataOps Spec] Slakh2100 데이터셋 가공 및 평가 프로토콜 (v1.3)

* **Document Stage:** Phase 8 (Quantitative Evaluation Framework)
* **Target Dataset:** Synthesized Lakh (Slakh) Dataset 2100 - `Redux` Version
* **Last Updated:** 2026-07-03

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

## 3. 전처리 파이프라인 (Data Preprocessing & I/O Architecture)

본 파이프라인은 로컬 PC의 하드디스크 용량 한계(Out of Storage)와 RAM 병목(OOM)을 회피하기 위해, 100GB 아카이브를 디스크에 풀지 않고 처리하는 **2-Pass 순수 스트리밍(On-the-fly) 아키텍처**를 채택한다. (관련 스크립트: `extract_streaming.py`)

### 3.1. 무결성 검증 (Metadata Scanning - Pass 1)
100GB `.tar.gz` 아카이브의 헤더(목차)만 메모리에 올려 `metadata.yaml`을 1차 스캔하며 다음 방어 로직을 통과한 트랙만 타겟팅한다.
* **렌더링 실패 방어:** `inst_class: Bass`로 지정되어 있어도 엔진 에러로 오디오가 생성되지 않은 깡통 스템(`audio_rendered: false`)을 명시적으로 배제하여 FFmpeg I/O 크래시 원천 차단.
* **다중 베이스 필터링:** 한 곡 내에 베이스(Synth Bass, Electric Bass 등)가 2개 이상 존재하는 앙상블 트랙은 Ground Truth(GT)의 1:1 매칭 모호성을 유발하므로 평가 모수에서 제외(Skip)한다.

### 3.2. 스트리밍 추출 및 변환 (Target Extraction - Pass 2)
무결성 검증을 통과한 유효 151곡의 3가지 핵심 파일만 추출한다.
* **추출 대상:** `mix.flac`, `[bass_stem].flac`, `[bass_stem].mid`
* **변환 사이클:** 단일 트랙별로 3개 파일만 임시 샌드박스로 추출 $\rightarrow$ `FFmpeg` 서브프로세스를 통해 `.wav`로 즉시 인코딩 $\rightarrow$ 즉시 원본 임시 파일 삭제. 
* **용량 최적화:** 위 과정을 통해 피크 디스크 점유량을 105GB 미만으로 억제하며, 최종적으로 약 **5GB 용량의 `slakh_test.zip`** 알짜 데이터셋만 생성하여 구글 드라이브(무료 한도 내) 업로드를 지원한다.

## 4. 정량 평가 프로토콜 (Evaluation Protocol)

### 4.1. 정답 MIDI 평탄화 (Monophonic Flattening)
CREPE 트래커의 단선율(Monophonic) 제약을 고려하여, 다성부(Polyphony)가 포함된 정답 MIDI를 가공한다.
* **로직:** **Last-Note Priority (후입 우선 원칙)**
    * 노트 오버랩 발생 시, 뒤에 연주된 노트가 앞 노트를 강제로 종료(Truncate)시킨다.
    * 동시 타현(화음)의 경우, 가장 높은 피치의 노트만 남기고 나머지는 삭제한다.

### 4.2. 이중 계층 평가 체계 (Dual-Layer Evaluation)
하나의 트랙 폴더 내에 공존하는 3개의 파일(`mix.wav`, `bass_gt.wav`, `bass_gt.mid`)을 활용하여, 파이프라인의 **음원 분리(Separation)와 기호화(Transcription) 성능을 End-to-End로 분리 추적**한다.

**[Layer 1: 음원 분리 지표 - Demucs]**
* **입력:** `mix.wav` $\rightarrow$ **출력:** `pred_bass.wav`
* `museval (BSSEval v4)`을 사용하여 `pred_bass.wav`와 `bass_gt.wav` 간의 파형을 비교한다.
* **SDR (Signal-to-Distortion Ratio):** 전체적인 분리 품질.
* **SIR (Signal-to-Interference Ratio):** 타 악기의 간섭(Bleeding) 정도.

**[Layer 2: 채보 성능 지표 - CREPE + HMM]**
* **입력:** `pred_bass.wav` $\rightarrow$ **출력:** 예측된 `NoteEvent` 리스트
* `mir_eval.transcription`을 사용하여 예측된 노트와 `bass_gt.mid`를 1:1 매칭한다.
* **허용 오차:** Onset $\pm$ 100ms (`--onset_tolerance 0.1`)
* **핵심 지표:**
    * **Precision:** 가짜 노트 및 고스트 노트 억제력.
    * **Recall:** 미검출 방지력.
    * **F1-Score:** 파이프라인의 최종 종합 점수.

## 5. 분석 및 로드맵 (Roadmap)

* **A/B 테스팅:** 양자화(Quantization) 전/후의 점수를 비교하여, 리듬 격자 스냅이 음악적 정확도에 미치는 영향 분석.
* **에러 분석:** 옥타브 에러 발생 빈도를 수치화하여 Viterbi HMM의 전이 확률(Transition Probability) 조정 근거로 활용.

## 6. 데이터셋 평가 목적 부합성 및 한계 (Fitness & Limitations)

Slakh2100 데이터셋은 우리 시스템의 수학적 무결성을 검증하는 **'상한선(Upper-bound) 벤치마크'**로 채택되었다.

* **강점 (Strengths):** 신디사이저로 합성된 오디오이므로, 파형(WAV)과 악보(MIDI) 간의 밀리초(ms) 단위 타이밍 오차가 완벽한 Zero에 가깝다. 노이즈 변수 없이 Demucs 분리 품질과 CREPE의 순수 알고리즘 정확도를 측정하기에 최적화되어 있다.
* **한계 (Limitations):** 실제 사람이 연주하는 어쿠스틱 환경에서의 프렛 버즈(Fret buzz), 피크 마찰음, 뮤트 질감 등 휴먼 팩터(Human Factor)가 결여되어 있다. 
* **결론:** Slakh2100에서의 F1-Score는 인비트로(In-vitro) 환경에서의 통제된 성능 지표이며, 향후 In-the-wild(실제 유튜브 커버 영상 등) 환경 투입 시 발생하는 도메인 갭(Domain Gap)을 보정하기 위해 추가적인 데이터 증강(Data Augmentation) 테스트가 필수적이다.
