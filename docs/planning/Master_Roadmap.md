# 🎸 Master Roadmap: End-to-End Bass Transcription & MLOps Pipeline

본 문서는 오디오 소스 분리부터 딥러닝 피치 트래킹, 수학적 운지법 최적화, 그리고 프로덕션 레벨의 백엔드 인프라 구축에 이르는 프로젝트 전체의 발전 단계(Phase)와 거시적 마일스톤을 정의하는 단일 진실 공급원(SSOT, Single Source of Truth)이다.

---

## 📌 Part 1. Completed Core Pipeline (Phase 1 ~ 8)
> **Status:** All Completed & Frozen
> **Goal:** 믹스 음원에서 베이스를 고해상도로 분리하고, 실제 연주 가능한 타브 악보 및 물리적 MIDI를 추출하는 End-to-End 알고리즘 및 단일 노드 아키텍처의 완성.

### Phase 1. Baseline & Infrastructure (기준점 설정 및 컨테이너화)
*   `htdemucs` 4-Stem 모델을 도입하고 추론 완료 후 CPU 단에서 Drums, Vocals, Other 트랙을 합산하여 MR(Bassless)을 생성하는 음원 분리 공식 확립[cite: 8, 9].
*   `python:3.10-slim` 기반 Docker 환경에 `ffmpeg` 등 OS 의존성을 캡슐화하고 FastAPI 라우터 뼈대 구축[cite: 7, 9].

### Phase 2. Deep Learning Transcription (자동 채보 및 피치 트래킹)
*   `torchcrepe` 알고리즘 도입 및 5현 베이스 대역폭을 고려해 하한선(`fmin`)을 40Hz로 고정하여 인덱싱 슬라이스 오류 억제[cite: 7, 9].
*   VRAM 메모리 오버헤드를 막기 위한 '30초 단위 Chunking' 설정 적용[cite: 8].
*   정적 트렌드 오염을 막기 위해 Onset-Bounded Segmental Filtering 적용 및 50ms 지연 버퍼(Wobble Tolerance) 신설[cite: 7, 9].

### Phase 3. Clean Architecture & Smart Fingering (모듈화 및 운지법 최적화)
*   `NoteEvent` 불변 데이터 클래스(Immutable Dataclass)를 도입하여 모듈 간 상태 오염을 제어하는 단방향 함수형 아키텍처 확립[cite: 7, 9].
*   생체역학적 이동 비용(수직/수평, 하이 프렛 등)을 모델링한 **Viterbi HMM 디코더**를 구현하여 전역 최적 운지 경로 산출[cite: 7, 9].

### Phase 4. Rhythmic Quantization & Concurrency (양자화 및 동시성 제어)
*   `Bassless MR` 중심의 총체적 템포 맵(Global Tempo Map)을 구축하고, 오차 제곱합(SSE) 기반으로 3연음/16분음표 동적 격자 평가 적용[cite: 7, 9].
*   오버랩 충돌 시 선행 노트의 오프셋을 강제 절단하여 100% 단선율화(Monophonic Enforcer)하고, 50ms 이하의 파편화 노트를 병합하는 기호 영역 필수 후처리 로직 확립[cite: 8].
*   `asyncio.Semaphore(1)`를 통한 GPU 직렬화 및 비동기 폴링(Polling) 큐잉 도입으로 다중 사용자 접속 시 OOM 방어[cite: 7, 9].

### Phase 5. API & Web UI Integration (평가 프레임워크 및 프론트엔드 연동)
*   직렬화 페이로드 크기를 억제하기 위해 Pydantic DTO 응답 스키마의 부동소수점을 3자리로 제한하고, 예측 신뢰도(Confidence) 메타데이터를 보존하는 API 통신 규격 확립[cite: 7].
*   양자화를 배제하여 물리적 리듬(Micro-timing)이 보존된 표준 `.mid` 파일 추출 로직 구축[cite: 7, 9].
*   Streamlit 기반의 MVP 웹 대시보드를 연동하여 E2E 파이프라인 시각화 테스트 환경 완성[cite: 7, 9].

### Phase 6. DSP Fine-Tuning & Symbolic Culling (오디오 도메인 튜닝)
*   HPF 컷오프(35Hz) 튜닝으로 럼블 노이즈에 의한 대규모 노트 증발(Massive Note Omission) 현상 차단[cite: 8, 9].
*   슬랩 팝(Pop) 타격 시 발생하는 기형적 마찰음을 60ms 이하 & 5반음 도약 조건으로 제거하는 기호 영역 후처리(Symbolic Culling) 도입[cite: 8, 9].

### Phase 7. Task Isolation & E2E Stability (샌드박스 격리 및 시스템 안정화)
*   고유 `task_id` 기반의 샌드박스 디렉토리 할당으로 동시성 환경에서의 파일 I/O 충돌(Race Condition) 원천 차단[cite: 7, 9].
*   OOM 발생 시 배치 사이즈를 반감하는 동적 백오프(Dynamic Backoff) 구축[cite: 7, 9]. 
*   CREPE 추론 시 발생하는 타임스탬프 밀림(Desync)을 교정하기 위해 마지막 프레임을 강제 절삭(`[:-1]`)하는 프레임 동기화 디테일 적용[cite: 8, 9].

### Phase 8. DataOps & Baseline Quantification (데이터옵스 및 벤치마크 평가)
*   100GB 규모 Slakh2100 데이터셋의 메모리 병목을 회피하는 **2-Pass 스트리밍 추출 아키텍처** 구축[cite: 7, 9].
*   정답 데이터의 옥타브 편향을 물리 주파수로 정규화하고, Demucs 위상 지연(Latency)을 상호상관도로 동기화하는 정량 평가기 가동[cite: 7, 9].
*   양자화 패널티 해소 후 **E2E F1-Score 63.03%** 성능 상한선 달성 확인 및 코어 알고리즘 튜닝 동결(Freeze)[cite: 9].
*   도출된 오답을 False Positive(노이즈 오인), False Negative(노트 증발), Octave Error 등 지배적 유형으로 분류하는 에러 분류 체계(Taxonomy)를 수립하여 타겟팅 개선 근거 마련[cite: 8].

---

## 🚀 Part 2. Production MLOps Evolution (Phase 9 ~ 14)
> **Status:** Planned (Active Development)
> **Goal:** 알고리즘 연구를 넘어, 대규모 트래픽 수용과 시스템 생존성(Survivability)을 증명하는 백엔드/MLOps 프로덕션 인프라 고도화 및 확장.

### Phase 9. Async Serving & Persistence (비동기 분산 큐 및 상태 영속화)
*   **Celery + Redis:** FastAPI(API Gateway)와 GPU 추론 워커를 물리적으로 격리하여 OOM 크래시로부터 메인 웹 서버의 생존성 보장[cite: 7, 9].
*   **PostgreSQL + SQLAlchemy 2.0:** 작업 생명주기를 RDBMS에 영구 저장하고, 서버 기동 시 고아 프로세스를 복구하는 자가 치유(Self-healing) 로직 구현[cite: 7, 9].

### Phase 10. Network Optimization (네트워크 및 페이로드 최적화)
*   **SSE 통신:** 폴링(Polling) 방식을 폐기하고 Server-Sent Events 기반 단방향 실시간 상태 스트리밍 구축[cite: 9].
*   **DTO 오프로딩:** 서버의 무거운 강제 양자화 및 문자열 렌더링 로직을 제거하고, 순수 원시 데이터(`NoteEvent`)만 반환하여 렌더링 부하를 클라이언트로 위임[cite: 9].

### Phase 11. Architecture Decoupling Proof (SOTA 모델 핫스왑 증명)
*   **BS-RoFormer 마이그레이션:** 벤치마크 성능을 제약하는 최종 병목인 전처리 왜곡(Demucs SAR) 타파를 위해 대역별 어텐션 기반 SOTA 모델 도입[cite: 7, 9].
*   **동적 서빙 배포(CD):** 코어 로직 격리 원칙을 활용하여 하위 파이프라인 수정 없이 2GB 이상의 모델 가중치를 유연하게 무중단 교체(Hot-swap)하고, `Production` 태그 기반 가중치 동적 로드 체계 마련[cite: 9].

### Phase 12. DataOps & Automated CI (데이터옵스 및 자동화 게이트)
*   **DVC 리니지:** Google Drive를 연동하여 오디오 데이터셋의 형상(Version)을 관리하고 파이프라인 재현성(Reproducibility) 확보[cite: 9].
*   **APM 로깅 및 CI 파이프라인:** API 지연 시간 및 VRAM 점유율 관측성 체계 정립[cite: 9]. GitHub Actions를 활용해 10초 미만 더미 샘플로 회귀(Regression)를 방어하는 CPU 기반 Smoke Test 도입[cite: 9].
*   **데이터셋 확장 전략:** 향후 타현 주법(5가지 세분화 라벨링) 분류 연구용으로 명시했던 'IDMT-SMT-Bass' 데이터셋 활용 계획 편입[cite: 8].

### Phase 13. Standard Notation Export (표준 악보 직렬화 엔진)
*   **MusicXML / GuitarPro 지원:** 단순 ASCII 타브를 넘어, 음악적 평탄화(Musical Smoothing) 휴리스틱을 거치고 `music21` 또는 `pyguitarpro` 라이브러리를 채택하여 `MusicXML`(`.xml`) 또는 `GuitarPro`(`.gp5`) 형식의 파일을 직접 직렬화하는 렌더링 엔진 신설[cite: 7, 8, 9].

### Phase 14. Viterbi Algorithm Optimization (운지법 자동 최적화)
*   **가중치 튜닝 자동화:** Optuna 또는 베이지안 최적화를 도입하여, 정답 악보와 모델 출력 간의 편집 거리(Levenshtein Distance)가 최소화되는 최적의 생체역학적 이동 비용 가중치 자동 탐색 파이프라인 구축[cite: 8].
