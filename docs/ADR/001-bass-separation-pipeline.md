# [ADR-001] 베이스 음원 분리를 위한 AI 모델 및 파이프라인 선정

* **Status:** Accepted (Supersedes previous decision dated 2026-02-17)
* **Date:** 2026-02-28
* **Related Documents:** [Algorithm_selection_devlog.md](./docs/Algorithm_selection_devlog.md), [Transcription_devlog.md](./docs/Transcription_devlog.md)

## 1. Context (배경)

본 프로젝트는 믹스된 오디오 트랙에서 베이스 라인을 고음질로 추출하고, 베이스가 제거된 연습용 Backing Track(MR)을 생성하는 것을 목표로 한다. 

초기 설계에서는 연산 최적화를 목적으로 2-Stem 모델(`htdemucs_two_stems`)을 채택했으나, 저음역대 주파수 중첩(특히 Kick Drum)으로 인한 블리딩(Bleeding) 현상과 향후 자체 다채널 데이터셋(드럼, 기타, 신스 등)을 활용한 파인튜닝(Fine-tuning) 로드맵을 고려할 때, 기존 결정의 치명적 설계 결함이 발견되었다. 이에 따라 음질, 연산 구조, 학습 확장성을 종합적으로 재검토하여 파이프라인 아키텍처를 전면 수정해야 한다.

## 2. Decision (결정)

우리는 Meta의 **Demucs 기본 4-Stem 모델(`htdemucs`)**을 최종 아키텍처로 채택한다. 

2-Stem 구조를 폐기하며, 베이스 전용 MR(Backing Track) 생성은 4-Stem 추론 완료 후 **CPU 메모리 단에서 나머지 3개 트랙(Drums, Vocals, Other)을 프로그래매틱하게 합산(Summing)하는 방식**으로 구현한다.

## 3. Considered Options (검토된 대안들)

1.  **Demucs 2-Stem (`--two-stems=bass`):** 모델 단에서 Bass와 Other(Noise)로만 분리. (초기 채택안, 현재 폐기)
2.  **Demucs 4-Stem (`htdemucs`) + Numpy Post-processing:** 4개 트랙을 온전히 추론한 후, 후처리로 MR 병합. (최종 채택안)

## 4. Rationale (의사결정 근거)

초기 2-Stem 모델 선정의 근거였던 '연산 최적화'와 '학습 편의성'은 기술적 오해에 기반한 것이었으며, 4-Stem으로 회귀해야 하는 명확한 공학적 이유는 다음과 같다.

### 4.1. 연산 최적화에 대한 시스템 엔지니어링적 착시
* **오류:** `--two-stems=bass` 옵션을 사용하면 2채널 전용 가벼운 신경망이 로드되어 GPU VRAM과 연산량(Compute)이 절약될 것이라 가정했다.
* **팩트:** Demucs의 2-stem 옵션은 내부적으로 무거운 4-stem 모델을 똑같이 로드하여 전체 추론(Inference)을 수행한다. 연산이 끝난 직후 CPU 단에서 베이스를 제외한 나머지 텐서들을 합산($Drums + Vocals + Other$)하여 디스크에 2개의 파일로 저장하는 I/O 스위치에 불과하다. 즉, 딥러닝 추론 최적화 측면에서 얻는 이득은 '0'이다.

### 4.2. 음향학적 분리도 한계 (Kick Drum Bleeding 방어)
* 베이스 트랙 분리 시 가장 큰 방해물은 30Hz ~ 100Hz(Sub-bass) 대역을 완벽하게 공유하는 **킥 드럼(Kick Drum)**이다. 
* **4-Stem의 우위:** 4-Stem 모델은 '드럼'이라는 독립된 클래스의 특징(Transient, Attack)을 명확히 학습했기 때문에, 베이스 신호에서 킥 드럼의 타격음을 수학적으로 날카롭게 빼버릴(Subtract) 수 있다.
* **2-Stem의 결함:** 베이스와 그 외(Noise)로만 강제 분리할 경우, 신경망은 킥 드럼을 보컬이나 기타와 같은 일반 '잡음'으로 뭉뚱그려 인식한다. 이로 인해 분리 경계가 모호해져 베이스 트랙에 킥 드럼 타격음이 섞여 들어오는 블리딩 현상이 급증한다.

### 4.3. 머신러닝 파인튜닝 해상도(Resolution) 보존
* 향후 베이스, 기타, 드럼, 신스를 개별 녹음하여 데이터셋을 구축하고 파인튜닝할 계획이 있다.
* 2-Stem 아키텍처를 유지할 경우, 고음질로 개별 녹음된 드럼, 기타, 신스 데이터를 하나의 'Non-bass' 오디오로 믹스(Mix-down)해서 모델에 주입해야 하며, 이는 데이터 고유의 피처(Feature) 해상도를 스스로 파괴하는 행위다.
* 4-Stem 구조를 유지해야, 직접 녹음한 드럼은 드럼 채널 Loss에, 기타/신스는 Other 채널 Loss에 개별 매핑하여 신경망 가중치를 정밀하게 업데이트할 수 있다.

## 5. Consequences (결과)

* **Positive:**
    * 킥 드럼과 베이스의 간섭을 최소화하여 최고의 음향학적 분리도를 달성했다.
    * 미래의 다채널 커스텀 데이터셋을 활용한 정밀 파인튜닝 잠재력을 100% 보존하는 아키텍처를 확립했다.
* **Negative:**
    * 디스크 I/O 관점에서 4개의 스템 파일을 임시로 저장해야 하므로 미세한 용량 오버헤드가 발생한다.
    * CPU RAM 단에서 3개 트랙을 합산(Numpy Addition)하는 후처리 로직이 추가된다. (단, 해당 연산은 < 0.1초 소요로 전체 Latency에 미치는 영향은 무시할 수 있는 수준이다.)
