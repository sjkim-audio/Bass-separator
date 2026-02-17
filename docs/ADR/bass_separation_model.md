# [ADR-001] 베이스 음원 분리를 위한 AI 모델 및 파이프라인 선정

* **Status:** Accepted
* **Date:** 2026-02-17
* **Related Documents:** [Algorithm_selection_devlog.md](../dev_logs/Algorithm_selection_devlog.md) (상세 실험 데이터)

## 1. Context (배경)

본 프로젝트는 일렉트릭 기타와 베이스가 혼합된 오디오 트랙에서 베이스 라인을 고음질로 추출하고, 베이스가 제거된 Backing Track(MR)을 생성하는 것을 목표로 한다.

주파수 대역이 겹치는 악기(Kick Drum, Low Piano 등)와 베이스를 위상 손실 없이 분리해야 하며, 향후 서버 환경에서의 **파일 I/O 효율성**과 **실시간성(Latency)**을 확보해야 한다. 이를 위해 다양한 DSP(신호 처리) 알고리즘과 딥러닝 모델을 비교 검증하여 최적의 기술을 선정해야 한다.

## 2. Decision (결정)

우리는 Meta의 **Demucs (Hybrid Transformer)** 아키텍처를 기반으로 하되, 베이스 분리에 특화된 **`htdemucs_two_stems` (2-Stem) 모델**을 최종 채택한다.

## 3. Considered Options (검토된 대안들)

상세한 실험 과정은 관련 DevLog(Exp 001 ~ 007)에 기록되어 있으며, 주요 대안은 다음과 같았다.

1.  **Frequency Filtering (LPF/HPF):** 주파수 대역 필터링
2.  **NMF (Non-negative Matrix Factorization):** 통계적 패턴 분리
3.  **OpenUnmix (UMX):** Bi-LSTM 기반 딥러닝 모델
4.  **Demucs (Various Stems):** 6-Stem, 4-Stem, 2-Stem 모델 비교

## 4. Rationale (의사결정 근거)

### 4.1. 기존 알고리즘의 한계 (Why not others?)
* **Filtering & NMF:** 250~300Hz 구간에서 기타와 베이스의 주파수가 겹쳐 '블리딩(Bleeding)' 현상이 심각했다. 특히 NMF는 하드 마스킹 적용 시 고주파 노이즈와 음질 왜곡(Artifacts)을 발생시켰다.
* **OpenUnmix:** NMF 대비 타격감은 보존되었으나, 모델이 베이스와 기타 채널을 혼동(Confusion)하는 편향이 있었으며, 후처리를 위한 추가 필터링이 강제되는 구조적 한계가 있었다.

### 4.2. Demucs 2-Stem 모델 선정 이유 (Why 2-Stem?)
실험(Exp 006, 007)을 통해 `htdemucs`의 파생 모델들을 정량적(SDR, SIR, SAR) 및 정성적으로 비교한 결과는 다음과 같다.

1.  **음질 및 노이즈 제어:**
    * 기타 분리에 특화된 **6-Stem 모델**은 기대와 달리 분리되지 못한 배음이 부우웅한 잡음으로 남아, SAR(음질 왜곡 지표)이 9.70dB로 급락했다.
    * 반면 **4-Stem**과 **2-Stem** 모델은 SAR 15.6dB 수준으로 준수한 음질을 보여주었다.

2.  **시스템 효율성 (Architecture Efficiency):**
    * 프로젝트의 최종 산출물은 `Bass Track`과 `Backing Track(MR)` 두 가지다.
    * 4-Stem 모델 사용 시 4개의 트랙을 분리한 후 다시 3개를 합치는(Mix) 연산이 필요하다.
    * **2-Stem 모델**은 처음부터 `Bass`와 `Other`로 분리되어 출력되므로, 불필요한 파일 I/O와 병합 연산을 생략하여 서버 리소스를 최적화할 수 있다.

3.  **파인튜닝 확장성 (Future-proof):**
    * 향후 자체 데이터셋으로 모델을 파인튜닝할 때, 타겟 변수가 2개(Bass vs Rest)로 줄어들면 손실 함수(Loss Function)가 베이스 특징 학습에만 집중할 수 있어 성능 최적화에 유리하다.

## 5. Consequences (결과)

* **Positive:**
    * 서버 내 불필요한 오디오 믹싱 로직을 제거하여 응답 속도를 개선했다.
    * 베이스 영역에 집중된 학습 구조를 통해 향후 파인튜닝 시 더 적은 데이터로도 효율적인 학습이 가능한 기반을 마련했다.
* **Negative:**
    * 베이스 외에 드럼이나 보컬만 따로 추출하고 싶은 요구사항이 발생할 경우, 모델을 교체해야 하는 유연성 저하가 있다. (현재 프로젝트 범위에서는 제외됨)
