## 🗓️ Project Roadmap: Bass Source Separation & Automatic Transcription Pipeline

이 프로젝트는 특수 주법(Slap)과 이펙터 환경에 강건한 베이스 분리 모델 구축부터, 고도화된 딥러닝 피치 트래킹, 최적 운지법(Viterbi) 추천, 그리고 프로덕션 레벨의 백엔드 서빙까지 아우르는 End-to-End 파이프라인 완성을 목표로 합니다.

---

### Phase 1. 기준점 설정 및 인프라 평가 (Baseline & Infrastructure)
> **Status:** Completed 
> **Goal:** 객관적인 분리 성능 기준을 확립하고, 모델 서빙을 위한 아키텍처 뼈대를 구축한다.
- [x] **Baseline 모델 확립:** `--two-stems=bass` 튜닝 모델 대신, 종합적인 주파수 간섭 제어 성능이 더 우수한 `htdemucs` 4-Stem 기본 모델을 최종 베이스라인으로 채택.
- [x] **컨테이너화 (Dockerization):** `python:3.10-slim` 기반 환경에 `ffmpeg` 등 시스템 의존성을 격리하여 OS별 DLL 충돌 에러 원천 차단.
- [x] **비동기 API 뼈대 구축:** FastAPI 프레임워크를 도입하여 오디오 파일 업로드 및 추론(Inference) 대기 I/O 병목 해소.

### Phase 2. 데이터 중심 성능 개선 (Data-Centric AI)
> **Status:** Pending (채보 파이프라인 고도화 이후 진행)
> **Goal:** 모델이 실패하는 원인을 분석하고 데이터의 품질과 다양성을 높여 성능을 끌어올린다.
- [ ] **Golden Test Set 구축:** 학습에 사용하지 않는 고품질 평가 전용 데이터셋 녹음 (Clean/Drive/Slap 등 조건별 분류).
- [ ] **평가 파이프라인 구축:** `museval`을 활용한 3대 지표(SDR, SIR, SAR) 자동 계산 스크립트 작성.
- [ ] **Custom Dataset & Augmentation:** 취약 파트 집중 녹음 및 Pitch Shift, Time Stretch, EQ 변형을 통한 데이터 증강.

### Phase 3. 모델 최적화 및 파인튜닝 (Fine-tuning & MLOps)
> **Status:** Pending
> **Goal:** 커스텀 데이터를 학습시키고 실험 과정을 체계적으로 관리한다.
- [ ] **Transfer Learning:** 기존 `htdemucs` 가중치를 기반으로 커스텀 데이터셋 추가 학습.
- [ ] **Experiment Tracking:** WandB 등을 도입하여 학습률(Learning Rate) 및 Loss 변화 추적.
- [ ] **Model Selection:** Validation Set 기준 SDR/SIR 점수가 가장 높은 최적의 모델 릴리즈.

### Phase 4. 자동 채보 및 피치 트래킹 (Deep Learning Transcription)
> **Status:** Completed
> **Goal:** 딥러닝 알고리즘을 활용해 분리된 베이스 오디오에서 기본 주파수(f0)를 정밀하게 추출한다.
- [x] **Deep Learning Pitch Tracking:** `torchcrepe` (CNN-based) 알고리즘을 도입하여 베이스 음역대(40~500Hz)에 특화된 고해상도 피치 추출.
- [x] **Robust Signal Processing:** `librosa.onset` 및 주파수 필터를 결합하여 음악적 맥락(어택 보존, 배음 제어)을 반영한 오디오 전/후처리 파이프라인 구축.
- [x] **Scalable Inference Architecture:** 프로덕션 환경을 고려하여 제한된 GPU VRAM 내에서 대용량 오디오를 안정적으로 처리하는 분할 추론(Chunking) 최적화.

### Phase 5. 타브 생성 및 운지법 최적화 (Smart Fingering & Export) [진행 중 🚀]
> **Status:** In Progress
> **Goal:** 추출된 주파수 배열을 실제 연주자의 물리적 한계를 고려한 타브 악보 및 MIDI로 변환한다.
- [ ] **Smart Fingering Model:** 동적 계획법(Viterbi Algorithm & HMM)을 도입하여 손의 수평/수직 이동 비용(Cost)을 최소화하는 최적의 프렛-현(Fret-String) 맵핑 도출.
- [ ] **Note Segmentation & Quantization:** 연속된 주파수 신호를 이산적인 MIDI 노트로 변환(Quantization) 및 어택 기준 그룹화.
- [ ] **Tablature & MIDI Export:** DAW 연동을 위한 `.mid` 파일 생성 및 직관적인 가로형 ASCII 타브 악보 렌더링.

### Phase 6. 배포 및 문서화 (Deployment & Documentation)
> **Status:** Planned
> **Goal:** 연구 결과를 실제 웹 서비스 형태로 배포하고 기술적 가치를 증명한다.
- [ ] **Streamlit / Web Demo 구축:** 브라우저에서 MP3를 업로드하면 베이스 분리 ➔ 피치 추적 ➔ 타브 악보 시각화 및 MIDI 다운로드를 원클릭으로 제공하는 프론트엔드 연동.
- [ ] **Tech Blog 작성:** 오디오 AI 파이프라인 최적화 과정의 엔지니어링 의사결정(ADR) 포스팅.
- [ ] **Final Project Report:** 전체 아키텍처와 분리/채보 성능을 요약한 최종 포트폴리오 문서화.

---

### 🚨 아키텍처 리뷰 (Red Teaming)
기존 로드맵은 '음원 분리(Separation)'의 성능 향상(Phase 2~3)을 1차 목표로 삼았으나, 현재의 엔지니어링 리소스는 '채보 및 타브 생성(Phase 4~5)' 인프라에 집중되어 있습니다. 분리 모델의 파인튜닝은 막대한 커스텀 데이터셋 구축(녹음 및 믹싱)과 GPU 연산 시간이 요구되므로, 현재 진행 중인 **Phase 5 (Viterbi 운지법 최적화)와 Phase 6 (웹 서비스 데모 구축)를 통해 End-to-End 파이프라인의 MVP(Minimum Viable Product)를 먼저 완성**한 후, 모델 성능 고도화(Phase 2~3)로 회귀하는 애자일(Agile) 전략이 프로젝트 완수율을 높일 것입니다.
