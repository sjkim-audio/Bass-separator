# 🎸 Automatic Bass Transcription Pipeline (DevLog)

> **Status:**
> Phase 1 Completed (Rule-based Transcription)
> Phase 2 Completed (Deep Learning-based Tracking & Error Correction)
> Phase 3 In Progress (Smart Tablature Generation & Optimization)

## 1. Overview
이 프로젝트는 믹스된 오디오에서 베이스를 분리하고 **실제 연주 가능한 타브 악보(ASCII Tab)**를 생성하는 End-to-End 파이프라인입니다. 

초기(Phase 1)에는 `librosa.pyin`을 사용했으나, 분리된 베이스 음원(Stem)의 낮은 음질과 노이즈로 인해 정확도가 떨어지는 한계가 있었습니다. 현재(Phase 2)는 **SOTA 딥러닝 모델인 CREPE**를 도입하고, 베이스에 특화된 전/후처리(Pre/Post-processing) 로직을 통해 피치 인식률을 비약적으로 향상시켰습니다. 나아가 물리적 연주 가능성(Playability)을 고려한 최적 운지법 추천 모델(Phase 3)을 개발 중입니다.

---

## 2. Technical Pipeline (Phase 2 Architecture)

현재 파이프라인은 다음 5단계로 고도화되었습니다.

### Step 1: Source Separation
- **Model:** `Demucs (htdemucs)`
- **Optimization:** `--two-stems=bass` 모델이 연산 속도와 실성능(베이스 추출 및 MR 제작 목적) 면에서 프로젝트의 목표에 가장 부합한다고 판단하여 2-Stem 구조로 회귀 및 확정.
- **Notebook:** `01_Melody_Extraction...`, `02_tracking_separated...`

### Step 2: Audio Pre-processing (Signal Cleaning)
- **High-pass Filter:** 35Hz 미만의 비음악적 노이즈(DC Offset, Rumble) 제거.
- **Normalization:** 오디오 파형의 최대 진폭을 1.0으로 정규화하여 모델의 입력 감도 확보.
- **Precision Optimization:** `scipy` 필터링 후 팽창된 `float64` 배열을 `float32`로 다운캐스팅하여 VRAM 누수 방지.

### Step 3: Deep Learning Pitch Tracking 
- **Algorithm:** `torchcrepe` (CNN-based Pitch Tracker)
- **Notebook:** `04_tracking_by_CREPE.ipynb`, `06_Main_pitch_track.ipynb`
- **Robust Configuration:**
  - **Decoder:** `Argmax` (Viterbi 방식보다 노이즈 환경에서 생존율 높음).
  - **Resolution:** 10ms (Hop Length: 160 @ 16kHz).
  - **Scope:** `fmin=40Hz` (Low E 근사치) ~ `fmax=500Hz`.
  - **VRAM/Speed Optimization:** `tiny` 모델을 기본값으로 채택하여 고속 추론을 확보하고, CUDA OOM 방지를 위해 오디오를 30초 단위 청크(Chunk)로 분할 처리 및 명시적 가비지 컬렉션 적용. Apple Silicon(MPS) 하드웨어 가속 지원 추가.

### Step 4: Error Correction (Post-processing)
- **Notebook:** `05_Octave_Error_Correction.ipynb`, `06_Main_pitch_track.ipynb`
- **Pipeline Reordering:** 이동 중앙값(Rolling Median) 연산 오류를 방지하기 위해 결측치(NaN) 마스킹을 수학적 보정(Median, Octave) 이후 가장 마지막 단계로 재배치.
- **Smart Octave Correction (Onset-aware):** `librosa.onset`을 활용하여 진폭(에너지) 급증 구간을 추출. 옥타브 도약(±12 Semitone) 발생 시 전후로 어택(Onset)이 존재하면 의도된 연주(Slap 등)로 보존하고, 지속음 구간의 도약만 배음 에러로 간주하여 강제 보정.

### Step 5: Tab Generation (Baseline)
- **Notebook:** `08_tab_gen_advanced.ipynb`
- **Logic:** `Lowest Fret Priority` (Greedy Algorithm) 기반의 1차원적 매핑.
- **Visualization:** CREPE의 시간축(`hop_length`)과 동기화하여 리듬 간격을 대시(`-`)로 시각화한 가로형 ASCII 악보 렌더링. 자동 줄바꿈(Word-wrap) UI 안정화 적용.

---

## 3. Result Preview

**Input:** Mixed Audio File (.wav)
**Output:** ASCII Tablature (Baseline Model)

```text
🎸 Generated Bass Tab (Standard Tuning G-D-A-E)

G |----------------------------------------------------------------------------|
D |--0---------0--0------------------------------------------------------------|
A |---------------------------------------------3----3------------0----0-----0-|
E |--------------------3--------3--3--------------------------------------4----|
```

---

## 4. Challenges & Solutions (Troubleshooting)

개발 과정에서 발생한 주요 문제점과 해결 방안입니다.

| Issue | Cause | Solution |
| :--- | :--- | :--- |
| **Phase 1 (Rule-based)** | | |
| **Octave Error** | 배음(Harmonics)을 기본음으로 오인하거나 피치 트래킹이 불안정함. | `fmax`를 500Hz로 제한하고 `frame_length`를 4096으로 확장하여 저음 해상도 확보. |
| **Pitch Instability** | 어택(Attack) 순간의 줄 장력 변화로 인한 피치 흔들림. | Onset 감지 후 약 0.05초 뒤의 피치 값들의 중간값(Median)을 취하는 안정화 로직 도입. |
| **Dependency Conflict** | `torchcodec`과 `torchaudio` 버전 간의 호환성 문제. | `subprocess`를 활용한 시스템 레벨(FFmpeg) 설치 및 라이브러리 재설치 자동화 스크립트 작성. |
| **Readability** | 단순 터미널 로그 출력으로 인한 가독성 저하. | 버퍼링(Buffering) 방식을 도입하여 가로형 악보 렌더링 및 자동 줄바꿈 구현. |
| **Phase 2 (Deep Learning)** | | |
| **Low-end Noise** | 피치가 31Hz 부근에서 일직선으로 그려짐 (실제 연주가 아님). | Demucs 분리 과정에서 남은 초저역 노이즈. **35Hz High-pass Filter (`scipy.signal.butter`)** 적용으로 해결. |
| **CUDA OOM Error & Float Bloat** | 긴 오디오 텐서 변환 시 GPU 메모리 한계 초과 및 `float64` 타입 캐스팅으로 인한 메모리 팽창. | 모델 추론부를 **30초 단위 오디오 Chunking 처리**로 분할. 추가로 `float32` 명시적 다운캐스팅 및 `tiny` 파라미터 노출로 VRAM 점유율 최적화. |
| **NaN Propagation** | 신뢰도 기반 Masking(`NaN` 할당)을 너무 일찍 수행함. | Rolling 윈도우 연산이 망가지지 않도록 **마스킹 단계를 스파이크 제거 및 옥타브 보정 이후로 연기(Reordering)**. |
| **False Positive Octave Jump** | 기계적 보정 로직이 의도된 연주(Slap & Pop 등)까지 평탄화시켜 버림. | **Onset(어택) 탐지 로직을 결합**하여 에너지 급증 구간의 도약은 보존하는 Heuristic 스마트 보정 함수 도입. |
| **Phase 3 (Tab Generation)** | | |
| **기형적 수직 도약 (String Skipping)** | 무조건 가장 얇은 줄(Lowest Fret)을 우선 선택하는 탐욕(Greedy) 알고리즘의 한계. | 손의 수직 이동 비용(Cost)을 계산하는 동적 계획법(Viterbi HMM) 모델링으로 해결 예정. |
| **과도한 개방현(0) 의존성** | 베이스라인 하행 시 포지션을 유지하지 않고 무조건 개방현으로 점프함. | 프렛 간 수평 이동 거리를 페널티로 부여하는 상태 전이(Transition) 로직으로 해결 예정. |
| **단선율 화음 오류 (False Polyphony)** | 어택 순간의 찰나의 배음 스파이크가 타브에 독립된 노트로 렌더링됨. | 양자화(Quantization) 단계에서 인접한 짧은 노트를 Grouping 하는 전처리 연산으로 해결 예정. |

---

## 5. Future Works (Roadmap)

다음 단계(Phase 3)의 목표입니다.

- [ ] **Smart Fingering (Viterbi HMM):** 현재의 '개방현 우선(Greedy)' 로직을 개선하여, 손의 수직(String) 및 수평(Fret) 이동 거리(Cost Function)를 최소화하는 동적 계획법(DP) 기반 최적 운지 경로 디코딩. 
- [ ] **Note Quantization & Grouping:** 딥러닝 프레임 단위의 연속적인 주파수를 이산적인 MIDI 노트 이벤트로 완벽히 병합하여 비정상적인 폴리포니(False Polyphony) 방지.
- [ ] **MIDI Export:** 정제된 주파수 데이터와 운지 정보를 `.mid` 파일로 변환 (DAW 연동).
- [ ] **Streamlit Demo:** 웹 브라우저에서 바로 파일을 업로드하고 악보를 볼 수 있는 End-to-End 데모 페이지 구축.
- [ ] **Playing Technique Classification:** Slap vs Finger 주법 분류 모델 추가 (Timbre Analysis).
