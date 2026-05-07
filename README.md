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
│   ├── API_SPEC.md       # 프론트엔드-백엔드 비동기 통신 규약
├── notebooks/            # EDA, 알고리즘 프로토타이핑 및 R&D 연구 환경
│   ├── archive/          # 초기 소스 분리 실험 (Demucs, UMX, NMF 등) 아카이브
│   └── transcription/    # Viterbi HMM, 디바운싱, 양자화 등 전사 알고리즘 튜닝 기록
├── src/                  # 코어 비즈니스 로직 및 DSP 라이브러리 (도메인 분리)
│   ├── core/             # 파이프라인 제어 및 프로세스 격리
│   │   ├── demucs_runner.py # Demucs 4-Stem 오디오 분리 및 Numpy MR 병합 로직
│   │   └── pipeline.py      # E2E 전사 파이프라인 (분리 -> 트래킹 -> 디코딩 -> 양자화)
│   ├── models/           # 데이터 스키마 및 도메인 객체
│   │   └── events.py        # 파이프라인 전반을 관통하는 불변 객체(NoteEvent) 모델
│   ├── renderers/        # 최종 결과물 포맷팅 로직
│   │   ├── midi_renderer.py # 물리적 타이밍/운지법/Velocity가 보존된 .mid 파일 생성기
│   │   └── tab_renderer.py  # ASCII 텍스트 기반 퀀타이즈 타브 악보 렌더러
│   ├── transcription/    # 음향 분석 및 타브 악보 변환 핵심 알고리즘
│   │   ├── fingering.py     # Viterbi HMM 기반 최적 운지법(Fret/String) 탐색 알고리즘
│   │   ├── parser.py        # 오디오 데이터 파싱 및 기호 영역 후처리 (Garbage Pitch Culling)
│   │   ├── quantization.py  # BPM 기반 밀리초(ms) 물리량의 음악적 양자화 (동적 격자 스냅)
│   │   ├── tab_generator.py # 노트 이벤트를 악보 좌표계로 매핑
│   │   └── tracker.py       # CREPE 기반 피치 트래킹(Pitch Detection) 및 옥타브 보정
│   ├── augmentation.py   # 파인튜닝용 오디오 데이터 합성 및 증강 모듈
│   ├── env_setup.py      # 의존성 및 환경 구축 스크립트
│   ├── evaluation.py     # 분리(SDR) 및 채보(mir_eval F1-Score) 정량 평가 모듈
│   ├── main.py           # CLI 환경 전용 단일 파이프라인 실행 래퍼 스크립트
│   ├── run_eval.py       # 다중 도메인 평가 파이프라인 일괄 실행 CLI
│   ├── utils.py          # 공통 유틸리티 및 실험 결과 I/O 함수
│   └── visualization.py  # 멜 스펙트로그램 및 피아노 롤 시각화 모듈
├── app.py                # Streamlit 기반 프론트엔드 웹 데모 (MVP 시각화 및 다운로드)
├── docker-compose.yml    # API 서버 컨테이너 오케스트레이션
├── Dockerfile            # API 서버 이미지 빌드 명세서
├── requirements.txt      # Python 패키지 의존성
├── LICENSE               # 오픈소스 라이선스
└── README.md             # 프로젝트 개요 및 가이드 (현재 파일)
