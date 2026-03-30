# [Roadmap] Automatic Bass Transcription Algorithm Evolution

본 문서는 베이스 오디오 자동 채보 파이프라인의 발전 과정, 핵심 아키텍처 의사결정(ADR), 그리고 향후 고도화 계획을 명세한 전략 로드맵이다. 각 페이즈(Phase)별 기술적 한계와 이를 극복하기 위해 채택한 수학적/논리적 트레이드오프를 기록한다.

---

## 📍 Phase 1~6: Core DSP & Pitch Tracking (동결 완료)

**목표:** 믹스 오디오에서 베이스를 분리하고, 단선율 피치와 물리적 운지법을 1차원으로 추출.

### 핵심 아키텍처 및 의사결정
1. **음원 분리 (Demucs v4):** * `htdemucs` 모델을 사용하여 Bass, Drums, Vocals, Other 4-Stem 분리.
2. **피치 추적 (CREPE):** * 딥러닝 기반 단선율 피치 추적기 사용. 다중 피치 추정(MPE) 모델은 베이스 저음역대 배음 간섭으로 인한 위양성 화음 발생률이 높아 기각.
3. **최적 운지법 탐색 (Viterbi HMM):** * 생체역학적 제약(손가락 이동 거리, 프렛 간격)을 Transition Matrix로 모델링하여 은닉 마르코프 모델(HMM) 기반 최적 String/Fret 경로 탐색.
4. **기호 영역 후처리 (Symbolic Culling):** * 슬랩 팝(Pop) 타격 시 발생하는 비화성 쓰레기 노트("띠-딩" 2단 튀김)를 오디오 신호 단에서 강제 뮤트(Transient Muting)하려 했으나, 정상 노트의 어택까지 훼손되는 부작용 발생(Iteration 10). 
   * **결정:** 신호 조작을 폐기하고, MIDI 이벤트 생성 후 기호 영역에서 '60ms 이하 & 5반음 이상 급변' 조건을 찾아 기계적으로 삭제하는 방식으로 우회(Iteration 11).

### 한계 및 기술 부채
* **위임된 책임:** 물리적인 밀리초(ms) 단위의 파편화된 노트 및 미세한 타이밍 오차는 이 단계에서 무리하게 파라미터로 튜닝하지 않고(과적합 방지), 다운스트림인 Phase 7 리듬 양자화기로 책임을 위임함.

---

## 📍 Phase 7: Rhythmic Quantizer (진행 중)

**목표:** 밀리초 단위의 물리적 시간을 음악적 16분음표 격자(Grid)에 동적으로 스냅(Snap)하고 노트 파편화를 병합.

### 핵심 아키텍처 및 의사결정
1. **총체적 템포 맵 (Global Tempo Map):**
   * **결정:** 템포 추출의 단일 진실 공급원(Single Source of Truth)으로 `Bassless MR` (Drums + Vocals + Other) 채택. 베이스 트랙은 Fallback으로 강등.
   * **근거:** 파트별로 참조 트랙을 스위칭하면 위상 불연속성(Phase Discontinuity)이 발생함. 또한 베이스 라인은 싱코페이션(엇박)이 잦아 이를 기준으로 비트를 추적하면 16분음표 격자가 반 박자 밀리는 치명적 오류 발생.
2. **솔로 구간 관성 보간 (Inertial Interpolation):**
   * **결정:** 드럼이 없는 구간에서는 Viterbi Decoding의 누적 페널티를 활용해 직전 BPM의 관성을 유지하여 가상의 다운비트를 투사함.
3. **단선율 강제화 (Monophonic Enforcer):**
   * **결정:** 오버랩 충돌 시 선행 노트의 오프셋을 강제 절단(Truncate)하여 100% 단선율화.
   * **근거:** 가독성 확보. 동일 피치의 50ms 이하 파편화 노트는 퀀타이저 단에서 단일 서스테인으로 병합 처리.

### 한계점 (Edge Cases)
* **루바토(Rubato) 붕괴:** 연주자가 의도적으로 템포를 늘이거나 당기는 솔로 구간에서는 관성 보간망을 벗어나 악보가 왜곡됨. (현 DSP 기술의 한계로 수용).

---

## 🚀 Phase 8: Articulation ML Classification (예정)

**목표:** 피치와 시간을 넘어, 특수 주법(Slap, Pop, Slide, Hammer-on/Pull-off)의 음향적 특징을 역추적하여 기호화.

### 핵심 아키텍처 및 의사결정
1. **다차원 특징 추출 (Feature Engineering):**
   * 단일 임계값(Threshold) 기반의 휴리스틱 룰은 연주자의 톤 메이킹이나 믹싱에 따라 쉽게 무너짐.
   * **결정:** 분할된 오디오 세그먼트의 멜 스펙트로그램(Mel-spectrogram)과 스펙트럴 플럭스(Spectral Flux)를 연산하여 특성 도출.
2. **경량 기계학습 모델 도입:**
   * **결정:** 추출된 Feature를 1D CNN 또는 Random Forest에 통과시켜 6 다중 클래스(Finger, Pick, Thumb, Pop, Slide, Legato)로 분류.

### 한계점 (잠재적 리스크)
* **데이터 기아 (Data Starvation):** 주법별로 정밀하게 라벨링된 오픈소스 베이스 데이터셋 부재. 모델 학습을 위한 데이터 수집 및 라벨링 공수가 프로젝트 전체의 크리티컬 패스(Critical Path)가 될 수 있음.

---

## 🚀 Phase 9: Standardized Score Serialization (예정)

**목표:** 주법 기호 및 복합 리듬을 완벽하게 시각화하기 위해, 한계에 다다른 ASCII 타브 렌더러를 폐기하고 표준 악보 포맷으로 전환.

### 핵심 아키텍처 및 의사결정
1. **ASCII 렌더러의 구조적 한계 인정:**
   * **근거:** 고정폭 2차원 텍스트 배열 방식은 가변 폭을 요구하는 주법 기호(예: `-12s14-`) 삽입 시 수직 정렬이 붕괴됨. 다중 레이어(슬랩 상하단 기호) 동기화를 위해서는 렌더러를 브라우저 DOM 엔진 수준으로 재설계해야 하는 비효율 발생.
2. **표준 라이브러리 연동 (MusicXML / Guitar Pro):**
   * **결정:** `music21` 또는 `pyguitarpro` 라이브러리를 통합하여 Phase 8에서 추출된 주법 이벤트 메타데이터를 `.gp5` 또는 `.xml` 포맷으로 직렬화(Serialization)하여 Export.
   * **효과:** 렌더링 엔지니어링 병목 해소 및 유저에게 실제 편집/재생 가능한 프로덕션 레벨 악보 제공.

---

## 🚀 Phase 10: E2E API & Infrastructure (예정)

**목표:** R&D 환경의 스크립트를 프로덕션 레벨의 비동기 백엔드 서버로 통합.

### 핵심 아키텍처 및 의사결정
1. **비동기 오케스트레이션:**
   * `FastAPI` 인터페이스 구성 및 무거운 오디오 처리(Demucs, CREPE)를 `Celery/Redis` 기반 백그라운드 워커로 위임.
2. **I/O 병목 최적화:**
   * 스템 분리 후 발생하는 중간 산출물(wav)의 디스크 쓰기 작업을 최소화하고, `Numpy` 텐서를 RAM 메모리 상에서 파이프라인으로 직접 체이닝하여 지연 시간(Latency) 단축.
  
---

## 📊 Data Strategy & Evaluation Framework (신설)

귀와 눈에 의존하는 휴리스틱 튜닝을 벗어나, 학계 표준(MIR)에 입각한 정량적 평가 및 지도 학습(Supervised Learning) 파이프라인을 구축하기 위한 데이터 전략이다.

### 1. Core Datasets
수백 시간의 수작업 사보 및 녹음 노동을 제거하기 위해 다음의 검증된 오픈소스 데이터셋을 파이프라인에 통합한다.

* **Slakh2100-redux (대규모 벤치마크용):**
    * **특징:** 2,100곡의 멀티트랙 오디오와 100% 수학적으로 일치하는 MIDI 파일. 중복이 제거된 Redux 버전 사용.
    * **활용:** Phase 6(피치 추적) 및 Phase 7(양자화)의 F1-Score를 기계적으로 자동 산출하는 테스트 베드로 활용.
* **IDMT-SMT-Bass (주법 분류 ML 학습용):**
    * **특징:** Fraunhofer IDMT 연구소 구축. 4,300개의 단일 노트 오디오 및 5가지 타현 주법(Slap, Pop, Finger, Pick, Muted), 5가지 표현 주법(Slide, Vibrato 등) 라벨링 제공.
    * **활용:** Phase 8의 Articulation 다중 클래스 분류 모델(1D CNN/Random Forest)을 위한 핵심 학습(Training) 데이터로 활용. '데이터 기아' 문제 원천 해결.

### 2. 하이브리드 검증 아키텍처 (3-Track Validation)
1.  **Public Data 자동 검증:** Slakh2100을 통해 파이프라인의 베이스라인 성능(Precision, Recall, F1)을 자동 측정.
2.  **Public Data 모델 학습:** IDMT-SMT-Bass를 통해 주법 분류기 학습.
3.  **Custom Data 도메인 적응 (Domain Adaptation):** 직접 녹음한 소량의 커스텀 데이터(5~10곡)를 최종 엣지 케이스 및 손버릇 테스트용으로 제한적 활용.
