# 🎸 Automatic Bass Transcription Pipeline (DevLog)

> **Status:**
> Phase 1 Completed (Rule-based Transcription)
> Phase 2 Completed (Deep Learning-based Tracking & Error Correction)

## 1. Overview
이 프로젝트는 믹스된 오디오에서 베이스를 분리하고 **연주 가능한 타브 악보(ASCII Tab)**를 생성하는 파이프라인입니다. 

초기(Phase 1)에는 librosa.pyin을 사용했으나, 분리된 베이스 음원(Stem)의 낮은 음질과 노이즈로 인해 정확도가 떨어지는 한계가 있었습니다. 현재(Phase 2)는 **SOTA 딥러닝 모델인 CREPE**를 도입하고, 베이스에 특화된 전처리(Pre-processing) 및 후처리(Post-processing) 로직을 통해 인식률을 비약적으로 향상시켰습니다.

---

## 2. Technical Pipeline (Phase 2 Architecture)

현재 파이프라인은 다음 5단계로 고도화되었습니다.

### Step 1: Source Separation
- **Model:** `Demucs (htdemucs)`
- **Optimization:** `--two-stems=bass` 에서 실성능이 더 좋다고 판단된 기본 모델로 변경 --> 실성능이 매우 유사함을 확인 후 프로젝트 목적성(베이스 제거 트랙 생성 등) 맞추어 tow-stem 모델로 회귀
- **Notebook:** `01_Melody_Extraction...`, `02_tracking_separated...`

### Step 2: Audio Pre-processing (Signal Cleaning)
- **High-pass Filter:** 35Hz 미만의 비음악적 노이즈(DC Offset, Rumble) 제거.
- **Normalization:** 오디오 파형의 최대 진폭을 1.0으로 정규화하여 모델의 입력 감도 확보.

### Step 3: Deep Learning Pitch Tracking 
- **Algorithm:** `torchcrepe` (CNN-based Pitch Tracker)
- **Notebook:** `04_tracking_by_CREPE.ipynb`, `06_Main_pitch_track.ipynb`
- **Robust Configuration:**
  - **Decoder:** `Argmax` (Viterbi 방식보다 노이즈 환경에서 생존율 높음).
  - **Resolution:** 10ms (Hop Length: 160 @ 16kHz).
  - **Scope:** `fmin=40Hz` (Low E 근사치) ~ `fmax=500Hz`.
  - **VRAM Optimization (Chunking):** CUDA OOM(Out of Memory) 방지를 위해 오디오를 30초 단위 청크(Chunk)로 분할 처리하고, VRAM 가비지 컬렉션을 명시적으로 수행하여 다중 요청/배포 환경에 대비.

### Step 4: Error Correction (Post-processing)
- **Notebook:** `05_Octave_Error_Correction.ipynb`, `06_Main_pitch_track.ipynb`
- **Pipeline Reordering:** 이동 중앙값(Rolling Median) 연산 오류를 방지하기 위해 결측치(NaN) 마스킹을 수학적 보정(Median, Octave) 이후 가장 마지막 단계로 재배치.
- **Median Filter:** 순간적인 스파이크 노이즈 제거.
- **Smart Octave Correction (Onset-aware):** `librosa.onset`을 활용하여 진폭(에너지) 급증 구간을 추출. 옥타브 도약(±12 Semitone) 발생 시 전후로 어택(Onset)이 존재하면 의도된 연주(Slap 등)로 보존하고, 지속음(Sustain) 구간에서 발생한 도약만 배음 에러로 간주하여 강제 보정.

### Step 5: Tab Generation & Visualization
- **Notebook:** `03_Tab_generator.ipynb`
- **Logic:** `Lowest Fret Priority` + Onset Synchronization.
- **Visualization:** CREPE의 시간축과 동기화된 가로형 ASCII 악보 생성.

---

## 3. Result Preview

**Input:** Mixed Audio File (.wav)
**Output:** ASCII Tablature

```text
🎸 Generated Horizontal Bass Tab
Standard Tuning (G-D-A-E)

G |-------------------|
D |----5----7----7----|
A |-------------------|
E |-0----0----0-----0-|

---

## 4. Challenges & Solutions (Troubleshooting)

개발 과정에서 발생한 주요 문제점과 해결 방안입니다.

| Issue | Cause | Solution |
| :--- | :--- | :--- |
|**Phase 1**| | |
| **Octave Error** | 배음(Harmonics)을 기본음으로 오인하거나 피치 트래킹이 불안정함 | `fmax`를 500Hz로 제한하고 `frame_length`를 4096으로 확장하여 저음 해상도 확보. |
| **Pitch Instability** | 어택(Attack) 순간의 줄 장력 변화로 인한 피치 흔들림 | Onset 감지 후 약 0.05초 뒤의 피치 값들의 중간값(Median)을 취하는 안정화 로직 도입. |
| **Dependency Conflict** | `torchcodec`과 `torchaudio` 버전 간의 호환성 문제 | `subprocess`를 활용한 시스템 레벨(FFmpeg) 설치 및 라이브러리 재설치 자동화 스크립트 작성. |
| **Readability** | 단순 터미널 로그 출력으로 인한 가독성 저하 | 버퍼링(Buffering) 방식을 도입하여 가로형 악보 렌더링 및 자동 줄바꿈 구현. |
|**Phase 2**| | |
| **Low-end Noise** | 피치가 31Hz 부근에서 일직선으로 그려짐 (실제 연주가 아님). | Demucs 분리 과정에서 남은 초저역 노이즈. **35Hz High-pass Filter (`scipy.signal.butter`)** 적용으로 해결. |
| **CUDA OOM Error** | 긴 오디오를 한 번에 텐서로 변환하여 GPU 메모리 한계 초과 | 모델 추론부를 **30초 단위 오디오 Chunking 처리**로 분할하고 Batch Size를 하향 조정. |
| **NaN Propagation** | 신뢰도 기반 Masking(`NaN` 할당)을 너무 일찍 수행함 | Rolling 윈도우 연산이 망가지지 않도록 **마스킹 단계를 스파이크 제거 및 옥타브 보정 이후로 연기(Reordering)**. |
| **False Positive Octave Jump** | 기계적 보정 로직이 의도된 연주(Slap & Pop 등)까지 평탄화시켜 버림 | **Onset(어택) 탐지 로직을 결합**하여 에너지 급증 구간의 도약은 보존하는 Heuristic 스마트 보정 함수 도입. |

---

## 5. Future Works (Roadmap)

다음 단계(Phase 3) 목표입니다.

- [ ] **Smart Fingering (Cost Function):** 현재의 '개방현 우선' 로직을 개선하여, 손의 이동 거리(Cost)를 최소화하는 Viterbi 기반 운지법 추천.
- [ ] **MIDI Export:** 정제된 주파수 데이터를 `.mid` 파일로 변환 (DAW 연동).
- [ ] **Streamlit Demo:** 웹 브라우저에서 바로 파일을 업로드하고 악보를 볼 수 있는 데모 페이지 구축.
- [ ] **Playing Technique Classification:** Slap vs Finger 주법 분류 모델 추가 (Timbre Analysis).
