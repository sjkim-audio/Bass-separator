## 🗓️ Project Roadmap: Bass Source Separation for Specialized Playing Styles

이 프로젝트는 일반적인 팝 음악뿐만 아니라, 특수한 주법(Slap)과 다양한 이펙터(Distortion, Modulation) 환경에서도 강력한 성능을 발휘하는 베이스/기타 분리 모델 구축을 목표로 합니다.

### Phase 1. 기준점 설정 및 정량적 평가 (Baseline & Evaluation)
> **Goal:** 객관적인 성능 지표(Metrics)를 확립하고 현재 모델의 한계를 수치화한다.
- [ ] **Golden Test Set 구축:** 학습에 사용하지 않는 고품질 평가 전용 데이터셋 2~5곡 녹음 (Clean/Drive/Slap 등 조건별 분류)
- [ ] **Baseline 성능 측정:** Pre-trained `htdemucs` 모델을 이용한 초기 분리 성능 테스트
- [ ] **평가 파이프라인 구축:** `museval`을 활용한 3대 지표(SDR, SIR, SAR) 자동 계산 스크립트 작성 (`src/metrics.py`)
- [ ] **1차 리포트 작성:** 기존 모델의 주법별/이펙터별 성능 하락폭 기록 (예: "드라이브 톤에서 SIR 3dB 하락 확인")

### Phase 2. 취약점 심층 분석 (Error Analysis)
> **Goal:** 모델이 실패하는 원인을 시각적/청각적으로 분석하여 개선 방향을 잡는다.
- [ ] **Stress Test:** 과도한 이펙팅, 빠른 속주 등 극한 상황에서의 분리 오류(Artifacts) 테스트
- [ ] **시각적 분석:** `src/visualization.py`를 활용해 Spectrogram 상에서 주파수 간섭(Frequency Masking) 및 누수(Leakage) 구간 시각화
- [ ] **Target 선정:** 파인튜닝 시 집중적으로 개선할 우선순위 주법 및 톤 선정

### Phase 3. 데이터 중심 성능 개선 (Data-Centric AI)
> **Goal:** 코드 수정보다 데이터의 품질과 다양성을 높여 성능을 끌어올린다.
- [ ] **Custom Dataset 녹음:** 취약 파트(예상: 슬랩 주법, 디스토션 톤 등) 집중 녹음
- [ ] **Stem Mixing Pipeline:** 개별 트랙(Bass, Guitar, Drums, Vocals)을 랜덤 조합하여 학습 데이터 수량 증식
- [ ] **Advanced Augmentation:** `src/augmentation.py`를 통해 Pitch Shift, Time Stretch, EQ 변형 등 데이터 증강 적용

### Phase 4. 모델 최적화 및 파인튜닝 (Fine-tuning & MLOps)
> **Goal:** 커스텀 데이터를 학습시키고 실험 과정을 체계적으로 관리한다.
- [ ] **Transfer Learning:** 기존 가중치(Checkpoint)를 기반으로 커스텀 데이터셋 추가 학습 진행
- [ ] **Experiment Tracking:** WandB 등을 도입하여 학습률(Learning Rate) 및 Loss 변화 추적
- [ ] **Model Selection:** Validation Set 기준 SDR/SIR 점수가 가장 높은 최적의 모델 선정 (Checkpoint 저장)

### Phase 5. 기능 확장: 자동 채보 및 타브 생성 (Audio-to-Tab) [New✨]
> **Goal:** 분리된 고품질 베이스 오디오를 분석하여 연주 가능한 타브 악보로 변환한다.
- [ ] **Pitch Tracking:** `pYIN` 또는 `CREPE` 알고리즘을 활용해 베이스의 기본 주파수(f0) 정밀 추출 (`src/transcription.py`)
- [ ] **Note Segmentation:** 연속된 주파수 신호를 개별 음표(Note Onset/Offset)로 분리하는 알고리즘 구현
- [ ] **Fretboard Mapping Logic:** 추출된 음을 '가장 연주하기 편한' 줄과 프렛 위치로 변환하는 알고리즘 개발 (Cost Function 활용)
- [ ] **Tab Output:** 분석 결과를 텍스트(ASCII) 또는 MIDI 포맷으로 출력

### Phase 6. 배포 및 문서화 (Deployment & Documentation)
> **Goal:** 연구 결과를 실제 프로덕트로 만들고 기술적 가치를 증명한다.
- [ ] **Web Demo 배포:** Hugging Face Spaces & Gradio를 활용한 웹 기반 도구 제작 (MP3 업로드 -> Bass 분리 & 악보 다운로드)
- [ ] **Tech Blog 작성:** 문제 정의부터 해결 과정(SDR 상승 수치 포함)을 담은 기술 포스팅
- [ ] **Final Project Report:** 전체 파이프라인과 성과를 요약한 최종 포트폴리오 문서화
