# 🎸 Automatic Bass Transcription & Separation Pipeline

![Python](https://img.shields.io/badge/Python-3.10-blue.svg)
![PyTorch](https://img.shields.io/badge/PyTorch-AI-orange.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-API-green.svg)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-DB-blue.svg)
![Docker](https://img.shields.io/badge/Docker-Ready-blue.svg)

## 📌 Project Overview
본 프로젝트는 믹스된 오디오 음원에서 베이스 트랙을 완벽하게 분리하고, 이를 바탕으로 **실제 연주 가능한 타브 악보(ASCII Tablature)**를 자동 생성하는 End-to-End AI 파이프라인입니다. 

단순한 주파수 추출을 넘어, 베이시스트의 생체역학적 운지 제약(String Skipping, Fret Shift)을 수학적으로 모델링한 Viterbi HMM 알고리즘을 통해 가장 자연스럽고 최적화된 운지법(Smart Fingering)을 제안합니다. 최근 SQL 기반의 비동기 상태 관리 및 샌드박스 아키텍처를 도입하여 대규모 트래픽 수용을 위한 프로덕션 레벨의 MLOps 인프라로 고도화되었습니다.

## ✨ Key Features
1. **High-Fidelity Bass Separation:** `Demucs` (4-Stem) 모델을 활용한 고품질 베이스 트랙 및 MR(Backing Track) 분리.
2. **Robust Pitch Tracking:** `CREPE` 딥러닝 모델 기반의 고해상도 피치 추적 (30초 단위 Chunking 처리 및 동적 VRAM 회수 메커니즘 적용).
3. **Viterbi Smart Fingering (HMM):** 동적 계획법(DP)을 통해 수직/수평 이동 비용, 하이 프렛 페널티, 시간 가중치($\Delta t$)를 계산하여 전역 최적 운지 경로 디코딩.
4. **Rhythmic Quantization:** Bassless MR 기반 전역 템포 맵(BPM) 추출 및 SSE(오차 제곱합) 기반 동적 격자 스냅(Triplet/16th) 양자화.
5. **Stateful Async Backend:** PostgreSQL 및 SQLAlchemy 2.0을 활용한 비동기 작업 상태 추적, 단명 세션(Short-lived Session) 패턴을 통한 DB 커넥션 풀 보호.
6. **Robust Resource Management:** Task 단위 샌드박스 격리, Queue-Aware TTL, FastAPI Lifespan 기반의 가비지 컬렉션(GC)을 통한 스토리지/메모리 누수 원천 차단.

---

## 🚀 Quick Start (설치 및 실행)

본 프로젝트는 오디오 처리 라이브러리(C++) 및 데이터베이스 환경이 요구됩니다. 개발 및 배포 편의성을 위해 **Docker Compose 환경**을 제공합니다. (단, 로컬 개발 시 VMM 메모리 오버헤드 방지를 위해 WSL2 네이티브 구동을 권장합니다.)

### 1. API 서버 및 DB 구동 (Docker Compose)
```bash
git clone [https://github.com/sjkim-audio/Bass-separator.git](https://github.com/sjkim-audio/Bass-separator.git)
cd Bass-separator

# PostgreSQL DB 및 FastAPI 컨테이너 빌드 및 백그라운드 실행
docker-compose up -d --build
```
- **API Swagger UI:** `http://localhost:8000/docs` (여기서 직접 I/O 테스트 가능)

### 2. Web UI 구동 (Streamlit)
로컬 파이썬 환경에서 프론트엔드 대시보드를 실행하여 시각적으로 결과물을 확인합니다.
```bash
pip install -r requirements.txt
streamlit run app.py
```
- **웹 데모 접속:** `http://localhost:8501`

---

## 📊 Benchmark Evaluation (성능 평가)

모델 고도화 및 파라미터 튜닝 시 성능 하락 여부(Regression)를 방어하기 위한 정량 평가 CLI 프레임워크입니다. (Slakh2100 데이터셋 기준)

```bash
# 1. Colab / 로컬 환경 필수 의존성 셋업
python -c "from src.env_setup import init_colab_env; init_colab_env()"

# 2. 대규모 배치 평가 가동 (E2E 모드, 위상 지연 자동 보정 포함)
python -m src.evaluation.run_batch_eval \
    --test_dir ./slakh_processed/test \
    --task e2e \
    --onset_tolerance 0.1 \
    --exp_id Phase8_Baseline
```
*평가 결과는 `results/` 디렉토리 내 JSON 파일로 자동 누적 저장됩니다.*

---

## 🧠 Core Pipeline Architecture (데이터 흐름도)

비동기 폴링 및 SQL 영속성 관리가 포함된 E2E 파이프라인의 핵심 흐름입니다.

1. **Task Request (API):** 클라이언트가 오디오 파일 업로드 $\rightarrow$ DB에 `PENDING` 상태 기록 및 `task_id` 발급 후 즉시 응답 반환 (비동기 폴링 시작).
2. **Sandbox & Separation:** 작업 전용 샌드박스 할당, DB 상태를 `PROCESSING`으로 업데이트 후 스레드풀에서 `Demucs` 4-Stem 분리 $\rightarrow$ Bass 트랙 및 Bassless MR(백킹 트랙) 추출.
3. **Pitch Tracking:** `CREPE` 모델 추론 (30초 Chunking, $f_{min}=40Hz \sim f_{max}=400Hz$ 도메인 최적화) 및 예측 신뢰도(Confidence) 산출.
4. **Symbolic Culling & Parsing:** 플럭(Pluck) 노이즈 등 기형적 가짜 피치를 기호 영역에서 강제 병합 및 필터링.
5. **Smart Fingering:** `Viterbi HMM` 알고리즘을 통한 생체역학적 최적 운지법(String/Fret) 전역 탐색.
6. **Rhythmic Quantization:** MR 기준 글로벌 템포 맵 추출 $\rightarrow$ 오차 제곱합(SSE) 기반 3연음/16분음표 동적 격자 스냅 및 단선율화.
7. **Rendering & Persistence:** ASCII 타브 악보 및 물리적 타이밍이 보존된(`.mid`) 파일 생성 $\rightarrow$ DB에 `SUCCESS` 상태 및 결과 메타데이터(JSONB) 영구 저장.
8. **Cleanup:** Queue-Aware TTL 및 Lifespan GC를 통해 만료된 샌드박스 리소스를 안전하게 회수.

---

## 📂 Repository Structure

```text
.
├── alembic/              # 데이터베이스 마이그레이션 스크립트 (Alembic)
│   └── versions/         # 스키마 리비전 히스토리
├── app/                  # FastAPI 기반 REST API 백엔드 서버
│   ├── database/         # 비동기 DB 엔진, 세션 관리 및 SQLAlchemy ORM 모델
│   ├── schemas/          # API 응답 및 데이터 컨트랙트 계층 (Pydantic DTO)
│   └── main.py           # API 라우팅, DB 트랜잭션 격리, Lifespan GC 및 상태 관리
├── docs/                 # 프로젝트 기술 문서 (표준 Taxonomy 적용)
│   ├── ADR/              # Architecture Decision Records (설계 의사결정 기록)
│   ├── devlogs/          # 알고리즘 실험 및 인프라 트러블슈팅 일지
│   ├── planning/         # 향후 로드맵, 파인튜닝 계획 및 전략적 트레이드오프
│   └── API_SPEC.md       # 프론트엔드-백엔드 비동기 통신 규약
├── notebooks/            # EDA, 알고리즘 프로토타이핑 및 R&D 연구 환경
├── src/                  # 코어 비즈니스 로직 및 DSP 라이브러리 (도메인 분리)
│   ├── core/             # 파이프라인 제어 및 외부 연산 격리
│   │   ├── demucs_runner.py  # Demucs 4-Stem 모델 추론 래퍼 및 오디오 Numpy 텐서 병합(MR 생성) 로직
│   │   └── pipeline.py       # 분리 -> 트래킹 -> 파싱 -> 디코딩 -> 양자화로 이어지는 상태 제어 중앙 컨트롤러
│   ├── evaluation/       # 벤치마크 및 다중 도메인 성능 정량 평가 프레임워크
│   │   ├── evaluator.py      # BSSEval(분리), mir_eval(채보) 정량 지표 채점 및 위상 지연 동기화(Alignment) 코어
│   │   ├── run_batch_eval.py # 대규모 데이터셋(Slakh2100) 비동기 배치 평가 및 OOM/메모리 누수 방어 스크립트
│   │   ├── run_eval.py       # 단일/다중 도메인 평가 수행용 CLI 엔트리포인트
│   │   └── visualization.py  # 멜 스펙트로그램, 피아노 롤, 오차 스캐터 플롯 등 평가 지표 시각화 도구
│   ├── models/           # 데이터 스키마 및 도메인 객체
│   │   └── events.py         # 파이프라인 전반을 관통하는 단일 진실 공급원(SSOT) 불변(Immutable) 객체 모델
│   ├── renderers/        # 최종 결과물 포맷팅 및 직렬화 로직
│   │   ├── midi_renderer.py  # 양자화(Grid Snap)를 배제하여 실제 연주의 그루브(Micro-timing)를 보존하는 .mid 추출기
│   │   └── tab_renderer.py   # 양자화된 격자 데이터 기반으로 겹침 없는 단선율 ASCII 텍스트 악보 생성기
│   ├── transcription/    # 음향 분석 및 타브 악보 변환 핵심 알고리즘
│   │   ├── fingering.py      # Viterbi HMM 동적 계획법(DP)을 활용한 생체역학적(수평/수직, 개방현) 최적 운지법 디코더
│   │   ├── parser.py         # 오디오 신호 배열을 이산적 이벤트로 파싱 및 플럭(Pluck) 노이즈 병합(Symbolic Culling) 처리
│   │   ├── quantization.py   # MR 트랙 기준 템포(BPM) 추출 및 오차 제곱합(SSE) 동적 격자 스냅/단선율화 엔진
│   │   └── tracker.py        # CREPE 딥러닝 기반 피치 추적 및 Onset 기반 파티션 필터링(옥타브 도약 방어) 로직
│   ├── augmentation.py       # 파인튜닝을 대비한 Pedalboard 기반 아날로그 질감(Distortion/Compressor) 데이터 증강 모듈
│   ├── env_setup.py          # 구글 코랩 및 로컬 환경의 OS 종속성(FFmpeg 등) 자동 구축 헬퍼 스크립트
│   ├── main.py               # 백엔드 API 없이 단일 터미널 환경에서 코어 파이프라인을 실행하는 래퍼 스크립트
│   └── utils.py              # 구글 드라이브 연동, 평가 결과 JSON I/O 등 공통 유틸리티 함수 모음
├── alembic.ini           # Alembic 설정 파일
├── app.py                # Streamlit 기반 프론트엔드 웹 데모 (MVP 시각화 및 다운로드)
├── docker-compose.yml    # API 서버 및 PostgreSQL DB 컨테이너 오케스트레이션
├── Dockerfile            # API 서버 이미지 빌드 명세서
├── requirements.txt      # Python 패키지 의존성
├── LICENSE               # 오픈소스 라이선스
└── README.md             # 프로젝트 개요 및 가이드 (현재 파일)
```
