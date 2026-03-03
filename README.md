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
├── app/                  # FastAPI 기반 API 서버 (분리 서비스)
│   ├── main.py           # API 엔드포인트 라우팅
│   └── services/         # Demucs 프로세스 실행 등 비즈니스 로직
├── docs/                 # 프로젝트 문서 (ADR, 로드맵, 개발 일지 등)
│   ├── ADR/              # Architecture Decision Records
│   └── Transcription_devlog.md # 핵심 개발 기록
├── notebooks/            # 알고리즘 실험 및 데이터 분석 환경 (Jupyter)
│   ├── archive/          # 과거 알고리즘 비교 실험 (NMF, UMX 등)
│   └── transcription/    # 타브 생성 및 에러 보정 파이프라인 실험
├── src/                  # 핵심 파이썬 모듈 (Core Library)
│   ├── augmentation.py   # 파인튜닝용 오디오 증강 모듈
│   ├── bass_transcription.py # CREPE 트래킹 및 Post-processing 로직
│   ├── env_setup.py      # 의존성 및 환경 구축 스크립트
│   ├── evaluation.py     # 분리 성능 정량 평가 (SDR, SIR, SAR)
│   ├── tab_generator.py  # Viterbi HMM 및 상태 머신 적용 타브 생성기
│   └── visualization.py  # 피아노 롤 및 스펙트로그램 시각화
├── docker-compose.yml    # API 서버 컨테이너 오케스트레이션
├── Dockerfile            # API 서버 이미지 빌드 파일
└── requirements.txt      # Python 패키지 의존성
```

