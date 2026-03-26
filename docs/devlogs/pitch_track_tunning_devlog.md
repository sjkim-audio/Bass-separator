### 6.2. Parameter Tuning Iterations (Phase 6)

본 섹션은 분리된 베이스 음원(Stem)을 대상으로 한 피치 트래킹 및 파싱 모듈의 하이퍼파라미터 최적화 실험 기록입니다. E2E 파이프라인 정합성을 위해, 정량적 수치 변화에 따른 오디오-MIDI 시각적 대조(Time-alignment) 결과를 기반으로 튜닝을 진행했습니다.

---

#### 🧪 Iteration 1: Baseline Test (`midi_tunning_test.mid`)

**[Parameters]**
* **Tracking Module:**
  * `BASE_CONF_THRESH`: `0.4` (저음역대 포함 전체 적용)
  * `HIGH_FREQ_HZ`: `200.0` / `HIGH_FREQ_CONF_THRESH`: `0.7` (타악기 블리딩 및 배음 에러 방어선)
* **Parsing Module:**
  * `MIN_DURATION_FRAMES`: `5` (50ms 미만 노이즈 필터링)
  * `TOLERANCE_FRAMES`: `5` (50ms 결측치 브릿징)

**[Results]**
1. **Low-end Early Cutoff:** 4번 줄의 낮은 베이스 노트 인식률이 현저히 떨어지며, 실제 연주보다 음이 조기에 끊어짐(Sustain loss).
2. **High-end Stability:** 비교적 높은 음역대의 라인은 빠른 속주에서도 양호한 인식률을 보임.
3. **Transient Artifacts (Double-triggering):** 슬랩의 썸(Thumb) 주법은 피치를 잘 추적하나, 플럭(Pluck) 주법의 강한 타격 구간에서 발생하는 비화성(Inharmonic) 배음이 독립적인 짧은 노트로 튀는 현상 발생.
4. **Slide Fragmentation:** 슬라이드 주법 시 연속적인 주파수(Hz)를 이산적인 MIDI 노트로 변환하는 과정에서, 경유하는 반음들이 짧고 급격한 속주로 쪼개지는 현상 발생.

**[Next Steps (Action Item)]**
* 저음역대 인식률 복구를 위해 주파수 대역별 동적 임계값 도입 (저역대 Threshold 하향).
* 플럭 주법의 타격 노이즈(Pitch Spike)를 평탄화하기 위해 F0 배열에 `Median Filtering` 도입.
* 슬라이드 파편화 방지를 위해 `MIN_DURATION_FRAMES` 상향 조정.

---

#### 🧪 Iteration 2: Aggressive Filtering (`midi_tunning_test2.mid`)

**[Parameters]**
* **Tracking Module (3-Tier Dynamic Threshold & Median Filter):**
  * Low-Freq Gate (`< 80Hz`): `0.25` (4번 줄 조기 끊김 방지)
  * Mid-Freq Gate (`80 ~ 200Hz`): `0.4` (기존 유지)
  * High-Freq Gate (`> 200Hz`): `0.7` (기존 유지)
  * `F0 Median Filter Window`: `5` (플럭 스파이크 강제 평탄화)
* **Parsing Module:**
  * `MIN_DURATION_FRAMES`: `7` (70ms로 상향, 슬라이드 파편화 방지)
  * `TOLERANCE_FRAMES`: `5`

**[Results]**
1. **Noise Reduction:** 1차 실험의 노트 조기 끊김 및 파편화 현상은 유의미하게 감소함.
2. **Recall Drop (True Positive Loss):** 필터링이 과도하게 개입하여 정상적으로 연주된 짧은 노트들까지 전체적으로 증발함.
3. **Onset Smearing (Groove Loss):** 미디언 필터가 베이스의 어택(Attack) 특성을 훼손하여 전체적인 그루브가 무너짐. 하이 노트 솔로 파트에서 음의 시작과 끝 타이밍이 불명확해지는 부작용 발생.

**[Next Steps (Action Item)]**
* 베이스 어택 타이밍을 왜곡하는 F0 미디언 필터 전면 폐기 (1차 실험 베이스라인으로 롤백).
* 유실된 하이 노트 복구를 위해 High-Freq Threshold 하향 조정 (`0.7` -> `0.6`).
* 잃어버린 그루브(짧은 팝 노트) 복구를 위해 `MIN_DURATION_FRAMES` 하향 조정 (`7` -> `6`).

---

#### 🧪 Iteration 3: Groove Recovery (`midi_tunning_test3.mid`)

**[Parameters]**
* **Tracking Module (Dynamic Threshold Only):**
  * Low-Freq Gate (`< 80Hz`): `0.25`
  * Mid-Freq Gate (`80 ~ 200Hz`): `0.4`
  * High-Freq Gate (`> 200Hz`): `0.6` (하향 조정)
  * F0 Median Filter: **제거됨**
* **Parsing Module:**
  * `MIN_DURATION_FRAMES`: `6` (하향 조정)
  * `TOLERANCE_FRAMES`: `5`

**[Results]**
1. **Balance Restored:** 2차 실험에서 발생한 그루브 상실 및 어택 훼손 문제가 대다수 해결되며 밸런스를 찾음.
2. **Same-Pitch Retriggering Failure:** 근음 8비트/16비트 연타(동일 피치 반복) 구간에서 노트를 분할하지 못하고 하나의 긴 음(Legato)으로 뭉뚱그려 인식함. 파서가 주파수 변화에만 의존하여 발생하는 한계로 추정.
3. **Onset Latency:** 하이 노트 솔로 라인에서 원본 파형의 어택(Peak) 지점에 비해 MIDI 노트의 시작점(Onset)이 미세하게 뒤로 밀리는 딜레이 확인.
4. **High-frequency Ghost Notes:** 슬랩 파트에서 타격 잔향으로 인한 산발적인 초고역대 고스트 노트가 발생하여 정상적인 썸(Thumb) 트래킹을 방해함.

**[Next Steps (Action Item)]**
* **Onset-Aware Parsing:** 피치 변화 없이도 노트를 분할할 수 있도록, 트래킹 모듈에서 `librosa.onset.onset_strength`를 추출하여 파서(Parser)의 상태 머신에 강제 트리거(Re-trigger) 신호로 주입.
* **Latency Compensation:** CREPE 모델 윈도우링 특성상 발생하는 고정 지연(Latency)을 해소하기 위해 휴리스틱 기반의 시작점 후보정(예: -15ms) 로직 도입.

---

#### 🧪 Iteration 4: Onset-Aware Parser & Latency Compensation (`midi_tunning_test4.mid`)

**[Parameters]**
* **Tracking Module (Onset Data Injection):**
  * `librosa.onset.onset_detect`: 트래킹 단계에서 베이스 음원의 타격점(Onset) 포락선을 추출하여 `onset_mask`(Boolean 배열) 생성 후 파서로 전달.
* **Parsing Module (State Machine Upgrade):**
  * **Onset-aware Finalize & Restart**: 피치(Hz) 변화가 없더라도 `onset_mask`가 `True`인 프레임을 만나면 즉시 현재 노트를 종료하고 새로운 노트를 시작하는 동일 피치 연타(Retriggering) 강제 분할 알고리즘 신설.
  * `LATENCY_COMP_SEC`: `0.015` (15ms). CREPE 모델의 윈도우링 특성으로 인해 발생하는 고정 지연(Latency)을 해소하기 위해, 모든 추출된 노트의 시작점을 15ms 앞으로 당기는 휴리스틱 보정치 도입.

**[Results]**
1. **Same-Pitch Retriggering Failure:** 파서에 Onset 분할 로직을 도입했음에도 불구하고, 1파트의 근음 연타 구간이 시각적/청각적으로 여전히 쪼개지지 않음. 기본 Onset 탐지 감도(Threshold)가 낮아 저음역대의 부드러운 타격 에너지를 캡처하지 못한 것으로 진단됨.
2. **Latency Overcompensation:** 15ms의 고정 지연 보정이 베이스 어택 특성상 전체적인 노트 시작점이 원본 파형보다 미세하게 더 앞당겨지는(Rushed) 과보정 부작용 발생.

**[Next Steps (Action Item)]**
* **Sensitivity Maximization:** 저음역대 연타의 미세한 에너지 변화를 잡아내기 위해, Onset 탐지기의 감도 파라미터(`delta`)를 대폭 상향(수치 하향 조정)하고 타악기 간섭을 막기 위해 `fmax`를 400Hz로 제한.
* **Latency Adjustment:** 과보정된 타이밍을 교정하기 위해 `LATENCY_COMP_SEC`를 15ms에서 10ms(`0.010`)로 하향 조정.

---

#### 🧪 Iteration 5: Onset Sensitivity Maximization (`midi_tunning_test5.mid`)

**[Parameters]**
* **Tracking Module (Runner):**
  * `librosa.onset.onset_detect`: `delta` 파라미터를 기본값(0.07)에서 `0.03`으로 대폭 하향 조정하여 어택 탐지 감도(Sensitivity)를 한계치까지 극대화. 타악기 간섭을 줄이기 위해 `fmax`는 400Hz로 제한.
* **Parsing Module:**
  * `LATENCY_COMP_SEC`: `0.010` (10ms). 4차 실험의 15ms 과보정 현상을 해결하기 위해 하향 조정.

**[Results]**
1. **Same-Pitch Retriggering Failure (Feature Invariance):** 감도를 극대화했음에도 1파트의 저음역 근음 연타 구간은 분할되지 않음. 부드러운 베이스 연타는 진폭(Amplitude) 포락선만으로는 식별 가능한 물리적 특징점(Transient)이 부족함을 확인.
2. **False Polyphony (Sustain Regression):** Onset 감도가 너무 민감해진 결과, 베이스의 정상적인 서스테인(Sustain) 구간에서 발생하는 길게 유지되어야 할 음표들이 중간에 잘게 부서지는(Fragmentation) 치명적인 현상 발생.

**[Next Steps (Action Item)]**
* **Rollback Onset Sensitivity:** 5차 실험의 과도한 감도를 폐기하고 `delta`를 0.07(기본값)로 롤백하여 서스테인 노트를 보호.
* **Confidence-Aware Retriggering (Test 6):** 진폭(Amplitude) 기반 분할을 포기하고, 모델의 예측 신뢰도(Confidence) 하락을 Feature로 활용. 피치가 유지되더라도 Confidence가 순간적으로 특정 임계값(`0.3`) 이하로 떨어졌다 회복되면 재타현(Retrigger)으로 간주하여 노트를 분할하는 로직 도입.

---

#### 🧪 Iteration 6: Confidence-Aware Retriggering (`midi_tunning_test6.mid`)

**[Parameters]**
* **Tracking Module (Runner Rollback):**
  * `librosa.onset.onset_detect`: 5차 실험의 과도한 감도를 폐기하고 `delta`를 `0.07`(기본값)로 롤백. 서스테인 파편화(False Polyphony) 원천 차단.
* **Parsing Module (Feature Shift):**
  * `RETRIGGER_CONF_THRESH`: `0.3` (신설). 진폭(Amplitude) 대신 모델의 예측 신뢰도(Confidence)를 Feature로 활용. 피치가 유지되더라도 Confidence가 0.3 미만으로 순간 하락하면 베이시스트의 재타현(Retrigger)에 의한 배음 간섭으로 간주하여 노트를 강제 분할함.
  * `LATENCY_COMP_SEC`: `0.010` (10ms 유지).

**[Results]**
1. **Same-Pitch Splitting Success:** 1파트의 저음역 근음 연타 구간이 드디어 박자에 맞게 분할(Retriggering)되기 시작함. 부드러운 연타 분할에는 진폭보다 '신뢰도의 순간적 균열'이 훨씬 유효한 지표임을 증명.
2. **Sustain Truncation Bug:** 파서의 상태 머신 설계 결함 발견. 신뢰도 하락 시 이전 노트를 종료한 후, 대기(Blank) 상태로 가지 않고 곧바로 새 노트를 시작해버려 정상적인 서스테인(Sustain)의 꼬리 부분이 짧게 깎여나가는 부작용 발생.
3. **Slap Octave Jumps:** 코랩 기반의 빠른 테스트 환경(Test Harness)을 구성하는 과정에서, 기존 파이프라인(Phase 2)에 존재하던 `clean_octave_errors_smart` 모듈을 누락하여 슬랩 주법 특유의 강한 배음이 옥타브 점프 에러로 발현됨.

**[Next Steps (Action Item)]**
* **State Machine Bug Fix:** 파서 로직을 수정하여, 신뢰도 하락으로 노트를 종료한 직후에는 `current_note = None`으로 전환해 노이즈 구간 동안 대기하도록 조치 (서스테인 보호).
* **Octave Correction Restoration:** 트래킹 모듈에 스마트 옥타브 보정 함수를 복구하여 슬랩 파트의 옥타브 튐 현상 억제.
* **Threshold Fine-tuning:** 서스테인 꼬리를 더 길게 살리기 위해 `RETRIGGER_CONF_THRESH`를 `0.2`로 하향.

---

#### 🧪 Iteration 7: Sustain Protection & Octave Correction Attempt (`midi_tunning_test7.mid`)

**[Parameters]**
* **Tracking Module:**
  * `clean_octave_errors_smart`: 슬랩 파트의 옥타브 튀김을 방어하기 위해 배음 오인 보정 모듈 복구.
* **Parsing Module (Bug Fix & Strict Threshold):**
  * `RETRIGGER_CONF_THRESH`: `0.2` (서스테인 보호를 위해 0.3에서 하향 조정).
  * **State Machine Transition Fix**: Confidence 하락 조건 충족 시, 기존 노트를 Finalize하고 `current_note = None` 상태로 전환하여 노이즈 구간 대기 (서스테인 꼬리 짤림 방지 목적).

**[Results]**
1. **Retriggering Regression:** 근음 타격 파트가 다시 5차 실험 수준(하나의 긴 Legato)으로 회귀함. 임계값을 0.2로 낮춘 결과, 연타 시 발생하는 미세한 신뢰도 하락(0.2 ~ 0.3 사이의 균열)을 감지하지 못해 동일 피치 분할 기능이 완전히 무력화됨.
2. **Slap Part Degradation & High-Note Spikes:** 옥타브 보정 모듈을 추가했음에도 슬랩 파트의 완성도가 오히려 저하되고 돌발적인 초고역대 노트가 발생함. 6차 실험에서 롤백한 Onset 감도(기본값 0.07)로 인해 옥타브 보정기가 슬랩 타격점(Intentional Attack)을 제대로 인지하지 못하고 오작동한 것으로 진단됨.
3. **Groove & Solo Intact:** 그럼에도 불구하고 16분음표 핑거링 그루브와 12프렛 이상의 하이 노트 솔로 파트의 정확도는 훼손되지 않고 양호하게 유지됨.

**[Next Steps (Action Item)]**
* **Threshold Decoupling:** 서스테인 보호와 연타 분할을 분리해야 함. `RETRIGGER_CONF_THRESH`의 최적점(Sweet Spot, 예: 0.25)을 찾거나, 일정 길이(Duration) 이상 유지된 음에 대해서만 제한적으로 Retriggering을 허용하는 방어 로직 추가 필요.
* **Octave Correction Refinement:** `clean_octave_errors_smart` 내부의 `window_size`와 `onset_tolerance` 파라미터를 슬랩 베이스의 물리적 특성에 맞게 재조정해야 함.

---

#### 🧪 Iteration 8: High-Frequency Spectral Flux (Auto-Chop) Attempt (`midi_tunning_test8.mid`)

**[Parameters]**
* **Tracking Module (Onset Isolation):**
  * `librosa.onset.onset_strength`: 베이스의 뭉툭한 저음에 가려진 어택을 찾기 위해, 분석 대역을 고주파(`fmin=500`, `fmax=8000`)로 제한하여 줄의 마찰 노이즈(Transient)만 캡처하는 Auto-Chop 방식 도입.
  * `clean_octave_errors_smart`: 타격점과 피치 인식 사이의 물리적 지연을 극복하기 위해 `onset_tolerance`를 2(20ms)에서 5(50ms)로 상향.

**[Results]**
1. **Root Note Splitting Failure:** 고주파 마찰음을 추적했음에도 1파트의 부드러운 근음 연타는 분할되지 않음. 물리적 타격 강도가 약해 500Hz 이상 대역의 에너지 변화가 임계값을 넘지 못한 것으로 추정됨.
2. **Pluck Double-Triggering ("띠-딩" 현상):** 슬랩 파트의 플럭(Pluck) 연주 시, 타격 순간의 비화성(Inharmonic) 노이즈가 독립된 피치(가짜 고음)로 인식된 후 진짜 피치로 연결되는 2단 튀김 현상이 발생. 이 가짜 노트들이 썸(Thumb) 라인까지 침범하여 그루브를 방해함.
3. **Random High-Note Spikes:** 슬랩 파트가 아닌 일반 라인에서도 돌발적인 초고음이 튀어나옴.
4. **Missing Notes (Recall Drop):** 서스테인과 뼈대는 정형화되었으나, 전반적으로 인식되지 않고 증발하는 노트의 비율이 증가함.

**[Next Steps (Action Item)]**
* **Architecture Redesign:** 파라미터 튜닝을 중단하고, 피치 트래커(CREPE)가 타격 노이즈(Transient) 구간의 쓰레기 데이터(Garbage Pitch)를 파서로 넘기지 못하도록 **Transient Masking (Muting)** 구조를 도입해야 함.
* **Decoupling Masks:** 옥타브 보정기를 위한 마스크(Broadband)와 연타 분할을 위한 마스크(High-freq)의 역할이 충돌하는 아키텍처 결함 수정 필요.

---

#### 🧪 Iteration 9: Optimal Single-Mask Tuning & Threshold Compromise (`midi_tunning_test9.mid`)

**[Parameters]**
* **Tracking Module:**
  * `fmax=400` / `delta=0.06`: 8차 실험의 고주파 예민 마스크를 폐기하고, 저음역대 기반의 안정적인 타격 탐지로 롤백하되 감도를 미세하게 올림.
  * `clean_octave_errors_smart`: `onset_tolerance`를 `4`(40ms)로 설정하여 슬랩 타격점과 피치 인식 사이의 지연 보정.
  * `mask_low` (저음역 게이트): `confidence < 0.2`로 관용도 최대화.
* **Parsing Module:**
  * `RETRIGGER_CONF_THRESH`: `0.5` (대폭 상향). 신뢰도가 0.5 미만으로 떨어지면 즉시 노트를 분할하도록 설정하여 근음 연타 감지력 극대화.
  * `MIN_DURATION_FRAMES`: `7` (70ms) / `TOLERANCE_FRAMES`: `6.5` (65ms).
  * `LATENCY_COMP_SEC`: `0.005` (5ms).

**[Results]**
1. **Root Note Splitting (80% Success):** `RETRIGGER_CONF_THRESH`를 0.5로 대폭 상향한 결과, 부드러운 근음 연타 시 발생하는 미세한 신뢰도 하락을 성공적으로 포착하여 박자의 80%가량을 정확히 분할해 냄.
2. **General Line Stability & Spike Suppression:** `fmax=400`으로 롤백하여 옥타브 보정기의 오작동(False Slap Detection)을 막아냄. 그 결과 2파트(일반 핑거링 라인)에서 지금까지 중 가장 우수한 추적 성능을 보여주며 돌발적인 초고음 에러가 사라짐.
3. **Slide/Hammer-on Fragmentation (Trade-off):** 임계값을 0.5로 높인 부작용 발현. 고음역 솔로 파트에서 슬라이드나 해머링 온(Hammer-on) 등 주파수가 연속적으로 변하는 구간은 본질적으로 모델 신뢰도가 순간 하락하는데, 파서가 이를 모두 '연타'로 오진하여 노트를 잘게 부숴버림("띠리링" 현상).
4. **Pluck Double-Triggering Persistence:** 슬랩 팝(Pop)과 썸(Thumb) 타격 인식률은 안정화되었으나, 플럭 시 배음 붕괴 구간에서 AI가 뱉어내는 '가짜 피치'로 인한 2단 튀김("띠-딩") 현상은 파라미터 튜닝만으로는 물리적으로 해결 불가함을 최종 확인.

**[Decision & Next Steps]**
* 수차례 전체적인 튜닝을 통해 단일 마스크 구조에서 도달할 수 있는 타협점(Best Compromise)에 도달함.
* 슬라이드 파편화 및 플럭 2단 튀김을 근본적으로 해결하기 위해 **Dual-Masking (역할별 마스크 분리)** 및 **Transient Muting (노이즈 구간 강제 결측 처리)** 아키텍처(Test 10) 도입 결정.

---

#### 🧪 Iteration 10: Dual-Mask Architecture & Transient Muting (`midi_tunning_test10.mid`)

**[Parameters]**
* **Tracking Module (Architecture Redesign):**
  * **Dual Onset Masking:** 역할을 분리한 두 개의 마스크 도입. 옥타브 보정 및 플럭 방어용 둔감한 마스크(`slap_mask`: fmax=400, delta=0.06)와 파서의 연타 분할용 예민한 고주파 마스크(`chop_mask`: fmin=500, fmax=8000, delta=0.04).
  * **Transient Muting:** 플럭 주법의 가짜 피치(Garbage Pitch)를 원천 차단하기 위해, `slap_mask`가 켜진 시점부터 4프레임(40ms) 동안의 `f0` 값을 강제로 결측치(`np.nan`) 처리(블랙아웃 윈도우).
* **Parsing Module:**
  * `MIN_DURATION_FRAMES`: `8` (80ms) / `TOLERANCE_FRAMES`: `7` (70ms) 상향. 슬라이드 파편화 방어 및 Mute 구간 브릿징 목적.

**[Results]**
1. **Latency & Groove Loss (Critical Regression):** 40ms의 강제 Muting 윈도우가 플럭 노이즈뿐만 아니라 일반 핑거링과 고음 솔로 파트의 정상적인 어택(Attack) 구간까지 통째로 삭제함. 이로 인해 파서가 피치를 뒤늦게 인식하여 모든 노트가 실제 연주보다 느리게(Delayed) 출력되며 전체적인 그루브가 박살남.
2. **General Line Degradation:** 9차 실험에서 안정적이었던 2파트(일반 라인) 및 3파트(솔로)의 서스테인이 심하게 불안정해지고, 고음 노트가 빠르게 오작동("띠띵")하거나 뚝뚝 끊어지는 현상 발생.
3. **Slap Part Mixed Results:** Transient Muting 덕분에 플럭의 2단 튀김("띠-딩")은 제압되어 타격 타이밍이 눈에 띄게 개선되었으나, 썸(Thumb) 노트들의 서스테인이 희생됨.
4. **Overall Evaluation:** 플럭 노이즈 하나를 잡기 위해 신호(Signal) 자체를 도려내는 물리적 접근은 정상적인 노트들의 어택을 훼손하는 교각살우(矯角殺牛)임을 확인. 전체 퀄리티가 9차 실험 대비 심각하게 퇴보함.

**[Decision & Next Steps]**
* **Rollback:** 10차 실험의 Dual Masking 및 Transient Muting 아키텍처를 전면 폐기하고, 오디오 처리부(DSP)를 가장 밸런스가 좋았던 9차 실험(Golden State) 코드로 롤백함.
* **Symbolic Culling (Test 11):** 플럭의 2단 튀김 문제는 신호 영역이 아닌, 파싱이 완료된 기호 영역(MIDI Event)에서 포스트 프로세싱(Post-processing) 알고리즘을 통해 패턴화된 쓰레기 노트를 기계적으로 걸러내는 방식으로 우회 해결 예정.

---

#### 🧪 Iteration 11: Rollback to Golden State & Symbolic Post-Processing (`midi_tunning_test11.mid`)

**[Parameters]**
* **Tracking & Parsing Module (Rollback to Test 9):**
  * 10차 실험의 Dual Masking 및 Transient Muting 구조를 전면 폐기하고, 오디오 처리부(DSP) 파라미터를 가장 밸런스가 좋았던 9차 실험의 상태(`fmax=400`, `delta=0.06`, `RETRIGGER_CONF_THRESH=0.5`)로 롤백함.
* **MIDI Post-Processing Module (신설):**
  * **Garbage Pitch Culling (기호 영역 후처리):** 플럭 주법의 "띠-딩" 2단 튀김 문제를 신호(Signal) 영역이 아닌 기호(Symbolic/MIDI) 영역에서 해결하기 위한 휴리스틱 필터 도입.
  * 조건: 현재 노트의 길이가 60ms 이하이고, 다음 노트와의 간격이 40ms 이하이며, 두 노트 간의 피치 차이가 5반음(완전4도) 이상 급변할 경우 -> 앞의 노트를 '가짜 타격 노이즈'로 간주하여 강제 삭제하고, 뒤 노트의 시작점을 앞당겨 어택 타이밍 보존.

**[Results]**
1. **Groove & Latency Recovery:** 10차 실험에서 발생했던 글로벌 지연(Latency) 현상이 사라지고, 9차 실험 수준의 안정적인 일반 핑거링 라인과 솔로 파트 그루브가 복구됨.
2. **Pluck Noise Mitigation:** MIDI 후처리 필터가 슬랩 파트의 기형적인 "띠-딩" 패턴을 기계적으로 잡아내어 단일 노트("딩")로 병합하는 데 성공함. 오디오 신호를 훼손하지 않고도 타격 노이즈를 억제하는 유효한 우회로임을 증명.
3. **Remaining Limitations:** 극단적인 슬라이딩이나 해머링 구간에서의 노트 파편화("띠리링")는 여전히 존재하며, 부드러운 썸(Thumb) 타격의 인식률이 완벽하지 않음.

**[Decision: 파라미터 튜닝 임시 중단 (Freeze)]**
* **수확 체감의 법칙(Law of Diminishing Returns) 도달:** 현재의 오디오 DSP 파이프라인(Phase 6)은 단일 음원에 대해 낼 수 있는 최적의 타협점에 도달했음. 여기서 파라미터를 더 미세 조정하는 것은 특정 데모 음원에 대한 과적합(Overfitting)을 초래함.
* **한계 위임 (Delegation to Downstream):** 현재 남아있는 파편화된 노트와 미세한 타이밍 오차는 Raw MIDI의 본질적인 한계임. 이는 다음 개발 단계인 **리듬 양자화기(Rhythmic Quantizer)**의 그리드 스냅 기능과 **비터비 운지법(Viterbi Fingering)**의 물리적 제약 알고리즘을 통해 교정(Filtering)하는 것이 구조적으로 타당함.
* **결론:** Pitch Tracking 및 Parsing 모듈의 하이퍼파라미터 튜닝을 공식적으로 임시 중단(Freeze)하고, 다음 파이프라인(마디/박자 분석 및 악보화) 개발로 페이즈를 전환함.
