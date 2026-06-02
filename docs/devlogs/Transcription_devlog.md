# 🎸 Automatic Bass Transcription Pipeline (DevLog)

> **Status:**
> Phase 1 Completed (Rule-based Transcription)
> Phase 2 Completed (Deep Learning-based Tracking & Error Correction)
> Phase 3 Completed (Smart Tablature Generation & Optimization)
> Phase 4 Completed (Rhythmic Quantization & Pipeline Modularization)
> Phase 5 Completed (MIDI Export & Streamlit Web UI Integration)
> Phase 6 Completed (DSP Fine-Tuning & Symbolic Post-Processing)
> Phase 7 Completed (Quantizer Fallback Tuning & E2E Stability)
> Phase 8 Planned (Baseline F1-Score Quantification & Standard Notation Export)

## 1. Overview
이 프로젝트는 믹스된 오디오에서 베이스를 분리하고 **실제 연주 가능한 타브 악보(ASCII Tab)**를 생성하는 End-to-End 파이프라인입니다. 

초기(Phase 1)에는 `librosa.pyin`을 사용했으나, 분리된 베이스 음원(Stem)의 낮은 음질과 노이즈로 인해 정확도가 떨어지는 한계가 있었습니다. 현재(Phase 2)는 **SOTA 딥러닝 모델인 CREPE**를 도입하고, 베이스에 특화된 전/후처리(Pre/Post-processing) 로직을 통해 피치 인식률을 비약적으로 향상시켰습니다. 나아가 물리적 연주 가능성(Playability)을 고려한 최적 운지법 추천 모델(Phase 3)을 거쳐, 오디오의 물리적 시간을 음악적 박자(16분음표 격자)로 정렬하는 **리듬 양자화(Phase 4)**를 달성했습니다. 전체 시스템은 유지보수와 확장을 위해 불변 데이터 파이프라인(Immutable Data Pipeline)으로 재설계되었습니다. 최근(Phase 5)에는 추출된 원시 노트 이벤트(NoteEvent) 배열을 활용하여 물리적 타이밍과 운지법이 보존된 **표준 `.mid` (MIDI) 파일 렌더링 로직**을 신설하고, REST API와 연동되는 **Streamlit 기반의 시각화 프론트엔드 웹 데모**를 구축하여 사용자 접근성과 데이터 출력 다각화를 완수했습니다.

최근(Phase 6)에는 피치 트래커(CREPE)와 파서(Parser)의 하이퍼파라미터를 튜닝하여 저음역대 연타 인식률과 슬랩(Slap) 주법의 옥타브 에러를 개선했습니다. 오디오 신호(Signal) 영역에서의 파라미터 튜닝이 수확 체감(Law of Diminishing Returns)에 도달했음을 인지하고, 기호(Symbolic/MIDI) 영역에서의 휴리스틱 후처리 필터를 도입하여 플럭(Pluck) 노이즈를 제압하는 최적의 타협점(Golden State) 파이프라인을 확정했습니다. ([자세한 파라미터 튜닝 실험 일지는 pitch_track_tunning_devlog.md 참조](./pitch_track_tunning_devlog.md))

최근(Phase 6.5 ~ 7)에는 파이프라인의 숨겨진 도메인 결함과 데이터 동기화(Synchronization) 문제를 심층 디버깅하여 해결했습니다. 5현 베이스 대역폭을 커버하기 위해 무리하게 확장했던 주파수 하한선(HPF, fmin)이 CREPE 모델의 훈련 임계치(32.7Hz)를 벗어나 음수 슬라이싱 버그를 유발하고, 초저역대 럼블(Rumble) 노이즈가 온셋 탐지기를 마스킹하여 대규모 노트 증발(Massive Note Omission)을 일으키는 아키텍처 결함을 발견했습니다. 이를 안정적 초기값(Golden State)으로 롤백하여 피치 인식 무결성을 복원했습니다. 또한, OOM 방지용 오디오 청크(Chunk) 분할 과정에서 발생하는 경계 프레임 중복 적재 버그(Time Desync)를 교정하고, 단일 베이스 트랙 입력 시 리듬 양자화기의 BPM 추출이 고주파 노이즈에 의해 오작동하는 엣지 케이스를 방어하여 파이프라인의 E2E 안정성을 달성했습니다. 추가적으로, 가상 악기(VSTi)에서 베이스 연타가 하나의 장음으로 뭉개지는 현상을 해결하기 위해 렌더러에 '단선율(Monophonic) 강제 커팅' 로직을 도입하고, Viterbi HMM 운지법 모델의 수학적 허점(시간 가중치 하한선 누락 등)을 학술적으로 엄밀하게 교정(Refinement)하여 최종 악보의 물리적 타당성을 강화했습니다. 나아가 리듬 양자화기(Rhythmic Quantizer)의 수학적 엄밀성을 재정립하여 음수 지속시간(Negative Duration)으로 인한 시스템 크래시를 원천 차단하고, 3연음(Triplet)과 고속 연타 구간의 다이내믹스를 보존하기 위해 오차 제곱합(SSE) 기반의 동적 격자 평가 및 그리드 기반 병합 로직을 도입하여 양자화 품질과 유연성을 끌어올렸습니다.

---

## 2. Technical Pipeline (Phase 2 ~ 5 Architecture)

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
- **Pipeline Reordering:** 이동 중앙값(Rolling Median) 연산 오류를 방지하기 위해 결측치(NaN) 마스킹을 수학적 보정(Median, Octave) 이후 가장 마지막 단계로 재배치.
- **Smart Octave Correction (Onset-aware):** `librosa.onset`을 활용하여 진폭(에너지) 급증 구간을 추출. 옥타브 도약(±12 Semitone) 발생 시 전후로 어택(Onset)이 존재하면 의도된 연주(Slap 등)로 보존하고, 지속음 구간의 도약만 배음 에러로 간주하여 강제 보정.

### Step 5: Tab Generation & Smart Fingering (Phase 3)
- **Note Debouncing (State Machine):** CREPE의 미세 피치 흔들림과 찰나의 결측치(NaN)로 인해 발생하는 비정상적 다중 노트 인식(False Polyphony) 현상을 상태 머신(State Machine) 기반 디바운스 로직으로 병합(Grouping). 최소 유지 시간(`min_duration`)과 결측치 관용도(`tolerance`)를 부여하여 노트를 정규화.
- **Viterbi HMM Decoder:** 기존의 탐욕(Greedy) 기반 1차원 매핑을 은닉 마르코프 모델(HMM)로 대체. 동적 계획법(DP)을 통해 전체 연주의 '생체역학적 이동 비용(Cost)'을 최소화하는 최적 경로를 추론.

### Step 6: Rhythmic Quantization & Pipeline Architecture (Phase 4)
- **BPM Tracking & PLP:** 베이스 라인의 잦은 당김음 오판을 방지하기 위해 MR(Bassless) 트랙을 최우선으로 분석함. 믹스 음원이 아닌 단일 베이스 트랙(Isolated) 처리 시, 고주파 대역 온셋 추적기(`fmax=8000`)가 슬랩 노이즈를 비트로 오인하는 결함을 방어하기 위해 MR 변수에 `None`을 주입, 저주파 대역(`fmax=400`) 전용 추적기(Fallback)로 강제 우회시키는 안전장치 적용.
- **Grid Snapping (Euclidean Distance):** 추정된 BPM을 기반으로 16분음표 길이의 시간 격자(Time Grid, $\Delta t$)를 산출. 각 노트의 물리적 발생 시간($t_i$)을 유클리드 거리가 최소화되는 수식($k_i^* = \text{round}(t_i / \Delta t)$)을 통해 가장 가까운 16분음표 격자에 강제 할당(Quantize). 동일 격자 내 다중 노트 소실 방지를 위해 리스트(List) 기반 누적 아키텍처 적용.
- **Immutable Pipeline (Layered Architecture):** 가변 딕셔너리로 인한 상태 오염과 God Object 안티패턴을 해결하기 위해, `NoteEvent` 불변 데이터 클래스(Dataclass, `frozen=True`)를 도입. 모듈 네임스페이스 충돌을 방지하기 위해 표현 계층(Presentation Layer)을 `renderers/` 패키지로 완전히 분리하여 `Parser` $\rightarrow$ `Fingering` $\rightarrow$ `Quantization` $\rightarrow$ `Renderer` 로 이어지는 단방향 함수형 파이프라인 완성 (`v1.0.0-alpha`).

### Step 7: MIDI Export & Web Integration (Phase 5)
- **Physical-Time MIDI Rendering (`MidiRenderer`):**
  - **정밀한 Offset 동기화 (Unquantized):** 타브 악보 렌더링 시 적용되는 16분음표 격자 양자화(Quantization) 로직을 MIDI 추출에서는 의도적으로 배제함. `PitchParser`가 디바운싱(Debouncing) 프레임으로부터 역산한 정확한 물리적 발생 시간(`time`)과 **지속 시간(`duration`)**을 신뢰하여, 기계적인 스냅(Snap) 없이 실제 연주의 그루브와 종료점(Offset)이 그대로 보존된 `note_off` 이벤트를 기록.
  - **Velocity 매핑:** CREPE 모델이 산출한 피치 예측 **신뢰도(`confidence`)**를 MIDI의 타건 강도(`velocity`, 64~127)로 스케일링하여 맵핑함으로써, 불확실한 노트(고스트 노트, 노이즈)를 DAW에서 시각적/청각적으로 쉽게 필터링할 수 있는 확장성 확보.
- **Asynchronous Web Architecture (FastAPI + Streamlit):**
  - **Backend (Concurrency & Serving):** 무거운 딥러닝 추론으로 인한 단일 노드(Single Node) 서버의 OOM(메모리 초과)을 방지하기 위해, `asyncio.Semaphore(1)`를 통한 GPU 작업 직렬화와 `BackgroundTasks`를 결합함. 클라이언트에게는 즉시 `HTTP 202 Accepted`와 `task_id`를 반환하고, 최종 산출물은 `StaticFiles` 라우터를 통해 정적 서빙(Static Serving)함.
  - **Frontend (Stateful Polling):** Streamlit의 잦은 UI 재렌더링으로 인한 API 중복 호출을 방어하기 위해, `st.session_state`를 활용하여 작업 ID와 상태를 캐싱(Caching)함. 서버 응답을 2초 주기로 비동기 폴링하며, Demucs의 디렉토리 생성 규칙(특수문자 정규화)을 프론트엔드 URL 조합기에 동기화하여 404 Broken Link 에러를 원천 차단함.

### Step 8: DSP Fine-Tuning & Symbolic Culling (Phase 6)
- **Confidence-Aware Retriggering:** 부드러운 동일 피치 연타 시 진폭(Amplitude) 변화가 거의 없는 베이스의 특성을 극복하기 위해, 예측 신뢰도(Confidence)의 미세한 하락(Dip, `< 0.5`)을 타격 지표로 삼아 노트를 강제 분할하는 파서 상태 머신 고도화.
- **Latency & Onset Mask Rollback:** 연타 인식률을 높이기 위한 고주파 예민 마스크(High-freq Flux) 및 강제 신호 삭제(Transient Muting) 시도가 전체 그루브와 어택(Attack)을 훼손함을 증명(ADR 참조). 이에 따라 저주파 기반의 안정적인 마스크(`fmax=400Hz`)로 롤백하고, 5ms의 휴리스틱 지연 보정(`LATENCY_COMP_SEC`)을 적용하여 최적의 타이밍 밸런스 도출.
- **Garbage Pitch Culling (MIDI Post-Processor):** 슬랩의 플럭(Pluck) 주법 시 발생하는 40ms 구간의 비화성 노이즈를 AI가 가짜 고음으로 추론하는 "띠-딩(Double-triggering)" 현상 해결. 오디오 신호를 훼손하지 않고, 추출 완료된 MIDI 이벤트 리스트에서 극단적으로 짧고 피치 도약이 큰 노이즈 패턴을 기계적으로 병합(Merge)하는 기호 영역 후처리 도입.

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

개발 과정에서 발생한 주요 문제점과 해결 방안입니다.

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
| **당김음 템포 탐지 오류 (Syncopation BPM Error)** | 베이스 특유의 엇박과 당김음으로 인해 표준 Beat Tracking 알고리즘이 템포를 잘못 짚거나 산출에 실패함(0 반환). | Onset Envelope 추출 시 **fmax를 400Hz로 제한** 및 **PLP** 곡선 적용. | 베이스 특유의 엇박으로 BPM 탐지 실패 시, 임의의 120 BPM을 강제 주입하면 유클리드 격자 연산이 붕괴되어 전체 데이터가 오염됨. | 억지 BPM 할당(Fallback) 로직을 전면 폐기. 유효한 BPM이 없을 경우 양자화를 완전히 생략하고 **물리적 시간(Unquantized Time) 원본을 다음 파이프라인으로 패스**하도록 데이터 무결성 보존. |
| **가독성 붕괴 및 시간 종속성 (Unquantized Time Dependency)** | 기존 악보는 대시(`-`) 개수가 물리적 시간 비율에 비례하여 마디(Measure) 구분이 불가능하고 가독성이 떨어짐. | 16분음표 단위로 시간을 이산화(Discretization)하는 **유클리드 거리 최소화(Grid Snapping)** 수학 모델 도입. 마디 단위(`\|`) 출력을 지원하는 정량적 렌더러 분리. |
| **데이터 오염 및 강한 결합 (Data Corruption & Tight Coupling)** | 하나의 `Generator` 클래스가 파싱, Viterbi 연산, 양자화를 모두 수행하며 딕셔너리 리스트를 직접 수정(In-place)하여 디버깅 불능 상태 초래. | 객체 상태의 변이를 원천 차단하는 `frozen=True` 기반의 **`NoteEvent` 불변 데이터 클래스(Dataclass)** 설계 및 계층별 모듈화 적용. |
| **양자화 중 데이터 소실 (Data Loss during Quantization)** | 16분음표 격자(Grid Index)를 딕셔너리 키로 사용하여, 같은 격자 내 빠른 패싱 노트 발생 시 선행 노트가 덮어쓰기(Overwrite) 됨. | `RhythmicQuantizer`의 딕셔너리 구조를 폐기하고 **리스트(List) 누적 및 정렬 방식**으로 변경하여 원본 이벤트 데이터 소실 방지. |
| **모듈 네임스페이스 충돌 (Module Namespace Collision)** | 도메인 로직과 무관한 렌더러가 전역 `utils/`에 위치하여 파이썬 파일명(`utils.py`)과 패키지(`utils/`) 간의 모듈 충돌 발생. | 출력 계층을 완전히 격리하는 **`renderers/` 패키지를 신설**하고 `TabRenderer`를 이동시켜 의존성 분리 및 안전한 Import 보장. |
| **파이프라인 단절 및 참조 오류 (Pipeline Disconnection & NameError)** | API에서 호출하는 `src/main.py` 내부의 파이프라인 로직이 불완전하게 구현(주석 처리)되어 실행 시 붕괴됨. | API 컨텍스트와 완전히 격리된 `src/core/pipeline.py`를 신설하여 `CREPE -> Parser -> Viterbi -> Quantizer -> Renderer`로 이어지는 객체 지향적 메서드 체이닝을 완벽히 복원. |
| **신뢰도 데이터 유실 (Confidence Data Loss)** | CREPE 모델이 내부적으로 산출하는 예측 확률(Confidence) 데이터가 도메인 파이프라인으로 전달되지 않고 소실됨. | `tracker.py`의 반환값을 `(f0, confidence)` 튜플로 수정하고, `PitchParser`에서 각 노트 지속 구간의 평균(Mean) 신뢰도를 연산하여 `NoteEvent` 불변 객체에 직접 주입(Inject)함. |
| **격자 내 다중 노트 렌더링 소실 (Grid Collision)** | 딕셔너리 덮어쓰기를 방지하기 위해 이벤트를 리스트로 모았으나, 최종 `TabRenderer`의 2차원 배열(`tab_buffer`) 할당 시 같은 격자(grid_idx)에 위치한 짧은 꾸밈음이 여전히 덮어쓰기 됨. | `TabRenderer`에 **충돌 감지 및 병합(Collision & Merge) 로직** 추가. 기존 값이 있을 경우 하이픈(`-`)을 제거하고 새 프렛 번호를 이어 붙여(예: `57-`) 데이터 소실을 방지하고 가독성을 보장. |
| **VRAM 동기화 병목 및 속도 저하 (VRAM Sync Bottleneck)** | `tracker.py`의 Chunking 루프 내에서 매번 `torch.cuda.empty_cache()`를 호출하여 PyTorch의 메모리 할당자(Allocator)를 강제 동기화시킴. | 루프 내 캐시 비우기를 제거하고, `try-except RuntimeError`를 활용한 **Dynamic Batching** 로직을 도입. 실제 OOM 발생 시에만 배치 사이즈를 절반으로 줄이고 캐시를 비우도록 최적화하여 정상 상태의 추론 속도 극대화. |
| **기형적 하이 프렛 도약 (Blind Jump)** | 기존 Viterbi 비용 수식이 개방현에서 하이 프렛으로 이동할 때의 난이도를 단순 선형(Linear)으로 계산하여 물리적 한계를 반영하지 못함. | 이동 프렛이 7프렛을 초과할 경우 지수적(Exponential) 페널티를 부과하는 **비선형 생체역학 수학 모델(`max(0, f2 - 7)**1.5`)**로 수식 교정. |
| **BPM 탐지 실패 시 빈 악보 렌더링 (Empty Tab on Fallback)** | 양자화가 생략되어 `grid_index`가 `None`인 상태로 렌더러에 진입하면, 노트가 악보에 렌더링되지 않고 증발함. | `TabRenderer`에 **시간 비례 기반 가상 격자(Virtual Grid) Fallback 로직** 추가. 1초를 10칸(100ms 단위)으로 강제 매핑하여 박자가 없는 오디오라도 물리적 간격에 맞춰 ASCII 악보를 출력하도록 방어. |
| **음수 지속시간 버그 (Negative Duration Crash)** | 양자화 격자 스냅 후 두 노트의 간격이 매우 좁을 때, 뒤 노트에 맞춰 앞 노트의 꼬리를 자르는(Overlap Cut) 로직이 앞 노트의 시작점보다 과거로 역전되어 크래시 유발. | 절단 시 최소 지속시간(0.01초)을 반드시 보장하도록 수학적 하한선(Clamp) 수식(`max(onset+0.01, min(...))`)을 적용하여 안전성 완벽 확보. |
| **고속 펑크 연타의 다이내믹 훼손 (Staccato Merging)** | 양자화 전 50ms 이하의 간격(Gap)을 일괄 병합하는 정적 로직으로 인해, 빠른 템포에서 의도적으로 끊어 치는 16분음표 스타카토 연타가 단일 장음(Legato)으로 뭉개짐. | 절대 시간 기준을 폐기하고, **동일 피치이면서 같은 양자화 격자(Grid Index)에 스냅된 노트들만 병합**하도록 로직을 격상하여 템포 의존적 음악성 보존. |
| **3연음 및 스윙 바운스 각짐 현상 (Triplet Rigidity)** | 곡의 모든 박자를 16분음표($N=4$) 격자에 기계적으로 강제 할당(Snap)하여, 셔플이나 재즈 등 바운스가 포함된 곡의 유연한 그루브가 완전히 파괴됨. | 비트별로 온셋 분포를 분석하여, 8분 3연음($N=3$)과 16분음표($N=4$) 중 원본 시간과의 **오차 제곱합(SSE Cost)이 더 적은 해상도를 동적으로 선택(Dynamic Grid Evaluation)**하여 그루브 복원. |
| **Phase 5 (MIDI Export & Web UI)** | | |
| **서스테인 오류 및 Note-Off 한계 (Sustain Error)** | 원본 파서(Parser)에서 노트의 종료 시간(Duration) 데이터를 누락하여, MIDI 렌더링 시 다음 노트가 시작될 때까지 이전 음이 강제로 이어지는(Legato) 부자연스러운 서스테인 발생. | `PitchParser`의 디바운싱 로직에서 프레임 기반의 정확한 **물리적 지속 시간(초 단위)**을 역산하여 불변 객체 `NoteEvent`에 명시적으로 주입. MIDI `note_off` 타이밍을 실제 연주와 동기화. |
| **프론트엔드 상태 증발 및 중복 호출 (UI State Loss)** | 버튼 클릭이나 폴링 대기 중 Streamlit 특유의 전체 화면 재렌더링 현상으로 인해 백엔드 API가 중복 호출되거나 작업 상태가 증발함. | **`st.session_state`**를 활용하여 발급받은 `task_id`와 최종 `result_data`를 캐싱(Caching)하고, 비동기 폴링 루프를 상태 기반으로 격리하여 서버 자원 고갈 방어. |
| **경로 파편화로 인한 무한 폴링 (Infinite 404 Polling)** | 백엔드는 결과물을 `app/outputs/`에 저장하고, 폴링 라우터와 프론트엔드는 프로젝트 루트의 `outputs/`를 바라보는 디렉토리 파편화 발생으로 영구적인 타임아웃 발생. | 저장소 경로를 최상단 `outputs/`로 강제 통합(**SSOT 구축**)하고, 라우터 주소(`/tasks`)와 프론트엔드 호출 규약을 완벽히 일치시킴. |
| **오디오 서빙 오류 및 특수문자 충돌 (Audio Serving 404)** | 업로드된 파일명에 괄호 `()`나 공백 등 특수문자가 포함될 경우, Demucs가 이를 내부적으로 언더스코어(`_`)로 치환하여 저장하면서 프론트엔드의 다운로드 URL과 실제 경로가 불일치함. | 프론트엔드(`app.py`)에 **정규표현식(`re.sub`)** 헬퍼 로직을 추가하여, 클라이언트 단에서 Demucs의 디렉토리 생성 규칙을 똑같이 모방(Mocking)하도록 URL 조합 규약 동기화. |
| **동일 피치 연타 뭉개짐 (Legato Merge Error)** | 앞 노트의 종료점과 뒤 노트의 시작점이 겹칠 경우, 표준 MIDI 규격에 의해 가상 악기(VSTi)가 이를 어택(Attack) 없는 하나의 이음줄(Legato)로 씹어버림. | `MidiRenderer`에 **단선율(Monophonic) 강제화 로직**을 신설. 베이시스트의 물리적 뮤트(Mute) 시간을 모사하여, 오버랩 발생 시 앞 노트의 꼬리를 10ms 강제 커팅(-10ms Note Off)함으로써 타격감을 복원함. |
| **Phase 6 (DSP Tuning & Symbolic Culling)** | | |
| **동일 피치 연타 병합 오류 (Same-Pitch Retriggering)** | 피치(Hz)가 변경될 때는 파서가 새로운 노트로 정상 분할하지만, **동일한 피치가 연속으로 타현될 때**는 전체 진폭(Amplitude) 변화가 미미하여 탐지기가 타격점을 놓치고 하나의 긴 음(Legato)으로 뭉뚱그려 인식함. | 피치 변화에만 의존하던 기존 파서의 노트 분할 조건식에, **동일음 타현 시 발생하는 미세한 마찰 노이즈로 인해 '모델 예측 신뢰도(Confidence)'가 순간 하락(<0.5)하는 현상**을 새로운 교차 검증 지표(Feature)로 추가하여 강제 분할(Retriggering) 구현. |
| **슬랩 옥타브 보정기 오작동 (Slap Octave Miscorrection)** | 연타 감지를 위해 Onset 탐지기를 고주파 대역(fmin=500)으로 예민하게 튜닝하자, 일반적인 핑거링 찰과음을 슬랩 타격으로 오진하여 배음 에러를 무사통과시킴. | 단일 마스크 구조의 한계를 인정하고, 옥타브 보정용 Onset 마스크를 둔감한 **저음역대 기반(fmax=400Hz, delta=0.06)으로 롤백**하여 안정성(Golden State) 우선 확보. |
| **플럭 주법의 2단 튀김 현상 (Pluck Double-Triggering)** | 플럭(Pluck) 타격 직후 30~40ms의 배음 붕괴 구간에서 CREPE 모델이 터무니없는 고음(Garbage Pitch)을 뱉어내어 2개의 독립된 노트로 파싱됨. | 신호 결측(Muting) 방식이 정상 어택까지 훼손하는 부작용을 확인한 후, 파싱이 완료된 기호 영역에서 **짧은 지속 시간(<60ms)과 극단적 피치 도약(>5반음)을 감지해 강제 삭제/병합하는 MIDI Post-Processor** 도입. |
| **Phase 6~7 (Time-Sync & Domain Calibration)** | | |
| **피치 트래킹 시간 밀림 현상 (Time Desync)** | CREPE 모델의 VRAM 보호를 위해 오디오를 30초 청크 단위로 나누어 연산할 때, 각 청크 경계선에 위치한 프레임이 중복 적재되며 전체 타임스탬프가 점진적으로 밀리는(Desync) 현상. | 마지막 청크를 제외한 모든 청크 결과물의 마지막 프레임을 기계적으로 절삭(`[:-1]`)하여 병합하도록 슬라이싱 로직 교정. |
| **설정 오류로 인한 대규모 노트 증발 (Massive Note Omission)** | 5현 베이스(B0=30.8Hz) 지원을 위해 HPF를 25Hz, `fmin`을 33Hz로 하향했으나, 모델 최저 학습 한계점(C1=32.7Hz) 이하의 음수 인덱스 슬라이싱 버그가 확률 텐서를 날려버리고 초저주파 럼블이 온셋을 마스킹함. | HPF 컷오프를 35Hz, `fmin`을 40Hz의 **안정적 초기값(Golden State)**으로 롤백. 가비지 노이즈로 인한 예측 신뢰도 하락과 파서의 어택 병합(노트 증발) 현상 완벽 해결. |
| **단일 트랙 템포 추출 실패 (Tempo Fallback Failure)** | 믹스가 아닌 단일 베이스 트랙(Isolated) 입력 시, 템포 추출을 위한 `bassless_path` 변수에 베이스 소스가 그대로 주입되면서 고주파 온셋 에너지가 높게 측정되어 베이스 전용 BPM 추적(Fallback)이 차단됨. | 단일 트랙 처리 시 `bassless_path`에 명시적으로 `None`을 주입하도록 파이프라인 컨트롤러를 수정하여, 저역대 전용(`fmax=400`) BPM 추적기가 정상 가동되도록 강제함. |
| **파서 내 가변 상태 부작용 (Mutable State Side Effect)** | 파서의 기호 영역 보정 함수(`_post_process_garbage_pitch`)가 입력받은 이벤트 리스트를 In-place로 수정하여, Call-by-Assignment 특성에 의한 원본 데이터 오염 발생. | 원본 리스트를 얕은 복사(Shallow Copy)하고 `NoteEvent.update()` 메서드를 활용하여 객체를 교체(Immutable Replacement)하는 방식으로 순수 함수(Pure Function) 구조 보장. |
| **Duration Bloating & 쉼표 증발 오류** | `PitchParser`에서 무음 구간(`blank_counter`)을 이전 노트를 닫기 전에 초기화하여, 쉼표가 전부 앞선 음표의 길이(Duration)로 편입되어버림. | 1) `blank_counter = 0` 초기화 시점을 노트 Finalize 판정 이후로 지연시킴. 2) 노트 종료 시 `end_idx = i - blank_counter` 로 정확한 물리적 오프셋을 역산하도록 식 교정. |
| **신뢰도 컷오프에 의한 대규모 노트 증발 (Massive Note Omission)** | 동일 피치 연타를 잡기 위해 도입한 `RETRIGGER_CONF_THRESH` 로직이, 서스테인 중 신뢰도가 미세하게 하락하는 프레임을 계속해서 잘라내어 노트를 소멸시킴. | 신뢰도 기반 강제 컷오프 로직 전면 삭제. 억지 분절을 포기하고 Onset Mask의 정상 탐지 능력과 Viterbi/Quantizer의 하위 처리에 맡겨 데이터 무결성을 회복함. |
| **옥타브 보정 필터 무력화 (Assimilation)** | 옥타브 트렌드를 구하는 롤링 미디언 윈도우 사이즈가 `7`(70ms)로 너무 짧아, 40ms 짜리 에러 점프만 발생해도 트렌드 자체가 에러값으로 동화됨. | `clean_octave_errors_smart`의 `window_size`를 `31`(약 310ms)로 대폭 확장하여, 일시적인 에러 점프가 트렌드를 오염시키지 못하도록 강건성(Robustness) 확보. |
---

## 5. Future Works (Roadmap)

다음 단계의 목표입니다.

- [x] **Smart Fingering (Viterbi HMM):** 개방현 우선(Greedy) 로직을 개선하여, 손의 수직(String) 및 수평(Fret) 이동 거리(Cost)를 최소화하는 동적 계획법 기반 운지 경로 디코딩. 
- [x] **Note Grouping & Debouncing:** 딥러닝 프레임 단위의 연속적인 주파수를 이산적인 단일 MIDI 노트 이벤트로 병합하여 비정상적인 폴리포니 방지.
- [x] **Rhythmic Quantization (BPM Sync):** 오디오의 BPM을 추정하고 정량적인 16분음표 격자(Grid) 단위로 노트의 시작점을 스냅(Snap)하는 양자화 모델 개발 및 모듈화.
- [x] **Clean Architecture Integration:** FastAPI 백엔드와 코어 파이프라인(`src/core/pipeline.py`)을 완벽히 격리하고 비동기 폴링을 위한 JSON DTO 응답 규격 정립.
- [x] **MIDI Export (Phase 5):** 추출된 이벤트 데이터를 순회하며 물리적 타이밍(Delta Time)과 운지법이 보존된 표준 `.mid` 파일 추출 로직(`MidiRenderer`) 구현 완료.
- [x] **Streamlit / Web UI Dashboard:** 클라이언트가 `202 Accepted` 응답 후 `task_id`를 기반으로 비동기 폴링하여 최종 타브 악보, 음원 렌더링 및 MIDI를 다운로드할 수 있는 MVP 프론트엔드 구축 완료.
- [x] **Model Fine-Tuning (Phase 6):** 파라미터 튜닝 한계 도달 인지 및 DSP 튜닝 동결. 기호 영역(Symbolic) 후처리 필터로 치명적 예측 에러 방어 완료.
- [x] **Residual Noise Filtering via Downstream (Phase 7):** 단일 트랙에 대한 양자화기(Rhythmic Quantizer) Fallback 로직 보완 및 CREPE 청크 분할 시 발생하는 Time-Desync 버그 완벽 교정.
- [ ] **Action 1: Baseline F1-Score Quantification:** 정답 MIDI(Ground Truth)를 갖춘 테스트 벤치마크 데이터셋을 구축하여 `src/evaluation.py` 가동. 양자화 전후(Raw vs Quantized)의 **Onset/Pitch F1-Score 초기 기준값**을 측정하고 정량적 성능 지표로 삼음.
- [ ] **Action 2: Standard Notation Serialization Engine:** 단순히 텍스트를 출력하는 ASCII 타브를 넘어, **MusicXML 또는 GuitarPro 파일(.gp5)** 포맷을 직접 생성하는 렌더러 구축. 이를 위해 양자화 로직 내부에 '가독성을 위한 초단기음 평탄화 휴리스틱(Musical Smoothing)' 선행 적용.
- [ ] **Action 3: Articulation Classification ML:** Slap, Pop, Slide 등의 타현 주법 태깅을 위해, 별도의 전처리 없이 CREPE 내부 임베딩 레이어를 재활용하는 경량 주법 분류기(Transfer Learning) 설계.
- [ ] **Offset Heuristics (Quality):** CREPE 모델의 Offset(음 종료점) 추적 한계를 보완하여 질척이는 음(Sustain)을 깔끔하게 절삭하는 릴리즈(Release) 휴리스틱 로직 고도화.
