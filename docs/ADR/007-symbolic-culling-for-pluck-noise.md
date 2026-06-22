# [ADR-007] 플럭(Pluck) 노이즈 제거를 위한 기호 영역 후처리(Symbolic Culling) 도입

* **Status:** Accepted
* **Date:** 2026-03-01 (Retroactively Documented for Phase 6)
* **Related Documents:** [pitch_track_tunning_devlog.md](../devlogs/pitch_track_tunning_devlog.md), [Transcription_devlog.md](../devlogs/Transcription_devlog.md)

## 1. Context (배경)

베이스 피치 트래킹 고도화(Phase 6) 과정에서, 연타 탐지 감도를 올리자 강한 플럭(Pluck)이나 슬랩 팝(Pop) 주법 시 치명적인 파싱 오류가 관찰되었다.
* **이슈 현상 (Double-Triggering):** 줄을 강하게 뜯는 순간 발생하는 30~40ms 구간의 비화성(Inharmonic) 마찰 노이즈를 CREPE 모델이 터무니없는 고음(Garbage Pitch)으로 잘못 추론하는 현상.
* **결과:** 실제로는 하나의 음을 연주했음에도, 짧은 고음 노이즈("띠")와 실제 베이스 음("딩")이 분할되어 2개의 독립된 노트로 악보에 기록되는("띠-딩" 현상) 문제가 발생하여 전체 채보의 신뢰도를 크게 떨어뜨렸다.

## 2. Decision (결정)

오디오 신호(Signal) 자체를 변형하여 노이즈를 제거하려던 시도(Transient Muting)를 전면 폐기하고, 피치 트래커의 파라미터는 가장 안정적인 상태(Golden State: `fmax=400Hz`)로 롤백한다. 

대신, 파싱이 완료된 **기호 영역(Symbolic/MIDI Event Domain)에서 패턴화된 쓰레기 노트를 기계적으로 걸러내는 후처리 필터(Post-Processor)**를 도입한다.
* **필터링 조건 (Heuristics):** 1. 현재 노트의 지속 시간(Duration)이 60ms 이하이고,
  2. 다음 노트와의 발생 간격(Gap)이 40ms 이하이며,
  3. 두 노트 간의 피치 차이가 5반음(완전4도) 이상 급변할 경우.
* **병합 로직:** 위 조건을 만족하면 앞의 짧은 노트를 '가짜 타격 노이즈'로 간주하여 리스트에서 삭제하고, 뒤에 오는 실제 노트의 시작점(Onset)을 앞당겨(Pull-back) 삭제된 노이즈 구간만큼 채워 넣음으로써 본래의 타격 그루브(Attack Timing)를 보존한다.

## 3. Considered Options (검토된 대안들)

1. **고주파 스펙트럴 플럭스 (High-Frequency Spectral Flux):** 어택 탐지기를 고주파 대역(`fmin=500`, `fmax=8000`)으로 제한하여 마찰 노이즈를 캡처하려 시도. (결과: 뭉툭한 저음역대 근음의 연타를 놓치는 부작용 발생으로 기각 - Iteration 8)
2. **트랜지언트 뮤팅 (Transient Muting in DSP):** 슬랩 마스크가 켜진 시점부터 40ms 동안의 오디오 분석 결과(`f0`)를 강제로 결측치(`NaN`) 처리하여 가짜 피치 자체를 은폐하는 방식. (결과: 노이즈는 사라졌으나, 일반 핑거링 연주의 정상적인 어택(Attack) 구간까지 통째로 삭제되어 전체 노트가 늦게 찍히는(Delayed) 치명적 레이턴시 유발로 기각 - Iteration 10)
3. **기호 영역 후처리 (Symbolic Culling):** 오디오 신호는 보존하고 추출된 MIDI 이벤트 리스트의 논리적 모순을 찾아 병합하는 방식. (최종 채택안 - Iteration 11)

## 4. Rationale (의사결정 근거)

### 4.1. 신호 무결성(Signal Integrity) 보존
오디오 파형이나 추론된 주파수 텐서 배열에 직접 개입(Muting, Median Filtering)하는 것은 노이즈뿐만 아니라 정상적인 음악적 특징(Transient, Groove)까지 훼손하는 교각살우(矯角殺牛)의 결과를 낳았다. 반면 기호 영역에서의 후처리는 1차적으로 보존된 온셋 타임스탬프 데이터를 안전하게 재조합하므로 파이프라인의 글로벌 레이턴시나 타격감을 훼손하지 않는다.

### 4.2. 패턴의 명확성
플럭 주법 시 발생하는 CREPE 모델의 가짜 피치는 예측 불가능한 랜덤 노이즈가 아니라, "극단적으로 짧고(60ms 이하), 다음 음과 거의 붙어있으며, 음정 도약이 비상식적으로 크다"는 뚜렷한 논리적 패턴을 가지고 있어 단순한 조건문(Rule-based)으로도 충분히 높은 정확도로 필터링이 가능했다.

## 5. Consequences (결과)

* **Positive:**
  * 오디오 신호의 어택을 훼손하지 않으면서 슬랩/플럭 파트의 기형적인 "띠-딩" 더블 트리거링 패턴을 단일 노트("딩")로 성공적으로 병합했다.
  * DSP 튜닝을 동결(Freeze)할 수 있게 되어, 핑거링 연주 시의 전반적인 피치 트래킹 안정성을 이전 단계(Test 9) 수준으로 온전히 복구했다.
* **Negative & Limitations:**
  * 현재 적용된 조건문은 하드코딩된 휴리스틱(Heuristics) 룰이다. 만약 숙련된 연주자가 의도적으로 매우 짧은 고스트 노트를 치고 1옥타브 위를 슬랩으로 강하게 뜯는(String popping) 극단적인 하이엔드 연주를 할 경우, 이 필터는 명연주를 노이즈로 오인하여 삭제할 위험성(False Negative)을 내포하고 있다.
  * **Future Work:** 이 방식은 데이터 기반 해결책이 아닌 엔지니어링적 우회로(Band-aid)이다. 향후 Phase 8에서 멜 스펙트로그램 기반의 주법 분류 1D CNN 모델이 도입되면, 해당 노트가 '노이즈'인지 '의도된 팝(Pop)'인지 데이터 기반으로 분류하여 본 하드코딩 룰을 대체해야 한다.
