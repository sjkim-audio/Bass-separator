# 🚀 E2E Bass Transcription & MLOps Pipeline


**Document Purpose:**
본 문서는 베이스 오디오 자동 채보 파이프라인의 발전 과정, 핵심 아키텍처 의사결정(ADR), 그리고 향후 고도화 계획을 명세한 전략적 마스터 로드맵이다. 단순한 연구용 스크립트를 넘어 프로덕션 레벨의 E2E(End-to-End) 서비스로 진화하기 위해, 프로젝트를 **Track A (코어 알고리즘 및 DSP 고도화)**와 **Track B (시스템 인프라 및 MLOps 확장)**의 두 축으로 나누어 기술 부채 상환 및 현실적인 성능 검증 계획을 기록한다.

---

## 🎵 Track A: Automatic Bass Transcription Algorithm Evolution
**목표:** 믹스 오디오에서 베이스를 분리하고, 단선율 피치와 물리적 운지법을 추출하는 핵심 신호 처리 및 추론 알고리즘의 고도화.

### 📍 Phase 1~6: Core DSP, Pitch Tracking & API Infra (동결 완료)
**목표:** 다중 사용자 환경에서 안정적으로 서비스하는 알고리즘 기반 확립.
* **음원 분리 (Demucs v4):** 기본 `htdemucs` 4-Stem 모델을 사용하여 분리한 후, CPU 단에서 Drums, Vocals, Other를 합산하여 Bassless MR을 생성하는 후처리 아키텍처 확정.
* **피치 추적 및 도메인 최적화 (CREPE):** 딥러닝 기반 단선율 피치 추적기 도입(`tiny` 모델, 30초 단위 Chunking). **도메인 튜닝(Golden State)**으로 HPF 컷오프를 35Hz, `fmin`을 40Hz의 안정적 초기값으로 동결하여 주파수-Bin 인덱싱 에러 및 럼블 노이즈로 인한 대규모 노트 증발(Massive Note Omission) 현상 차단.
* **최적 운지법 탐색 (Viterbi HMM):** 생체역학적 제약(손가락 이동 거리, 하이 프렛 도약 비선형 페널티)을 Transition Matrix로 모델링하여 은닉 마르코프 모델(HMM) 기반 최적 경로 탐색.
* **기호 영역 후처리 (Symbolic Culling):** 슬랩 팝(Pop) 타격 시 발생하는 비화성 쓰레기 노트("띠-딩")를 기호 영역에서 '60ms 이하 & 5반음 이상 급변' 조건으로 기계적으로 병합/삭제.
* **E2E API 및 UI 구축:** FastAPI 기반 비동기 폴링 서버 및 Streamlit MVP 프론트엔드 연동. `asyncio.Semaphore(1)`를 통한 GPU 직렬화로 OOM 1차 방어.

### 📍 Phase 7: Rhythmic Quantizer & E2E Stability (동결 완료)
**목표:** 물리적 시간을 격자에 동적 스냅하고 데이터 무결성 확보.
* **총체적 템포 맵 (Global Tempo Map) 및 Fallback:** 템포 추출 1순위로 `Bassless MR` 채택. 단일 베이스 트랙(Isolated) 입력 시 고주파 노이즈가 비트로 오인되는 현상을 막기 위해 명시적으로 MR 변수에 `None`을 주입, 저주파 대역(`fmax=400`) 전용 추적기로 우회(Fallback)시키는 방어 로직 구축.
* **단선율 강제화 (Monophonic Enforcer):** 오버랩 충돌 시 선행 노트의 오프셋을 강제 절단하여 100% 단선율화. 동일 피치의 50ms 이하 파편화 노트는 퀀타이저 단에서 병합.
* **Task 샌드박스 격리 & 프레임 동기화:** `task_id` 기반 샌드박스 디렉토리 격리로 Race Condition 방지. OOM 발생 시 강제 VRAM 회수 메커니즘 도입. CREPE 청크 병합 시 발생하는 타임스탬프 밀림 현상을 마지막 프레임 강제 절삭(`[:-1]`)으로 교정 완료.

### 🚀 Phase 8: Baseline Quantification & Regression Test (진행 중 / 최우선 과제)
**목표:** 객관적 평가 지표(Baseline)를 수립하여 알고리즘 수정 시 성능 하락 방지.
* **Slakh2100 벤치마크 평가:** `src/evaluation.py`를 가동하여 현재 파이프라인의 양자화 전(Raw)과 후(Quantized) Onset/Pitch F1-Score 초기 기준값(Baseline) 확보.
* **에러 분류 체계(Taxonomy) 확립:** False Positive(노이즈 오인), False Negative(노트 증발), Octave Error 등 도출된 오답의 지배적 유형을 분류하여 타겟팅 개선의 근거로 활용.

### 🚀 Phase 9: Notation Readability & Standard Export (예정)
**목표:** ASCII 타브의 가독성 한계 극복 및 표준 악보 포맷 제공.
* **Musical Smoothing (음악적 평탄화):** 양자화기 내부에 32분음표 이하의 미세 파편음을 인접 노트로 병합하거나 무시하는 휴리스틱 로직을 추가하여 악보 가독성 확보.
* **Standard Serialization Engine:** `music21` 또는 `pyguitarpro`를 연동하여 추출된 데이터를 MusicXML(`.xml`) 또는 GuitarPro(`.gp5`) 파일로 직렬화 및 다운로드 제공.

### 🚀 Phase 10: Viterbi Optimization (예정)
**목표:** 경험적 수치(Heuristics)를 알고리즘적 최적화로 대체.
* **Viterbi Weight Tuning:** Optuna 또는 베이지안 최적화를 도입하여, 정답 악보와 모델 출력 간의 편집 거리(Levenshtein Distance)가 최소화되는 최적의 생체역학적 이동 비용 가중치 자동 탐색.

---

## 📊 Data Strategy & Evaluation Framework
알고리즘 검증 및 향후 고도화를 위해 활용할 제한적이고 현실적인 오픈소스 데이터 전략이다.

### 1. Slakh2100-redux (Baseline 및 회귀 테스트용)
* **특징:** 전문가급 VSTi로 렌더링된 고품질 합성음 및 100% 매핑된 다중 트랙 MIDI.
* **활용:** Phase 8의 코어 알고리즘(Parser, Quantizer) 논리 결함 검증 및 F1-Score 상한선(Upper Bound) 측정. 알고리즘 튜닝 시 성능 하락 여부를 자동 판별하는 테스트 베드.

### 2. IDMT-SMT-Bass (주법 분류 연구용 - 장기 보류)
* **특징:** 실제 베이스 연주 및 5가지 타현 주법 세분화 라벨링 제공.
