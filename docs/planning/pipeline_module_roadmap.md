# [Docs/Planning] 베이스 채보 파이프라인 모듈별 고도화 및 교체 검증 계획

---

## 1. 개요 및 기본 원칙

본 문서는 현재 구축된 베이스 채보 파이프라인(`Demucs` $\rightarrow$ `Tracker` $\rightarrow$ `Parser` $\rightarrow$ `Viterbi` $\rightarrow$ `Quantizer`)의 주요 모듈을 안전하게 검증하고 점진적으로 고도화하기 위한 실행 로드맵입니다.

### 핵심 설계 원칙
1. **아키텍처 격리성 유지:** 파이프라인의 핵심 도메인 객체인 불변 데이터 클래스(`NoteEvent`)와 후처리 엔진(파서, Viterbi 운지법, 리듬 양자화기)의 직접적인 수정을 지양하고 격리 상태를 유지합니다.
2. **어댑터 패턴(Adapter Pattern) 적용:** 신규 모듈은 기존 입출력 규격(`f0: np.ndarray`, `confidence: np.ndarray`, `onset_mask: np.ndarray`)에 맞춘 단일 래퍼(Wrapper) 스크립트로 구현하여 1:1 교체가 가능하도록 구성합니다.
3. **격리 검증(Isolated-first Evaluation):** 교체 모듈의 성능은 믹스 음원이 아닌 정답 오디오(`bass_gt.wav`) 기반의 Isolated 모드에서 우선 검증한 후 E2E 환경에 투입합니다.

---

## 2. 대안 모듈 후보 검토 및 베이스 적합성 분석

### A. 피치 트래커 (Pitch Tracker) 영역

현재 `CREPE`의 한계인 단일 지속음 내 배음 널뛰기(Harmonic Hopping) 현상을 완화하기 위한 후보군 분석입니다.

| 모듈명 | 분석 기법 / 아키텍처 | 베이스 음향 특성 적합성 | 예상 장점 | 주요 검토 사항 및 리스크 |
| :--- | :--- | :--- | :--- | :--- |
| **Basic Pitch** *(Spotify)* | HCQT (Harmonic CQT) 기반 Neural Net | **높음** (배음 구조 모델링) | 기음과 배음열을 함께 인지하므로 옥타브 도약 억제에 효과적일 것으로 기대됨. | 피치 빈 행렬을 반환하므로 프레임별 대표 Hz 및 Confidence 추출 래퍼 로직 구현 필요. |
| **RMVPE** | Deep ResNet + U-Net (360 Pitch Bins) | **보통 ~ 높음** (노이즈 저항성) | 백킹 트랙 및 믹스 노이즈 환경에서 기음 추론의 강건성 우수. | 보컬 특화 학습 모델이므로 40Hz 이하(Low-E, Low-B) 저역대 응답성 사전 확인 필요. |
| **FCPE** | Context-aware PyTorch Model | **보통** (맥락 반영 및 속도) | 프레임 전후 맥락을 고려하여 미세 피치 흔들림 완화, 추론 속도가 양호함. | 배음 구조 억제력에 대해서는 Basic Pitch 대비 다각도 검증 필요. |

* **베이스 적합성 의견:** 베이스 기타는 1차 기음보다 2~3차 배음의 에너지가 우세하게 나타나는 음향학적 특성을 가집니다. 배음열 구조를 묶어서 인지하는 **`Basic Pitch (HCQT)`를 1순위 검증 대상**으로 설정하고, 노이즈 저항성이 우수한 **`RMVPE`를 2순위 대안**으로 검토합니다.

---

### B. 음원 분리 (Source Separation) 영역

`Demucs (htdemucs)`가 가진 40~80Hz 대역 킥 드럼 잔향(Bleed)으로 인한 피치 평탄화 현상을 개선하기 위한 후보군 분석입니다.

| 모듈명 | 핵심 기술 | 베이스 음향 특성 적합성 | 예상 장점 | 주요 검토 사항 및 리스크 |
| :--- | :--- | :--- | :--- | :--- |
| **BS-RoFormer** | Band-Split RoPE Transformer | **높음** (대역별 분할 처리) | 40~80Hz 대역의 킥 드럼과 베이스의 미세한 위상 차이를 대역별 어텐션으로 선명하게 분리. | Demucs 대비 VRAM 점유율이 높고 추론 연산 시간이 다소 증가할 수 있음. |
| **Mel-RoFormer** | Mel-scale Band-Split Transformer | **보통** | 전반적인 음원 분리 품질이 우수하며 스펙트럼 보존율 양호. | 초저역대 선명도 측면에서 BS-RoFormer와의 정량적 비교 필요. |

* **베이스 적합성 의견:** E2E 테스트에서 관찰된 성능 하락 요인 중 하나는 킥 드럼의 초저역대 공진이 베이스 스템에 남아 피치 트래커를 교란하는 현상입니다. **주파수 대역을 분할하여 처리하는 `BS-RoFormer`가 저음역대 분리에 유의미할 것으로 예상**됩니다.

---

### C. 온셋 탐지 (Onset Detection) 영역

`librosa.onset`의 저음역대 둔감 및 슬랩/플럭 주법 어택 놓침 현상을 보완하기 위한 후보군 분석입니다.

| 모듈명 | 핵심 기술 | 베이스 음향 특성 적합성 | 예상 장점 | 주요 검토 사항 및 리스크 |
| :--- | :--- | :--- | :--- | :--- |
| **madmom** | RNN / CNN Onset Processor | **높음** (학습된 딥러닝 디텍터) | 수치 계산 방식 대비 실제 베이스 타현(Pluck, Slap) 어택 인지율이 높음. | 최신 Python 환경(3.11+)에서의 의존성 패키지 빌드 충돌 여부 사전 점검 필요. |
| **BeatNet** | CRNN + Particle Filtering | **보통 ~ 높음** (비트/마디 인지) | 온셋뿐만 아니라 마디 및 템포 비트 그리드를 통합적으로 추적. | 단순 노트 분할용 마스크로 활용하기에는 모델의 연산 비중이 다소 큼. |

---

## 3. 모듈별 성능 평가 지표 및 판정 기준

모듈 교체 시 객관적인 정량 지표를 기반으로 채택 여부를 결정합니다.

```text
                  ┌─────────────────────────────────────────┐
                  │          평가 환경 정규화           │
                  │   (GT 주파수 / 2.0 옥타브 보정)   │
                  └────────────────────┬────────────────────┘
                                       │
            ┌──────────────────────────┴──────────────────────────┐
            ▼                                                     ▼
┌──────────────────────┐                              ┌──────────────────────┐
│ Isolated Mode 평가   │                              │    E2E Mode 평가     │
│ (Target: 피치 트래커)│                              │ (Target: 음원 분리)  │
└───────────┬──────────┘                              └───────────┬──────────┘
            │                                                     │
            ├─► Chroma F1 >= 80% (목표)                           ├─► Chroma F1 Gap <= 5% (목표)
            └─► Octave Error <= 15% (목표)                         └─► SDR >= 8.0 dB (목표)

```

---

| 검증 단계 | 대상 모듈 | 주요 평가 지표 (Metrics) | 기존 Baseline (참고치) | 채택 (Pass) 판정 기준 |
| :--- | :--- | :--- | :--- | :--- |
| **Phase 2** | 피치 트래커 (`Basic Pitch`, `RMVPE`) | **Isolated Chroma F1**<br>**Octave Error Rate** | 75.50 %<br>73.59 % *(보정 전)* | **Chroma F1 >= 80.0%**<br>**Octave Error <= 15.0%** *(GT 보정 후)* |
| **Phase 3** | 음원 분리 (`BS-RoFormer`) | **E2E SDR**<br>**E2E vs Isolated Chroma F1 격차** | 5.23 dB<br>16.20 %p 격차 | **SDR >= 8.0 dB**<br>**Chroma F1 격차 <= 5.0 %p** |
| **Phase 4** | 온셋 탐지 (`madmom`) | **Onset Precision / Recall / F1**<br>*(Tolerance=0.1s)* | - | **Onset F1 >= 85.0%** 및 연타/슬랩 분할 개선 확인 |

---

## 4. 기술적 리스크 및 관리 방안

### 리스크 1: 입출력 데이터 표현 및 타임스탬프 불일치
* **현상:** `Basic Pitch` 등은 프레임별 피치 빈 확률 행렬을 반환하므로, 기존 CREPE의 1차원 `f0` 배열 및 `hop_length` 타임스탬프와 차원이 다를 수 있습니다.
* **대처 방안:** 어댑터 래퍼 내부에서 프레임별 Max Probability 피치 인덱스를 Hz로 변환하고, 파이프라인의 `hop_length(160 @ 16kHz)` 기준에 맞춰 선형 보간(Interpolation) 연산을 수행하는 정규화 로직을 포함시킵니다.

### 리스크 2: 저음역대 하한선(fmin) 인덱스 오버플로우
* **현상:** 보컬/일반 악기용 피치 트래커의 기본 하한선이 베이스 개방현(E1=41.2Hz, B0=30.9Hz)보다 높게 설정되어 있을 경우, 초저역대 노트 추적 실패 및 음수 인덱스 접근 오류가 발생할 수 있습니다.
* **대처 방안:** 어댑터 초기화 시 minimum frequency(`fmin`) 파라미터를 30Hz 대역으로 명시적 할당하고, 안전범위 미만 주파수에 대한 Clamping(하한선 고정) 처리를 적용합니다.

### 리스크 3: GPU 메모리 점유 및 연산 병목
* **현상:** `BS-RoFormer` 등 고성능 트랜스포머 모델 적용 시 VRAM 점유율 증가로 인한 OOM 위험이 존재합니다.
* **대처 방안:** 기존 파이프라인에 구현된 30초 오디오 Chunking 연산 구조를 재활용하고, `torch.cuda.amp` (Mixed Precision) 추론을 적용하여 메모리 점유율을 관리합니다.

---

## 5. 단계별 실행 로드맵 (Execution Roadmap)

### Phase 1: 평가 프레임워크 정상화 (1일차)
- [ ] `src/evaluation/evaluator.py` 내 Slakh 정답지(GT) 주파수를 `/ 2.0` 하강시키는 기준 정규화 적용.
- [ ] 10곡 마이크로 테스트(Isolated 및 E2E)를 가동하여 **'정상화된 Baseline F1 Score'** 측정 및 `evaluation_record.md` 업데이트.

### Phase 2: Pitch Tracker 모듈 A/B 테스트 (2~3일차)
- [ ] `src/transcription/adapters/` 디렉토리 신설.
- [ ] `Basic Pitch` 기반 어댑터 래퍼 (`basic_pitch_adapter.py`) 작성.
- [ ] 10곡 Isolated 모드 테스트 실행 후 `Chroma F1` 및 `Octave Error Rate` 측정.
- [ ] `RMVPE` 기반 어댑터 래퍼 (`rmvpe_adapter.py`) 작성 및 동일 조건 비교 평가.
- [ ] 목표 지표 달성 시 메인 `tracker.py` 백엔드 선택 옵션으로 반영.

### Phase 3: Source Separation 모듈 A/B 테스트 (4일차)
- [ ] `BS-RoFormer` 래퍼 스크립트 연동.
- [ ] 10곡 E2E 모드 테스트 실행하여 SDR 측정 및 Isolated 모드와의 Chroma F1 격차 비교.
- [ ] 분리 품질 향상 폭과 추론 연산 시간 간의 트레이드오프 검토 후 채택 여부 결정.

### Phase 4: Onset Detection 및 파이프라인 통합 (5일차)
- [ ] `madmom` 온셋 디텍터 래퍼 작성 및 노트 분할 정밀도 검증.
- [ ] `pipeline.py` 설정 제어부(Config)에 신규 모듈들을 옵션 인자로 통합.
- [ ] 전체 130곡 테스트셋 중 20곡 표본에 대한 최종 종합 벤치마크 수행 및 데브로그 업데이트.
