# 🎸 Automatic Bass Transcription Pipeline (DevLog)

> **Status:**
> Phase 1 Completed (Rule-based Transcription)
> Phase 2 Completed (Deep Learning-based Tracking & Error Correction)
> Phase 3 Completed (Smart Tablature Generation & Optimization)
> Phase 4 Completed (Rhythmic Quantization & Pipeline Modularization)
> Phase 5 Completed (MIDI Export & Streamlit Web UI Integration)
> Phase 6 Completed (DSP Fine-Tuning & Symbolic Post-Processing)
> Phase 7 Completed (Quantizer Fallback Tuning & E2E Stability)
> Phase 8 Completed (DataOps, Baseline Quantification & Architecture Refinement)
> Phase 9 Planned (Source Separation Migration & Standard Notation Export)

## 1. Overview
이 프로젝트는 믹스된 오디오에서 베이스를 분리하고 **연주 가능한 타브 악보(ASCII Tab)**를 생성하는 End-to-End 파이프라인입니다. 

초기(Phase 1)에는 `librosa.pyin`을 사용했으나, 분리된 베이스 음원(Stem)의 낮은 음질과 노이즈로 인해 정확도가 떨어지는 한계가 있었습니다. 현재(Phase 2)는 **SOTA 딥러닝 모델인 CREPE**를 도입하고, 베이스에 특화된 전/후처리(Pre/Post-processing) 로직을 통해 피치 인식률을 비약적으로 향상시켰습니다. 나아가 물리적 연주 가능성(Playability)을 고려한 최적 운지법 추천 모델(Phase 3)을 거쳐, 오디오의 물리적 시간을 음악적 박자(16분음표 격자)로 정렬하는 **리듬 양자화(Phase 4)**를 달성했습니다. 전체 시스템은 유지보수와 확장을 위해 불변 데이터 파이프라인(Immutable Data Pipeline)으로 재설계되었습니다. 최근(Phase 5)에는 추출된 원시 노트 이벤트(NoteEvent) 배열을 활용하여 물리적 타이밍과 운지법이 보존된 **표준 `.mid` (MIDI) 파일 렌더링 로직**을 신설하고, REST API와 연동되는 **Streamlit 기반의 시각화 프론트엔드 웹 데모**를 구축하여 사용자 접근성과 데이터 출력 다각화를 완수했습니다.

최근(Phase 6)에는 피치 트래커(CREPE)와 파서(Parser)의 하이퍼파라미터를 튜닝하여 저음역대 연타 인식률과 슬랩(Slap) 주법의 옥타브 에러를 개선했습니다. 오디오 신호(Signal) 영역에서의 파라미터 튜닝이 수확 체감(Law of Diminishing Returns)에 도달했음을 인지하고, 기호(Symbolic/MIDI) 영역에서의 휴리스틱 후처리 필터를 도입하여 플럭(Pluck) 노이즈를 제압하는 최적의 타협점(Golden State) 파이프라인을 확정했습니다. ([자세한 파라미터 튜닝 실험 일지는 pitch_track_tunning_devlog.md 참조](./pitch_track_tunning_devlog.md))

최근(Phase 6.5 ~ 7)에는 파이프라인의 숨겨진 도메인 결함과 데이터 동기화(Synchronization) 문제를 심층 디버깅하여 해결했습니다. 5현 베이스 대역폭을 커버하기 위해 무리하게 확장했던 주파수 하한선(HPF, fmin)이 CREPE 모델의 훈련 임계치(32.7Hz)를 벗어나 음수 슬라이싱 버그를 유발하고, 초저역대 럼블(Rumble) 노이즈가 온셋 탐지기를 마스킹하여 대규모 노트 증발(Massive Note Omission)을 일으키는 아키텍처 결함을 발견했습니다. 이를 안정적 초기값(Golden State)으로 롤백하여 피치 인식 무결성을 복원했습니다. 또한, OOM 방지용 오디오 청크(Chunk) 분할 과정에서 발생하는 경계 프레임 중복 적재 버그(Time Desync)를 교정하고, 단일 베이스 트랙 입력 시 리듬 양자화기의 BPM 추출이 고주파 노이즈에 의해 오작동하는 엣지 케이스를 방어하여 파이프라인의 E2E 안정성을 달성했습니다. 추가적으로, 가상 악기(VSTi)에서 베이스 연타가 하나의 장음으로 뭉개지는 현상을 해결하기 위해 렌더러에 '단선율(Monophonic) 강제 커팅' 로직을 도입하고, Viterbi HMM 운지법 모델의 수학적 허점(시간 가중치 하한선 누락 등)을 학술적으로 엄밀하게 교정(Refinement)하여 최종 악보의 물리적 타당성을 강화했습니다. 나아가 리듬 양자화기(Rhythmic Quantizer)의 수학적 엄밀성을 재정립하여 음수 지속시간(Negative Duration)으로 인한 시스템 크래시를 원천 차단하고, 3연음(Triplet)과 고속 연타 구간의 다이내믹스를 보존하기 위해 오차 제곱합(SSE) 기반의 동적 격자 평가 및 그리드 기반 병합 로직을 도입하여 양자화 품질과 유연성을 끌어올렸습니다.

최근(Phase 8) 벤치마크 평가를 가동하여, 파이프라인의 순수 DSP 채보 성능 상한선(F1-Score 63.03%)을 객관적으로 측정 및 동결했습니다. 이 과정에서 확인된 다양한 아키텍처 결함(양자화 패널티, 아티팩트 오인, 생체역학 경로 붕괴 등)을 해결하기 위해 'Time-Conditioned Peak 평가', 'Soft Quantization', 'Lazy 튜닝 탐지' 등의 고도화된 수리적 방어 로직을 구현하여 시스템을 리팩토링했습니다. 현재 채보 파이프라인의 구조적 완성도는 극한에 도달했으며, 시스템의 정확도를 제약하는 가장 주요한 성능 병목은 전처리 단계인 음원 분리 모델(Demucs)의 기계적 왜곡(SAR)으로 식별되었습니다.

---

## 2. Core Pipeline Architecture (Current)

현재 파이프라인은 다음 6단계로 고도화되었습니다.

### Step 1: Source Separation
- **Model:** `Demucs (htdemucs)`
- **Optimization:** `--two-stems=bass` 모델이 연산 속도와 실성능(베이스 추출 및 MR 제작 목적) 면에서 프로젝트의 목표에 가장 부합한다고 판단하여 2-Stem 구조로 회귀. 그러나 --two-stems 옵션의 VRAM 연산 착시와 킥 드럼 블리딩(Bleeding) 한계를 극복하기 위해, 기본 4-Stem 모델(htdemucs)을 유지하고 CPU 단에서 나머지 트랙을 합산하는 후처리 방식으로 최종 아키텍처 확정. (자세한 논리는 ADR-001 참조)

### Step 2: Audio Pre-processing (Signal Cleaning)
- **High-pass Filter:** 35Hz 미만의 비음악적 노이즈(DC Offset, Rumble) 제거.
- **Normalization:** 오디오 파형의 최대 진폭을 1.0으로 정규화하여 모델의 입력 감도 확보.
- **Precision Optimization:** `scipy` 필터링 후 팽창된 `float64` 배열을 `float32`로 다운캐스팅하여 VRAM 누수 방지.

### Step 3: Deep Learning Pitch Tracking 
- **Algorithm:** `torchcrepe` (CNN-based Pitch Tracker)
- **Robust Configuration:**
  - **Decoder:** `Argmax` (Viterbi 방식보다 노이즈 환경에서 생존율 높음).
  - **Resolution:** 10ms (Hop Length: 160 @ 16kHz).
  - **Scope:** `fmin=40Hz` ~ `fmax=500Hz`. (5현 베이스 확장을 위해 33Hz를 시도했으나, 딥러닝 모델의 주파수-Bin 변환 공식 한계치 도달 시 발생하는 파이썬 음수 인덱싱(`[:-4]`) 슬라이스 버그로 인해 확률 텐서가 소실되는 부작용이 확인되어 40Hz로 회귀)
  - **VRAM/Speed Optimization:** `tiny` 모델 채택 및 30초 단위 Chunking 처리. 청크 경계 병합 시 이전 청크의 마지막 프레임을 강제 절삭(`[:-1]`)하여 프레임 중복 적재로 인한 타임스탬프 밀림(Time Desync) 현상을 차단함.

### Step 4: Error Correction (Post-processing)
- **Robust Pipeline Ordering:** 무음 구간의 저-신뢰도 노이즈(Garbage Pitch)가 옥타브 대푯값(Median) 연산을 오염시키는 것을 방지하기 위해, 신뢰도 기반 결측치(NaN) 마스킹을 옥타브 보정 필터 가동 이전에 선행하도록 파이프라인 순서를 강제함. 이를 통해 100% 신뢰할 수 있는 순수한 피치 프레임들 사이에서만 화성 평탄화가 이루어짐.
- **Onset-Bounded Segmental Filtering:** 정적 트렌드 오염(Assimilation)을 방지하기 위해, 롤링 미디언을 폐기하고 전체 오디오를 타격점(Onset) 기준으로 독립된 조각(Segment)으로 격리하여 각 조각 내부의 중앙값을 대푯값으로 산출하는 구조로 개편.
- **Smart Octave Correction (Onset-aware):** 의도된 옥타브 도약(Slap 등)은 고유의 Onset을 동반하므로 독립된 조각으로 분리되어 보존되며, 지속음 구간의 도약만 배음 에러로 간주하여 필터링 적용.

### Step 5: Tab Generation & Smart Fingering
- **Note Debouncing (State Machine):** CREPE의 미세 피치 흔들림과 찰나의 결측치(NaN)로 인해 발생하는 비정상적 다중 노트 인식(False Polyphony) 현상을 상태 머신(State Machine) 기반 디바운스 로직으로 병합(Grouping). 최소 유지 시간(`min_duration`)과 결측치 관용도(`tolerance`)를 부여하여 노트를 정규화.
- **Wobble Tolerance Buffer:** 온셋(Onset)이 동반되지 않은 모든 피치 변화는 예외 없이 50ms 지연 버퍼를 거치도록 강제함. 이를 통해 찰나의 배음 간섭으로 인한 롱톤 파편화를 억제하고, 비브라토나 벤딩 시 발생하는 미세 피치 이탈이 숏 노트로 난도질당해 증발(False Negative)하는 현상을 원천 방어.
- **Viterbi HMM Decoder:** 은닉 마르코프 모델(HMM)을 통해 전체 연주의 '생체역학적 이동 비용(Cost)'을 최소화하는 최적 운지 경로 추론. 지판을 벗어나는 가비지 피치 유입 시, 무리하게 개방현으로 매핑하지 않고 시퀀스에서 영구 파기(Drop)하여 HMM 행렬 오염 방지.

### Step 6: Rhythmic Quantization & Pipeline Architecture
- **BPM Tracking & PLP:** 베이스 라인의 잦은 당김음 오판을 방지하기 위해 MR(Bassless) 트랙을 최우선으로 분석함. 믹스 음원이 아닌 단일 베이스 트랙 처리 시, 고주파 온셋 추적기(`fmax=8000`)가 노이즈를 비트로 오인하는 현상을 방지하기 위해 저주파 대역(`fmax=400`) 전용 추적기(Fallback)로 강제 우회시키는 안전장치 적용.
- **Grid Snapping (Soft Quantization):** 기계적인 강제 스냅으로 인한 정답 오차 이탈을 완화하고자 35ms 임계값 기반의 선택적 스냅(Soft Quantization) 도입. 동일 양자화 격자(Grid Index) 내에 배정된 노트들만 리듬 의존적으로 병합하되, 화음(Polyphony) 중첩 시 물리적 지속 시간이 가장 긴 노트를 덮어씌우는 최장음 우선(Longest-Note Priority) 로직 강제화.
- **Immutable Pipeline:** 모듈 간 상태 오염을 방지하기 위해 `NoteEvent` 불변 데이터 클래스(Dataclass, `frozen=True`) 도입. 표현 계층을 분리하여 `Parser` $\rightarrow$ `Fingering` $\rightarrow$ `Quantization` $\rightarrow$ `Renderer` 로 이어지는 단방향 함수형 아키텍처 확립.

### Step 7: MIDI Export & Web Integration
- **Physical-Time MIDI Rendering (`MidiRenderer`):**
  - **정밀한 Offset 동기화 (Unquantized):** 시각용 양자화(Quantization) 로직을 MIDI 추출에서는 완전히 배제. 파서가 디바운싱 프레임으로부터 역산한 정확한 물리적 시간(`time`, `duration`) 데이터를 신뢰하여 기계적 스냅 없이 그루브 보존.
  - **Velocity 매핑:** CREPE 모델의 예측 **신뢰도(`confidence`)**를 MIDI 타건 강도(`velocity`)로 스케일링하여 DAW에서 불확실한 노트 시각적 판별 지원.
- **Asynchronous Web Architecture:**
  - **Backend:** `asyncio.Semaphore(1)`를 통한 GPU 직렬화 및 `BackgroundTasks` 활용. 즉각적인 `HTTP 202 Accepted` 반환 후 비동기 폴링 큐잉 아키텍처 개편.
  - **Frontend:** `st.session_state` 기반 상태 캐싱을 통해 Streamlit 재렌더링 시 발생하는 API 중복 호출 차단. 경로 파편화 방지를 위한 SSOT 디렉토리 맵핑.

### Step 8: DSP Fine-Tuning & Symbolic Culling
- **Confidence-Aware Retriggering:** 피치(Hz) 변화 없이 진폭만 미세하게 흔들리는 베이스 연타를 탐지하기 위해, 예측 신뢰도의 순간 하락(< 0.5)을 타격 지표로 교차 검증하는 상태 머신 고도화.
- **Time-Conditioned Artifact Masking:** 음원 분리 왜곡(Artifact)에 의해 생성된 가짜 타격점을 걸러내기 위해, 타격 직후 40ms 구간에서 `confidence >= 0.4`가 **'연속된 2프레임(최소 10ms 물리적 유지 구간)'** 동안 충족될 때만 실제 타격으로 승인. 산발적인 1프레임 딥러닝 노이즈 스파이크 완벽 차단.
- **Garbage Pitch Culling:** 슬랩 팝(Pop) 타격 찰나의 비화성 마찰음을 가짜 피치로 오인하는 "띠-딩" 현상을 막기 위해, 기호 영역에서 극단적으로 짧고 피치 도약이 큰 패턴을 기계적으로 병합(Merge)하는 후처리 필터 가동.

---

## 3. Result Preview

**Input:** Separated Bass Audio File (.wav)
**Output:** Quantized ASCII Tablature (16th-note Grid, Viterbi Optimized)

```text
🎸 Quantized Bass Tab (BPM: 125)

G |------------------------------------------------|------------------------------------------------|
D |---0-----------------------0-----0--------------|------------------------------------------------|
A |------------------------------------------------|---3--------3--------------3-----3--------------|
E |---------------------------------------------3--|---------3-----4-----3--------------------------|
```

---

## 4. Challenges & Solutions (Troubleshooting)

개발 과정에서 발생한 주요 문제점과 해결 방안입니다. 본 트러블슈팅 테이블은 개발 과정을 보존하기 위해 작성되었습니다. 파이프라인의 특성상 이전 페이즈(Phase)에서 내린 최적화 결정이 시스템 통합(E2E) 후 예기치 않은 부작용을 유발할 수 있으며, 이 경우 후속 페이즈에서 이전의 결정을 롤백(Rollback)하거나 전면 재수정한 이력까지 기록하여 설계 의도의 진화 과정을 기록합니다.

| Issue | Cause | Solution |
| :--- | :--- | :--- |
| **Phase 1 (Rule-based)** | | |
| **옥타브 오인 오류 (Octave Error)** | 배음(Harmonics)을 기본음으로 오인하거나 피치 트래킹이 불안정함. | `fmax`를 500Hz로 제한하고 `frame_length`를 4096으로 확장하여 저음 해상도 확보. |
| **Phase 2 (Deep Learning)** | | |
| **메모리 초과 및 데이터 팽창 (CUDA OOM Error & Float Bloat)** | 긴 오디오 텐서 변환 시 GPU 메모리 한계 초과 및 `float64` 타입 캐스팅으로 인한 메모리 팽창. | 모델 추론부를 **30초 단위 오디오 Chunking 처리**로 분할. 추가로 `float32` 명시적 다운캐스팅 및 `tiny` 파라미터 노출로 VRAM 점유율 최적화. |
| **잘못된 옥타브 도약 보정 (False Positive Octave Jump)** | 기계적 보정 로직이 의도된 연주(Slap & Pop 등)까지 평탄화시켜 버림. | **Onset(어택) 탐지 로직을 결합**하여 에너지 급증 구간의 도약은 보존하는 Heuristic 스마트 보정 함수 도입. |
| **Phase 3 (Fingering & Debouncing)** | | |
| **기형적 수직 도약 (String Skipping)** | 무조건 가장 얇은 줄(Lowest Fret)을 우선 선택하는 탐욕(Greedy) 알고리즘의 한계. | 손의 수평/수직 이동 생체역학적 비용(Cost)을 계산하는 **Viterbi HMM 기반 동적 계획법(DP)** 디코더를 도입하여 전역 최적화 수행. |
| **단선율 화음 오류 (False Polyphony)** | 어택 순간의 찰나의 배음 스파이크나 미세한 피치 흔들림이 타브에 독립된 다중 노트(속주)로 오인 렌더링됨. | **상태 머신(State Machine) 기반 디바운싱(Debouncing)** 로직을 구현하여 최소 유지 시간 미만의 노이즈를 필터링하고 인접한 노트를 하나로 Grouping. |
| **Viterbi 시간 가중치 수학적 허점 (Zero-Cost Anomaly)** | 기존 수식($1/\Delta t$)은 두 음표 사이의 박자가 길어질 경우, 지판의 양극단을 오가는 극단적인 도약조차 페널티가 0으로 수렴하는 논리적 오류가 존재함. | 수식에 **물리적 도약 하한선 상수(`base_time_penalty`)를 추가**하고, 개방현 진입 계수(0.5)의 도메인 휴리스틱 의미를 학술적으로 엄밀히 재정립함. |
| **서스테인 조기 끊김 (Premature Sustain Cutoff)** | 롱톤(Sustain) 연주의 끝자락에서 배음이 무너질 때, 파서가 찰나의 결측치(NaN)를 견디지 못하고 노트를 너무 일찍 종료시켜버림. | 파서의 결측치 관용도(`TOLERANCE_FRAMES`)를 **150ms로 대폭 상향**하여 음표 꼬리가 자연스럽게 소멸할 때까지 관성으로 유지(Bridging)시킴. |
| **Phase 4 (Quantization & Architecture)** | | |
| **당김음 템포 탐지 오류 (Syncopation BPM Error)** | 베이스 특유의 엇박과 당김음으로 인해 표준 Beat Tracking 알고리즘이 템포를 잘못 짚거나 산출에 실패함(0 반환). | Onset Envelope 추출 시 **fmax를 400Hz로 제한** 및 **PLP** 곡선 적용. 억지 BPM 할당(Fallback) 로직을 전면 폐기하고 양자화를 생략하여 원본 타이밍 보존. |
| **가독성 붕괴 및 시간 종속성 (Unquantized Time Dependency)** | 기존 악보는 대시(`-`) 개수가 물리적 시간 비율에 비례하여 마디(Measure) 구분이 불가능하고 가독성이 떨어짐. | 16분음표 단위로 시간을 이산화(Discretization)하는 **유클리드 거리 최소화(Grid Snapping)** 수학 모델 도입. 마디 단위(`\|`) 출력을 지원하는 정량적 렌더러 분리. |
| **데이터 오염 및 강한 결합 (Data Corruption & Tight Coupling)** | 하나의 `Generator` 클래스가 파싱, Viterbi 연산, 양자화를 모두 수행하며 딕셔너리 리스트를 직접 수정(In-place)하여 디버깅 불능 상태 초래. | 객체 상태의 변이를 원천 차단하는 `frozen=True` 기반의 **`NoteEvent` 불변 데이터 클래스(Dataclass)** 설계 및 계층별 모듈화 적용. |
| **양자화 중 데이터 소실 (Data Loss during Quantization)** | 16분음표 격자(Grid Index)를 딕셔너리 키로 사용하여, 같은 격자 내 빠른 패싱 노트 발생 시 선행 노트가 덮어쓰기(Overwrite) 됨. | `RhythmicQuantizer`의 딕셔너리 구조를 폐기하고 **리스트(List) 누적 및 정렬 방식**으로 변경하여 원본 이벤트 데이터 소실 방지. |
| **모듈 네임스페이스 충돌 (Module Namespace Collision)** | 도메인 로직과 무관한 렌더러가 전역 `utils/`에 위치하여 파이썬 파일명(`utils.py`)과 패키지(`utils/`) 간의 모듈 충돌 발생. | 출력 계층을 완전히 격리하는 **`renderers/` 패키지를 신설**하고 `TabRenderer`를 이동시켜 의존성 분리 및 안전한 Import 보장. |
| **파이프라인 단절 및 참조 오류 (Pipeline Disconnection & NameError)** | API에서 호출하는 `src/main.py` 내부의 파이프라인 로직이 불완전하게 구현(주석 처리)되어 실행 시 붕괴됨. | API 컨텍스트와 완전히 격리된 `src/core/pipeline.py`를 신설하여 `CREPE -> Parser -> Viterbi -> Quantizer -> Renderer`로 이어지는 객체 지향적 메서드 체이닝 복원. |
| **신뢰도 데이터 유실 (Confidence Data Loss)** | CREPE 모델이 내부적으로 산출하는 예측 확률(Confidence) 데이터가 도메인 파이프라인으로 전달되지 않고 소실됨. | `tracker.py` 반환값을 `(f0, confidence)` 튜플로 수정하고, 노트 지속 구간의 평균(Mean) 신뢰도를 연산하여 `NoteEvent` 불변 객체에 직접 주입. |
| **격자 내 다중 노트 렌더링 소실 (Grid Collision)** | `TabRenderer`의 2차원 배열 할당 시 같은 격자(grid_idx)에 위치한 짧은 꾸밈음이 여전히 덮어쓰기 됨. | `TabRenderer`에 **충돌 감지 및 병합(Collision & Merge) 로직** 추가. 기존 값이 있을 경우 하이픈(`-`)을 제거하고 새 프렛 번호를 이어 붙여 데이터 소실 방어. |
| **VRAM 동기화 병목 및 속도 저하 (VRAM Sync Bottleneck)** | Chunking 루프 내 매번 `torch.cuda.empty_cache()` 호출로 PyTorch 메모리 할당자가 강제 동기화됨. | 캐시 비우기를 제거하고 `try-except RuntimeError` 기반 **Dynamic Batching** 도입. OOM 발생 시에만 배치 사이즈를 절반으로 줄여 추론 속도 극대화. |
| **기형적 하이 프렛 도약 (Blind Jump)** | 기존 Viterbi 비용 수식이 개방현에서 하이 프렛으로 이동할 때의 난이도를 단순 선형(Linear)으로 계산함. | 이동 프렛이 7프렛을 초과할 경우 지수적(Exponential) 페널티를 부과하는 **비선형 생체역학 수학 모델(`max(0, f2 - 7)**1.5`)**로 수식 교정. |
| **BPM 탐지 실패 시 빈 악보 렌더링 (Empty Tab on Fallback)** | 양자화가 생략되어 `grid_index`가 `None`인 상태로 렌더러에 진입하면 노트가 증발함. | `TabRenderer`에 **시간 비례 기반 가상 격자(Virtual Grid) Fallback 로직** 추가. 1초를 10칸(100ms 단위)으로 강제 매핑하여 ASCII 악보 출력 보장. |
| **음수 지속시간 버그 (Negative Duration Crash)** | 오버랩 절단(Cut) 로직이 앞 노트의 시작점보다 과거로 역전되어 크래시 유발. | 절단 시 최소 지속시간(0.01초)을 반드시 보장하도록 수학적 하한선(Clamp) 수식 적용하여 안전성 완벽 확보. |
| **고속 펑크 연타의 다이내믹 훼손 (Staccato Merging)** | 50ms 이하의 간격(Gap)을 일괄 병합하는 정적 로직으로 인해 16분음표 스타카토 연타가 장음으로 뭉개짐. | 절대 시간 기준을 폐기하고, **동일 피치이면서 같은 양자화 격자(Grid Index)에 스냅된 노트들만 병합**하도록 로직을 격상. |
| **3연음 및 스윙 바운스 각짐 현상 (Triplet Rigidity)** | 16분음표 격자 강제 스냅으로 인해 셔플, 바운스 리듬의 유연한 그루브가 완전히 파괴됨. | 오차 제곱합(SSE Cost) 기반의 **동적 격자 평가(Dynamic Grid Evaluation)**를 통해 비트별로 8분 3연음과 16분음표 중 적합한 해상도를 유동적 선택. |
| **Phase 5 (MIDI Export & Web UI)** | | |
| **서스테인 오류 및 Note-Off 한계 (Sustain Error)** | 파서(Parser)에서 노트의 종료 시간 데이터가 누락되어 MIDI 렌더링 시 다음 노트까지 강제 레가토 처리됨. | 디바운싱 로직에서 물리적 지속 시간(초 단위)을 역산하여 `NoteEvent`에 명시적 주입. MIDI `note_off` 타이밍을 실제 연주와 동기화. |
| **프론트엔드 상태 증발 및 중복 호출 (UI State Loss)** | Streamlit 전체 화면 재렌더링으로 백엔드 API가 중복 호출되거나 작업 상태가 증발함. | **`st.session_state`**를 활용하여 `task_id`와 최종 데이터를 캐싱하고, 비동기 폴링 루프를 상태 기반으로 격리. |
| **경로 파편화로 인한 무한 폴링 (Infinite 404 Polling)** | 백엔드 저장소와 프론트엔드의 폴링 라우터 간 디렉토리 파편화로 타임아웃 발생. | 저장소 경로를 최상단 `outputs/`로 강제 통합(**SSOT 구축**)하여 호출 규약 일치. |
| **오디오 서빙 오류 및 특수문자 충돌 (Audio Serving 404)** | 파일명에 특수문자 포함 시 Demucs가 이를 언더스코어(`_`)로 치환하여 다운로드 URL 불일치 발생. | 프론트엔드에 **정규표현식(`re.sub`)** 헬퍼 로직을 추가하여 Demucs의 디렉토리 생성 규칙을 클라이언트 단에서 동기화. |
| **동일 피치 연타 뭉개짐 (Legato Merge Error)** | 표준 MIDI 규격상 음표가 겹칠 경우 가상 악기가 이를 어택 없는 이음줄로 처리함. | `MidiRenderer`에 **단선율(Monophonic) 강제화 로직** 신설. 오버랩 시 앞 노트 꼬리를 10ms 강제 커팅하여 베이시스트의 물리적 뮤트(Mute) 모사. |
| **Phase 6 & 7 (DSP Tuning, Time-Sync & E2E Stability)** | | |
| **동일 피치 연타 병합 오류 (Same-Pitch Retriggering)** | 피치 변화가 없는 동일음 타현 시 진폭 변화가 미미하여 하나의 긴 음으로 뭉뚱그려 인식됨. | 타현 시 마찰 노이즈로 인해 **예측 신뢰도(Confidence)가 순간 하락(<0.5)**하는 현상을 교차 검증 지표로 활용하여 강제 분할 구현. |
| **슬랩 옥타브 보정기 오작동 (Slap Octave Miscorrection)** | 연타 감지용 고주파 대역(fmin=500) Onset 마스크가 핑거링 찰과음을 슬랩으로 오진함. | 옥타브 보정용 Onset 마스크를 둔감한 **저음역대 기반(fmax=400Hz, delta=0.06)으로 롤백**하여 안정성 확보. |
| **플럭 주법의 2단 튀김 현상 (Pluck Double-Triggering)** | 타격 직후 비화성 배음 붕괴 구간을 AI가 가짜 고음으로 추론하여 "띠-딩" 현상 발생. | 기호 영역에서 **짧은 지속 시간(<60ms)과 극단적 피치 도약(>5반음)을 기계적으로 병합(Merge)**하는 후처리 필터 가동. |
| **피치 트래킹 시간 밀림 현상 (Time Desync)** | 30초 청크 단위 연산 시 경계 프레임이 중복 적재되어 전체 타임스탬프가 밀림. | 마지막 청크를 제외한 모든 결과물의 마지막 프레임을 기계적으로 절삭(`[:-1]`)하여 병합하도록 슬라이싱 교정. |
| **설정 오류로 인한 대규모 노트 증발 (Massive Note Omission)** | 5현 지원을 위해 `fmin`을 33Hz로 하향했으나 모델 한계치 도달로 확률 텐서가 소실되고 온셋 마스킹이 붕괴됨. | `fmin`을 40Hz의 **안정적 초기값(Golden State)**으로 롤백하여 가비지 노이즈 억제 및 어택 병합 현상 완벽 해결. |
| **단일 트랙 템포 추출 실패 (Tempo Fallback Failure)** | 믹스가 아닌 베이스 트랙 입력 시 고주파 온셋 에너지가 높게 측정되어 베이스 전용 BPM 추적(Fallback)이 차단됨. | 단일 트랙 처리 시 `bassless_path`에 명시적으로 `None`을 주입하여 저역대 전용(`fmax=400`) BPM 추적기 강제 가동. |
| **파서 내 가변 상태 부작용 (Mutable State Side Effect)** | 기호 영역 보정 함수가 이벤트 리스트를 In-place로 수정하여 원본 데이터 오염 발생. | 원본 얕은 복사(Shallow Copy) 및 `NoteEvent.update()`를 활용한 객체 교체로 순수 함수(Pure Function) 구조 보장. |
| **Duration Bloating & 쉼표 증발 오류** | 무음 구간(`blank_counter`)을 조기 초기화하여 쉼표가 앞선 음표의 길이로 전부 편입됨. | `blank_counter` 초기화 시점을 판정 이후로 지연시키고 `end_idx` 역산 로직 교정. |
| **신뢰도 컷오프에 의한 대규모 노트 증발** | 신뢰도 기반 컷오프 로직이 서스테인 중 미세하게 하락하는 프레임을 잘라내어 노트를 소멸시킴. | 신뢰도 기반 컷오프 전면 삭제. 데이터 무결성 유지를 위해 Onset Mask와 Viterbi/Quantizer에 하위 처리 위임. |
| **옥타브 보정 필터 무력화 (Assimilation)** | 롤링 미디언 윈도우 사이즈가 짧아(70ms), 에러 점프 발생 시 트렌드 자체가 오염됨. | 윈도우 사이즈를 `31`(약 310ms)로 대폭 확장하여 일시적 에러 점프에 대한 강건성(Robustness) 확보. |
| **옥타브 하강 보정 누락 (Octave Fallback Failure)** | 슬랩 팝 연주 후 기음으로 복귀하는 -2 옥타브 하강(-24 반음) 분기 처리가 누락되어 연산 붕괴. | `-26 <= diff <= -22` 조건을 추가하여 +24 반음을 보상하는 복구 로직 신설. |
| **Phase 8 (Structural Refinement & Baseline)** | | |
| **정적 트렌드 오염 (Static Trend Assimilation)** | `tracker.py`의 롤링 미디언이 에러 구간 장기화 시 오염값으로 동화되어 보정을 포기함. | 타격점(Onset) 기준으로 오디오를 조각(Segment)으로 격리하는 파티션 필터링 도입. |
| **상태 머신의 무관용 분절 (Sustain Fragmentation)** | 파서가 찰나의 피치 흔들림(배음 간섭) 감지 시 즉시 노트를 절단하여 서스테인이 파편화됨. | 50ms 지연 버퍼(`wobble_counter`) 신설. |
| **정량 평가 기준의 도메인 왜곡 (GT Domain Mismatch)** | Slakh 데이터셋 정답지(GT)가 모델 추론값보다 1옥타브 높게 기보되어 정상 추론이 에러로 처리됨. | 평가기(`evaluator.py`) 데이터 로드 단계에서 GT 주파수 배열을 `/ 2.0` 연산하여 물리 주파수와 동기화하는 로직 추가. |
| **Phase 8.1 (Quantization Penalty)** | | |
| **양자화 후 채보 정확도(F1) 하락 가설** | 기계적인 강제 스냅(Hard Snapping)으로 인한 엇박자 정답 이탈, 16분음표 격자 맵핑 충돌 및 과도한 노트 병합이 F1 스코어 하락의 주요인일 것으로 추정됨. | 물리적 평가 시간과 시각적 맵핑 인덱스를 분리(Decoupling)하고, **35ms 임계값 기반의 선택적 스냅(Soft Quantization)** 구현. |
| **고품질 트랙의 F1 스코어 0% 수렴 (Zero-F1 Anomaly)** | 옥타브 보정기가 선행 실행되어, 무음 구간의 가비지 피치(노이즈)가 옥타브 대푯값(Median) 계산을 오염시키는 순서 역전 버그 발견. | 신뢰도 마스킹 연산을 옥타브 보정 로직 이전으로 재배치하여, 순수한 피치 데이터 위에서만 화성 평탄화가 이루어지도록 로직을 교정함. |
| **이기종 피치 간 다성부 중첩 (Polyphony Overlap)** | 양자화 후 피치가 다른 인접 노트들의 간격이 극도로 짧을 때, 서스테인 강제 할당 수식(`max(0.02, min)`)에 의해 뒤 노트의 시작점보다 앞 노트의 종료점이 늦어지는 물리적 침범 현상 발견. | 오버랩 클램핑(Clamp) 수식을 조절하여, 두 노트의 실제 간격(`available_gap`)을 바탕으로 앞 노트의 지속시간을 동적 절단하되 시스템 붕괴를 막기 위한 최소 한계치(10ms)만 보장하도록 수정. |
| **코드 컨벤션 오염 (Dead Code)** | 과거 실험 후 방치된 사용되지 않는 메서드 및 Kwargs가 모듈 내부에 잔존. | `quantization.py`의 `_apply_musical_smoothing` 및 `tracker.py` 호출부의 미사용 파라미터를 일괄 소거하여 유지보수성 확보. |
| **Phase 8.2 (Bugfix & Architectural Compliance)** | | |
| **5-String Bass Infrastructure Expansion** | Drop D 및 5현(Low B) 베이스 입력 시 발생하던 Viterbi HMM 디코더 및 렌더러의 `KeyError` 크래시 발생. | `PitchParser` 튜닝 배열을 `[23, 28, 33, 38, 43]`으로 확장하고, `TabRenderer`의 배열 규격을 5현 표준으로 일괄 상향 동기화함. |
| **Grid-based Merging Enforcer** | `quantization.py` 내 하드코딩된 절대시간(50ms) 병합 로직으로 인해 BPM 150 이상 곡의 16분음표 스타카토 연타 시 뭉개짐(False Legato) 현상 유발. | 기존 절대시간 로직을 전면 폐기하고, ADR-009 규약에 명시된 '동일 양자화 격자(Grid Index)' 기반 조건식으로 교정하여 원천 차단. |
| **Phase 8.3 (Architecture Refinement: Biomechanical Defense & Lazy Detection)** | | |
| **Dynamic Tuning Detection (Lazy Evaluation)** | 전역 하드코딩된 5현 렌더링이 4현 악보의 가독성을 파괴하는 안티패턴 발생. | `PitchParser`가 신뢰도 높은 피치 데이터를 스캔해 E1(MIDI 28) 미만의 타현이 있을 경우에만 5현 매핑을 개방하며, `TabRenderer`는 B현(인덱스 0) 데이터의 실제 존재 여부를 평가(Lazy Evaluation)하여 유동적으로 4/5현 템플릿을 생성하도록 개선. |
| **Viterbi Garbage Pitch Dropping** | 지판 매핑이 불가능한 가비지 피치(에러) 유입 시 강제로 개방현 `(0, 0)`을 할당하여 DP 행렬 오염(Penalty 붕괴) 및 전역 최적해 훼손을 유발함. | 유효 후보군이 없는 이벤트는 Viterbi 디코딩 이전의 이벤트 시퀀스에서 영구 파기(Drop)하여 생체역학 전역 최적해(Global Optimal Path)를 안전하게 보존하도록 로직 교정. |
| **Phase 8.4 (DSP Deep Calibration: False Negative Elimination)** | | |
| **Wobble Buffer Threshold Calibration (1차 시도)** | 장3도(4반음) 이상의 도약을 배음 에러로 의심하여 지연 버퍼에 억류함으로써, 해머링 온 등 유효한 숏 노트가 증발(False Negative)함. | 펜타토닉 스케일 등 베이스의 관용적 연주를 반영하여 예외 임계값을 완전5도(7반음)로 상향 조절하여 수용 범위 확보. |
| **Buffer Routing Enforcement (최종 교정)** | 위 7반음 상향 조치에도 불구하고, 비브라토나 미세 벤딩 시 피치 이탈이 여전히 1프레임 단위로 즉시 절단되어 삭제되는 증발 현상(Vibrato Evaporation) 잔존. | 피치 도약 임계값 예외를 **전면 삭제**. 온셋이 없는 모든 피치 변화를 50ms 지연 버퍼에 무조건 통과시켜 진동은 흡수하고 스케일 이동만 분리하도록 로직을 강제함. |
| **Max-Confidence Artifact Masking (1차 시도)** | 타격 발생 '순간'의 단일 프레임 신뢰도만 검사 시, 슬랩 팝(Pop)의 자연스러운 비화성 마찰음을 노이즈로 오인해 정상 숏 노트가 증발함. | 타격점 직후 40ms 구간의 '최대 신뢰도(Max Confidence)'를 평가(Post-Transient)하도록 교정하여 진짜 타격을 승인함. |
| **Post-Transient Continuity Enforcement (최종 교정)** | 최댓값(Max) 신뢰도를 검사할 경우, 저음역대 물리적 파장 주기를 위반하는 1프레임(10ms)짜리 CNN 노이즈 스파이크까지 타격으로 통과시키는 음향학적 모순 발생. | 산발적인 노이즈 스파이크 허점(Max)에 속지 않도록, `confidence >= 0.4`가 **'연속된 2프레임(최소 10ms 물리적 유지 구간)'**에서 동시 충족될 때만 유효 타격으로 승인하는 시계열 연속성 검사(Temporal Continuity) 적용. |
| **Strict Monophonic Enforcer** | 양자화 격자 병합 시 다른 피치가 동일 격자에 묶일 경우 이를 방치하여 MIDI 출력 단계에서 화음(Polyphony)이 재생되는 아키텍처 붕괴 확인. | 동일 격자 내 피치 충돌 시 원래의 물리적 지속 시간(Duration)이 더 긴 음을 덮어씌우는 최장음 우선(Longest-Note Priority) 로직을 삽입하여 단선율 무결성을 강제함. |

---

## 5. Future Works (Roadmap)

다음 단계의 핵심 마일스톤입니다.

- [x] **Smart Fingering (Viterbi HMM):** 동적 계획법 기반 생체역학적 운지 경로 디코딩. 
- [x] **Note Grouping & Debouncing:** 상태 머신 기반의 디바운싱 및 가짜 폴리포니 방지.
- [x] **Rhythmic Quantization (BPM Sync):** 오차 제곱합(SSE) 동적 평가 기반 유클리드 격자 스냅 및 양자화 패널티 완전 해소.
- [x] **Clean Architecture Integration:** `NoteEvent` 불변 객체 중심의 레이어드 아키텍처 및 API 단방향 맵핑.
- [x] **MIDI Export & Web UI:** 물리적 원시 타이밍(Unquantized) 보존 MIDI 추출 및 비동기 폴링 기반 Streamlit 대시보드 연동.
- [x] **DataOps & Baseline Evaluation:** 130곡 벤치마크 추출 파이프라인 및 도메인 정규화 적용. 파이프라인 순수 채보 성능의 수학적 한계점(Upper Bound: 63.03%) 객관적 측정 완료.
- [ ] **Action 1: Source Separation Migration (SDR Breakthrough):** 벤치마크 분석 결과 파이프라인의 유일한 병목으로 지목된 음원 분리 모델의 왜곡(SAR/SDR 한계)을 타파하기 위해, 대역별 어텐션 기반 베이스 분리 SOTA 모델(`BS-RoFormer`) 인프라 마이그레이션 및 A/B 테스트 진행.
- [ ] **Action 2: Standard Notation Serialization Engine:** 단순히 텍스트를 출력하는 ASCII 타브를 넘어, **MusicXML 또는 GuitarPro 파일(.gp5)** 포맷을 직접 생성하는 렌더러 구축. 이를 위해 양자화 로직 내부에 '가독성을 위한 초단기음 평탄화 휴리스틱(Musical Smoothing)' 선행 적용.
- [ ] **Action 3: Articulation Classification ML:** Slap, Pop, Slide 등의 타현 주법 태깅을 위해, 별도의 전처리 없이 CREPE 내부 임베딩 레이어를 재활용하는 경량 주법 분류기(Transfer Learning) 설계.
- [ ] **Offset Heuristics (Quality):** CREPE 모델의 Offset(음 종료점) 추적 한계를 보완하여 질척이는 음(Sustain)을 깔끔하게 절삭하는 릴리즈(Release) 휴리스틱 로직 고도화.
