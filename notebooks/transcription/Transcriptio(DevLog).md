# 🎸 Automatic Bass Transcription Pipeline (DevLog)

> **Status:** Phase 1 Completed (Rule-based Transcription)

## 1. Overview
이 모듈은 오디오 입력에서 베이스 트랙을 분리하고, 이를 분석하여 **연주 가능한 타브 악보(ASCII Tablature)**로 자동 변환하는 기능을 수행합니다.
단순한 주파수 변환을 넘어, 리듬감(Onset)을 살리고 시각적으로 직관적인 가로형 악보를 생성하는 데 초점을 맞췄습니다.

---

## 2. Technical Pipeline

전체 파이프라인은 다음 4단계로 구성됩니다.

### Step 1: Source Separation (Demucs)
- **Model:** `htdemucs` (Hybrid Transformer)
- **Optimization:** `--two-stems=bass` 옵션을 사용하여 베이스 분리 속도를 2배 향상시킴.
- **Role:** 믹스된 음원(Mix)에서 베이스 기타(Bass Stem)만을 깨끗하게 추출.

### Step 2: Pitch Tracking (pYIN Algorithm)
베이스 기타의 저음역대 특성에 맞춰 `librosa.pyin` 파라미터를 정밀 튜닝했습니다.
- **Parameters:**
  - `fmin=40Hz`, `fmax=400Hz`: 베이스 기타에 맞춘 파라미터 설정
  - `frame_length=4096`: 저음 주파수 해상도(Frequency Resolution) 확보를 위해 윈도우 크기를 2배 확장.
- **Filter:** Median Filter를 적용하여 순간적인 피치 튐 현상(Outliers) 제거.

### Step 3: Onset Detection & Pitch Stabilization
기계적인 샘플링 대신, **'줄을 튕기는 시점'**을 감지하여 악보를 생성합니다.
- **Onset Detection:** 에너지 급상승 구간(Transient)을 감지하여 노트의 시작점 포착.
- **Stabilization Logic:** 줄을 튕기는 직후(Attack)의 불안정한 피치를 무시하고, `onset + 5 frames` 뒤의 **Median Pitch**를 채택하여 정확도 향상.

### Step 4: Fretboard Mapping & Rendering
- **Algorithm:** `Lowest Fret Priority` (개방현 및 저프렛 우선 선택 로직 적용).
- **Visualization:** 수직형 로그(Log)가 아닌 **가로형 텍스트 악보(Horizontal Tab)** 구현.
  - **Rhythmic Spacing:** 음의 길이에 따라 대시(`-`) 간격을 동적으로 조절하여 시각적 박자감 구현.
  - **Wrapping:** 터미널 폭(80자)에 맞춰 자동 줄바꿈 처리.

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
| **Octave Error** | 배음(Harmonics)을 기본음으로 오인하거나 피치 트래킹이 불안정함 | `fmax`를 500Hz로 제한하고 `frame_length`를 4096으로 확장하여 저음 해상도 확보. |
| **Pitch Instability** | 어택(Attack) 순간의 줄 장력 변화로 인한 피치 흔들림 | Onset 감지 후 약 0.05초 뒤의 피치 값들의 중간값(Median)을 취하는 안정화 로직 도입. |
| **Dependency Conflict** | `torchcodec`과 `torchaudio` 버전 간의 호환성 문제 | `subprocess`를 활용한 시스템 레벨(FFmpeg) 설치 및 라이브러리 재설치 자동화 스크립트 작성. |
| **Readability** | 단순 터미널 로그 출력으로 인한 가독성 저하 | 버퍼링(Buffering) 방식을 도입하여 가로형 악보 렌더링 및 자동 줄바꿈 구현. |

---

## 5. Future Works (Roadmap)

다음 단계에서 개선할 사항들입니다.

- [ ] **Viterbi Algorithm:** 최단 경로 탐색을 통한 운지법(Fingering) 최적화 (단순 저프렛 우선 방식 탈피).
- [ ] **Playing Technique Classification:** Slap vs Finger 주법 분류 모델 추가 (Timbre Analysis).
- [ ] **MIDI Export:** 텍스트 악보를 DAW에서 사용 가능한 `.mid` 파일로 변환하는 기능 구현.
