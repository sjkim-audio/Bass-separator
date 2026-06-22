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

## ⚙️ Track B: System Infrastructure & MLOps Pipeline
**목표:** 대규모 트래픽을 견디는 비동기 서빙 인프라를 구축하고, 모델 품질 고도화를 위한 MLOps 체계를 확립한다.

### 🚀 Milestone 1. Core E2E Pipeline MVP & Data Contracts
**목표:** 오디오 입력부터 최종 데이터 구조체까지 이어지는 무결성 보장.
* **추론 아키텍처 확립:** Demucs(분리) $\rightarrow$ CREPE(피치 추적) $\rightarrow$ 전후처리(Filtering) 파이프라인 통합.
* **Unquantized 타이밍 및 운지법 디코딩:** 강제 격자 할당 로직 폐기. Onset 해상도를 밀리초 단위로 극대화하여 슬랩, 셔플 등 연주의 미세한 타이밍(Micro-timing)을 보존하는 Unquantized MIDI 추출 및 Viterbi 디코딩 수행.
* **표준화된 데이터 컨트랙트(DTO) 구현:**
  * **MLOps 메타데이터 통합:** 파인튜닝 추적용 `TranscriptionMetadata` 신설 및 클라이언트 다운로드용 정적 파일 서빙 URL DTO 내장.
  * **신뢰도(Confidence) 지표 보존:** CREPE 모델의 예측 확률을 보존하여 프론트엔드의 고스트 노트 시각적 렌더링 지원.
  * **직렬화 오버헤드 방어:** 부동소수점 데이터는 Pydantic `@field_validator`로 밀리초 단위 반올림하여 페이로드 팽창 억제.

### 🚀 Milestone 2. Asynchronous Serving Infrastructure
**목표:** 비동기 확장성 확보 및 실시간 진행 상태 스트리밍(SSE) 구축.
* **메시지 브로커 및 Task Queue 일원화:** FastAPI는 API Gateway 역할(HTTP 202)만 수행하며, 모든 추론 요청을 Redis/Celery 큐로 일원화. 단일 세마포어(Semaphore) 병목 해소.
* **Priority Queue 기반 워커 최적화:** 짧은 오디오 전담 `High-Priority Worker`와 대용량 전담 `Heavy-Duty Worker` 분리. 하드/소프트 타임아웃 강제 설정.
* **SSE (Server-Sent Events) 상태 스트리밍:** Polling의 낭비를 배제하고 FastAPI `StreamingResponse`를 통해 Celery Task 상태를 클라이언트에 단방향 푸시.

### 🚀 Milestone 3. Front-End Integration & UX
**목표:** 반응형 웹 UI 연동 및 데이터 클라이언트 제어권 이관.
* **React/Vanilla JS 프론트엔드 구축:** Streamlit 폐기 및 SSE 네이티브 웹 아키텍처 도입.
* **클라이언트 사이드 렌더링 및 제어:** 인터랙티브 악보 렌더링 및 '16분음표 스냅(Snap to Grid)' 토글을 구현하여 사용자가 원할 때만 양자화 제어.
* **E2E 통합 부하 테스트:** 업로드 $\rightarrow$ Celery 분배 $\rightarrow$ GPU 추론 $\rightarrow$ SSE 렌더링 사이클 검증.

### 🚀 Milestone 4. Data-Centric MLOps & Fine-Tuning
**목표:** 파이프라인 안정화 이후 베이스 분리 및 피치 추적의 한계 돌파.
* **프로그래매틱 데이터 합성:** 타 악기(MR)와 베이스 소스를 오류 없이 자동 믹싱/증강.
* **Training-Serving Skew 방어:** 훈련 데이터 생성 시 서빙 환경과 동일한 Sample Rate 변환 전처리 강제.
* **4-Stem 마스킹 학습 및 실험 추적:** 기존 4-Stem 분리 모델의 파국적 망각을 막기 위해 미비 트랙 Zero-padding 및 Partial Loss Optimization 도입. MLflow 연동 하이퍼파라미터 추적.

---

## 📊 Data Strategy & Evaluation Framework
알고리즘 검증 및 향후 고도화를 위해 활용할 제한적이고 현실적인 오픈소스 데이터 전략이다.

### 1. Slakh2100-redux (Baseline 및 회귀 테스트용)
* **특징:** 전문가급 VSTi로 렌더링된 고품질 합성음 및 100% 매핑된 다중 트랙 MIDI.
* **활용:** Phase 8의 코어 알고리즘(Parser, Quantizer) 논리 결함 검증 및 F1-Score 상한선(Upper Bound) 측정. 알고리즘 튜닝 시 성능 하락 여부를 자동 판별하는 테스트 베드.

### 2. IDMT-SMT-Bass (주법 분류 연구용 - 장기 보류)
* **특징:** 실제 베이스 연주 및 5가지 타현 주법 세분화 라벨링 제공.
