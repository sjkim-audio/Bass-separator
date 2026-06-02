# [ADR-010] 다중 도메인 독립 정량 평가 프레임워크(BSSEval, mir_eval) 도입

* **Status:** Accepted
* **Date:** 2026-03-01 (Retroactively Documented for Phase 8)
* **Related Documents:** [pitch_track_tunning_devlog.md](../devlogs/pitch_track_tunning_devlog.md), [Transcription_Algorithm_Roadmap.md](../planning/Transcription_Algorithm_Roadmap.md)

## 1. Context (배경)

Phase 6까지 파이프라인(CREPE 파라미터 튜닝, 파서의 임계값 설정, 옥타브 보정 로직 등)의 최적화 작업은 주로 소수의 데모 음원을 대상으로 한 개발자의 청감(Listening)과 시각적 MIDI 대조 등 정성적(Qualitative) 평가에 의존해 왔다.

하지만 파이프라인이 거대해짐에 따라 다음과 같은 엔지니어링 한계에 봉착했다.
1. **수확 체감과 과적합 (Overfitting):** 특정 주법(예: 플럭 노이즈)을 잡기 위해 파라미터를 수정하면 다른 파트(예: 서스테인)가 훼손되는 현상이 반복되었다. 주관적 튜닝은 이미 수확 체감(Law of Diminishing Returns)에 도달했으며, 특정 데모 음원에만 로직이 맞춰지는 과적합 위험이 컸다.
2. **회귀 테스트(Regression Test) 지표 부재:** 새로운 알고리즘(예: 양자화기)을 도입하거나 모델을 파인튜닝했을 때, 이전 파이프라인 대비 시스템 전체의 정확도가 '얼마나' 상승하거나 하락했는지 객관적인 수치로 증명할 수단이 전무했다.

## 2. Decision (결정)

귀에 의존하는 주관적인 하이퍼파라미터 튜닝을 전면 동결(Freeze)하고, **다중 도메인(오디오 신호 및 기호 채보)의 성능을 객관적 수치로 자동 측정하는 정량 평가 CLI 프레임워크(`run_eval.py`)**를 구축한다.

1. **오디오 소스 분리 (Audio Domain) 평가:** `museval` 라이브러리를 활용하여 원본 스템과 예측 스템 간의 **BSSEval 지표(SDR, SIR, SAR)**를 측정한다. (Demucs 분리 성능 한계 모니터링 목적)
2. **타브 채보 (Symbolic Domain) 평가:** `mir_eval.transcription` 모듈을 도입하여, 정답 데이터(Ground Truth MIDI)와 예측 MIDI 간의 **Onset, Pitch, Offset F1-Score**를 측정한다. (CREPE 트래커 및 양자화기 성능 모니터링 목적)

## 3. Considered Options (검토된 대안들)

1. **지속적인 휴리스틱 튜닝:** 예외 케이스가 발견될 때마다 파서를 수정하고 if-else 로직을 추가하는 방식. 끝이 없는 과적합의 늪에 빠지므로 기각했다.
2. **단일 E2E 지표(End-to-End Metric) 도입:** 입력 음원과 최종 악보의 일치율만을 하나로 묶어 채점하는 방식. 분리 단계에서 망가진 것인지 피치 추적에서 망가진 것인지 병목 원인을 추적할 수 없어 기각했다.
3. **다중 도메인 독립 평가 (BSSEval + mir_eval):** 분리(Audio)와 채보(Symbolic)를 각각의 독립된 학계 표준 지표로 측정하는 2-Track 프레임워크 구축. (최종 채택안)

## 4. Rationale (의사결정 근거)

### 4.1. 회귀 테스트 기반(Safety Net) 확립
알고리즘 고도화나 커스텀 파인튜닝(Fine-Tuning)을 진행하려면 베이스라인(Baseline)이 필수적이다. `Slakh2100`과 같은 검증된 멀티 트랙 데이터셋을 활용해 현재 파이프라인의 초기 F1-Score를 측정해 두면, 이후 코드를 리팩토링할 때마다 기존 성능이 훼손되지 않았음을 수학적으로 보장하는 자동화된 CI(Continuous Integration) 기반을 확보하게 된다.

### 4.2. 모듈별 병목 진단 (Decoupled Evaluation)
베이스 채보가 실패했을 때, 그것이 '킥 드럼의 주파수 간섭(분리 실패)' 때문인지 '초저역대 피치 모델의 한계(추론 실패)' 때문인지 책임 소재를 명확히 해야 한다. 분리와 채보의 평가 지표를 분리함으로써, 다음 개발 스프린트의 리소스를 어느 모듈에 집중할지 명확한 데이터 기반의 의사결정(Data-driven Decision)이 가능해진다.

### 4.3. 학계 표준(SOTA)과의 호환성
`BSSEval`과 `mir_eval`은 음악 정보 검색(MIR) 분야의 국제 표준 평가 라이브러리이다. 이를 채택함으로써, 향후 우리의 파이프라인 성능을 SOTA 논문들의 결과표와 직접 비교(Benchmark)할 수 있는 객관성을 100% 확보할 수 있다.

## 5. Consequences (결과)

* **Positive:**
  * 감각에 의존하던 소모적인 파라미터 튜닝 논쟁을 종식시키고, MLOps 기반의 데이터 중심(Data-driven) 아키텍처로 파이프라인을 진화시켰다.
  * 파이프라인 각 페이즈(Raw 예측 vs 양자화 후 예측) 간의 점수 변화를 측정하여, 양자화기(Quantizer)가 실제 정확도에 미치는 영향을 객관적으로 가시화할 수 있게 되었다.
* **Negative & Limitations:**
  * 정답 데이터셋(Slakh2100 등)과 예측 오디오를 동시에 로드하여 오차를 연산하므로, 평가 스크립트 실행 시 막대한 CPU 연산과 VRAM 오버헤드가 발생한다.
  * **근본적 한계 (Ground Truth Flaw):** 벤치마크에 사용되는 정답 MIDI 파일이 사람이 직접 연주한 미세한 타이밍(Micro-timing)이나 슬랩 등의 주법 특성을 완벽히 담고 있지 않은 '단순 렌더링/퀀타이즈 오디오'일 경우, **우리의 AI 파이프라인이 베이시스트의 실제 연주를 더 정확히 잡아내더라도 오히려 정답과 다르다며 F1-Score가 낮게 측정되는 모순**이 발생할 수 있다. 따라서 이 정량 지표를 맹신해서는 안 되며, 반드시 전문가의 정성 평가(Human Evaluation)와 병행해야 한다.
