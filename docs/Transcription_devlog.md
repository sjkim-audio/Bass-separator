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
- **Optimization:** `--two-stems=bass` 에서 실성능이 더 좋다고 판단된 기본 모델로 변경
- **Notebook:** `01_Melody_Extraction...`, `02_tracking_separated...`

### Step 2: Audio Pre-processing (Signal Cleaning)
- **High-pass Filter:** 35Hz 미만의 비음악적 노이즈(DC Offset, Rumble) 제거.
- **Normalization:** 오디오 파형의 최대 진폭을 1.0으로 정규화하여 모델의 입력 감도 확보.

### Step 3: Deep Learning Pitch Tracking 
- **Algorithm:** `torchcrepe` (CNN-based Pitch Tracker)
- **Notebook:** `04_tracking_by_CREPE.ipynb`
- **Robust Configuration:**
  - **Decoder:** `Argmax` 
  - **Resolution:** 10ms (Hop Length: 160 @ 16kHz).
  - **Scope:** `fmin=40Hz` (Low E 근사치) ~ `fmax=500Hz`.

### Step 4: Error Correction (Post-processing)
- **Notebook:** `05_Octave_Error_Correction.ipynb`
- **Median Filter:** 순간적인 스파이크 노이즈 제거.
- **Octave Correction:** 배음(Harmonics)을 기음으로 착각하여 피치가 12반음(1옥타브) 튀는 현상을 감지하고, 이동 평균(Rolling Median) 트렌드를 기반으로 강제 보정.

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
```

---

## 4. Challenges & Solutions (Troubleshooting)

개발 과정에서 발생한 주요 문제점과 해결 방안입니다.

| Issue | Cause | Solution |
| :--- | :--- | :--- |
| **Octave Error** | 배음(Harmonics)을 기본음으로 오인하거나 피치 트래킹이 불안정함 | `fmax`를 500Hz로 제한하고 `frame_length`를 4096으로 확장하여 저음 해상도 확보. |
| **Pitch Instability** | 어택(Attack) 순간의 줄 장력 변화로 인한 피치 흔들림 | Onset 감지 후 약 0.05초 뒤의 피치 값들의 중간값(Median)을 취하는 안정화 로직 도입. |
| **Dependency Conflict** | `torchcodec`과 `torchaudio` 버전 간의 호환성 문제 | `subprocess`를 활용한 시스템 레벨(FFmpeg) 설치 및 라이브러리 재설치 자동화 스크립트 작성. |
| **Readability** | 단순 터미널 로그 출력으로 인한 가독성 저하 | 버퍼링(Buffering) 방식을 도입하여 가로형 악보 렌더링 및 자동 줄바꿈 구현. |
|**Phase 2 | | |
| **Low-end Noise** | 피치가 31Hz 부근에서 일직선으로 그려짐 (실제 연주가 아님). | Demucs 분리 과정에서 남은 초저역 노이즈. **35Hz High-pass Filter (`scipy.signal.butter`)** 적용으로 해결. |
| **Octave Jump** | 특정 구간에서 음이 갑자기 1옥타브 위(약 2배 주파수)로 튐. | 배음 간섭 문제. **Rolling Median Trend**를 분석하여 ±12 Semitone 차이가 나면 원위치시키는 알고리즘 도입. |

---

## 5. Future Works (Roadmap)

다음 단계(Phase 3) 목표입니다.

- [ ] **MIDI Export:** 정제된 주파수 데이터를 `.mid` 파일로 변환 (DAW 연동).
- [ ] **Smart Fingering (Cost Function):** 현재의 '개방현 우선' 로직을 개선하여, 손의 이동 거리(Cost)를 최소화하는 Viterbi 기반 운지법 추천.
- [ ] **Streamlit Demo:** 웹 브라우저에서 바로 파일을 업로드하고 악보를 볼 수 있는 데모 페이지 구축.
- [ ] **Playing Technique Classification:** Slap vs Finger 주법 분류 모델 추가 (Timbre Analysis).
