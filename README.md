# 🎸 Automatic Bass Transcription & Separation Pipeline

![Python](https://img.shields.io/badge/Python-3.10-blue.svg)
![PyTorch](https://img.shields.io/badge/PyTorch-AI-orange.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-API-green.svg)
![Docker](https://img.shields.io/badge/Docker-Ready-blue.svg)

## 📌 Project Overview
본 프로젝트는 믹스된 오디오 음원에서 베이스 트랙을 완벽하게 분리하고, 이를 바탕으로 **실제 연주 가능한 타브 악보(ASCII Tablature)**를 자동 생성하는 End-to-End AI 파이프라인입니다. 

단순한 주파수 추출을 넘어, 베이시스트의 생체역학적 운지 제약(String Skipping, Fret Shift)을 수학적으로 모델링한 **Viterbi HMM 알고리즘**을 통해 가장 자연스럽고 최적화된 운지법(Smart Fingering)을 제안합니다.

## ✨ Key Features
1. **High-Fidelity Bass Separation:** `Demucs` 모델을 활용한 고품질 베이스 트랙 및 MR(Backing Track) 분리.
2. **Robust Pitch Tracking:** `CREPE` 딥러닝 모델 기반의 고해상도 피치 추적 (30초 단위 Chunking 처리로 VRAM 최적화).
3. **Smart Error Correction:** `librosa.onset`을 활용해 어택(Slap 등)을 보존하면서 불필요한 배음(Octave) 에러만 선택적으로 평탄화하는 휴리스틱 보정 로직.
4. **Viterbi Smart Fingering (HMM):** 동적 계획법(DP)을 통해 수직/수평 이동 비용, 하이 프렛 페널티, 시간 가중치($\Delta t$)를 계산하여 최적의 운지 경로를 디코딩.
5. **Note Debouncing:** 상태 머신(State Machine) 기반 알고리즘으로 미세한 피치 흔들림과 결측치(NaN)에 의한 가짜 속주(False Polyphony) 현상 제거.
6. **FastAPI Backend:** 오디오 분리 및 추론을 위한 Docker 기반 API 서버 지원.

---

## 🚀 Quick Start (설치 및 실행)

본 프로젝트는 오디오 처리 라이브러리(C++)의 OS 의존성 및 DLL 충돌을 방지하기 위해 **Docker 기반 환경**을 강력히 권장합니다.

### 1. API 서버 구동 (Docker)
```bash
git clone [https://github.com/sjkim-audio/Bass-separator.git](https://github.com/sjkim-audio/Bass-separator.git)
cd Bass-separator

# FastAPI 컨테이너 빌드 및 백그라운드 실행
docker-compose up -d --build
```
* **API Swagger UI:** `http://localhost:8000/docs` (여기서 직접 I/O 테스트 가능)

### 2. Web UI 구동 (Streamlit)
로컬 파이썬 환경에서 프론트엔드 대시보드를 실행하여 시각적으로 결과물을 확인합니다.
```bash
pip install -r requirements.txt
streamlit run app.py
```
* **웹 데모 접속:** `http://localhost:8501`

---

## 📊 Benchmark Evaluation (성능 평가)

모델 고도화 및 파라미터 튜닝 시 성능 하락 여부(Regression)를 방어하기 위한 정량 평가 CLI 프레임워크입니다. (Slakh2100 데이터셋 기준)

```bash
# 1. Colab / 로컬 환경 필수 의존성 셋업
python -c "from src.env_setup import init_colab_env; init_colab_env()"

# 2. 대규모 배치 평가 가동 (E2E 모드, 위상 지연 자동 보정 포함)
python -m src.evaluation.run_batch_eval \
    --test_dir ./slakh_processed/test \
    --exp_id Phase8_Baseline
```
*평가 결과는 `results/` 디렉토리 내 JSON 파일로 자동 누적 저장됩니다.*

---

## 🧠 Core Pipeline Architecture (데이터 흐름도)

단일 API 호출 시 내부적으로 실행되는 불변 데이터(Immutable Data) 파이프라인의 핵심 흐름입니다.

1. **Audio Input:** 믹스 오디오 업로드 (최대 50MB 제한, 비동기 큐잉).
2. **Source Separation:** `Demucs` 4-Stem 분리 $\rightarrow$ Bass 트랙 추출 및 Bassless MR(백킹 트랙) 병합.
3. **Pitch Tracking:** `CREPE` 모델 추론 (30초 Chunking, $f_{min}=40Hz \sim f_{max}=500Hz$ 도메인 최적화).
4. **Symbolic Culling:** 플럭(Pluck) 노이즈 등 60ms 이하의 가짜 피치를 기호 영역에서 강제 병합 및 필터링.
5. **Smart Fingering:** `Viterbi HMM` 알고리즘을 통한 생체역학적 최적 운지법(String/Fret) 전역 디코딩.
6. **Rhythmic Quantization:** Bassless MR 기준 글로벌 템포 맵(BPM) 추출 $\rightarrow$ 오차 제곱합(SSE) 기반 3연음/16분음표 동적 격자 스냅.
7. **Rendering & Export:** ASCII 형태의 퀀타이즈 타브 악보 및 물리적 원본 시간이 보존된(Unquantized) `.mid` 파일 병렬 추출.

---

## 📂 Repository Structure

```text
.
├── app/                  # FastAPI 기반 REST API 백엔드 서버
│   ├── main.py           # API 라우팅 (비동기 폴링, 상태 영속화, 정적 파일 서빙)
│   ├── schemas/          # API 응답 및 데이터 컨트랙트 계층
│   │   └── response.py   # Pydantic 기반 응답 DTO 스키마
│   ├── temp_uploads/     # 업로드된 원본 오디오 임시 대기열 (런타임 생성)
│   └── outputs/          # 최종 추출물 (Bass, MR, JSON, MIDI) 저장소 (런타임 생성)
├── docs/                 # 프로젝트 기술 문서 (표준 Taxonomy 적용)
│   ├── ADR/              # Architecture Decision Records (설계 의사결정 기록)
│   ├── devlogs/          # 알고리즘 실험 및 인프라 트러블슈팅 일지
│   ├── planning/         # 향후 로드맵, 파인튜닝 계획 및 전략적 트레이드오프
│   └── API_SPEC.md       # 프론트엔드-백엔드 비동기 통신 규약
├── notebooks/            # EDA, 알고리즘 프로토타이핑 및 R&D 연구 환경
│   ├── data_prep/        # 모델 파인튜닝 및 평가를 위한 데이터셋 전처리 (Slakh2100)
│   ├── evaluation/       # 음원 분리 및 채보 모델 성능 정량 평가 및 에러 시각화
│   ├── separation/       # 음원 분리 모델 실험 (Demucs, OpenUnmix 등)
│   └── transcription/    # Viterbi HMM, 디바운싱, 양자화 등 전사 알고리즘 튜닝 기록
├── src/                  # 코어 비즈니스 로직 및 DSP 라이브러리 (도메인 분리)
│   ├── core/             # 파이프라인 제어 및 프로세스 격리
│   │   ├── demucs_runner.py # Demucs 4-Stem 오디오 분리 및 Numpy MR 병합 로직
│   │   └── pipeline.py      # E2E 전사 파이프라인 (분리 -> 트래킹 -> 디코딩 -> 양자화)
│   ├── evaluation/       # 벤치마크 및 다중 도메인 성능 정량 평가 프레임워크
│   │   ├── evaluator.py     # BSSEval(분리) 및 mir_eval(채보) 정량 평가 코어 로직
│   │   ├── run_batch_eval.py# 대규모 배치 평가(Slakh2100) 및 OOM 방어 스크립트
│   │   ├── run_eval.py      # 단일/믹스 다중 도메인 평가 파이프라인 실행 CLI
│   │   └── visualization.py # 멜 스펙트로그램, 피아노 롤 등 평가 지표 시각화 모듈
│   ├── models/           # 데이터 스키마 및 도메인 객체
│   │   └── events.py        # 파이프라인 전반을 관통하는 불변 객체(NoteEvent) 모델
│   ├── renderers/        # 최종 결과물 포맷팅 로직
│   │   ├── midi_renderer.py # 물리적 타이밍/운지법/Velocity가 보존된 .mid 파일 생성기
│   │   └── tab_renderer.py  # ASCII 텍스트 기반 퀀타이즈 타브 악보 렌더러
│   ├── transcription/    # 음향 분석 및 타브 악보 변환 핵심 알고리즘
│   │   ├── fingering.py     # Viterbi HMM 기반 최적 운지법(Fret/String) 탐색 알고리즘
│   │   ├── parser.py        # 오디오 데이터 파싱 및 기호 영역 후처리 (Garbage Pitch Culling)
│   │   ├── quantization.py  # BPM 기반 밀리초(ms) 물리량의 음악적 양자화 (동적 격자 스냅)
│   │   └── tracker.py       # CREPE 기반 피치 트래킹(Pitch Detection) 및 옥타브 보정
│   ├── augmentation.py   # 파인튜닝용 오디오 데이터 합성 및 증강 모듈
│   ├── env_setup.py      # 의존성 및 환경 구축 스크립트
│   ├── main.py           # CLI 환경 전용 단일 파이프라인 실행 래퍼 스크립트
│   └── utils.py          # 공통 유틸리티 및 실험 결과 I/O 함수
├── app.py                # Streamlit 기반 프론트엔드 웹 데모 (MVP 시각화 및 다운로드)
├── docker-compose.yml    # API 서버 컨테이너 오케스트레이션
├── Dockerfile            # API 서버 이미지 빌드 명세서
├── requirements.txt      # Python 패키지 의존성
├── LICENSE               # 오픈소스 라이선스
└── README.md             # 프로젝트 개요 및 가이드 (현재 파일)
```
