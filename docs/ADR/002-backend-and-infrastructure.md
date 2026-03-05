# [ADR-002] 백엔드 프레임워크 및 인프라 환경(Docker) 도입

* **Status:** Accepted
* **Date:** 2026-02-20
* **Category:** Backend-Infra

## 1. Context (배경)

본 프로젝트는 무거운 딥러닝 모델(Demucs)을 구동하여 수십 MB의 오디오 파일을 처리해야 한다. 
초기 로컬(Windows) 환경에서 개발을 진행하는 동안 다음과 같은 심각한 아키텍처 및 인프라 문제에 직면했다.

1.  **OS 의존성 및 DLL 충돌:** Windows 환경에서 PyTorch와 C++ 기반 오디오 라이브러리(`ffmpeg`, `libsndfile` 등)를 연동할 때, 환경 변수 누락으로 인한 `[WinError 1114] DLL 초기화 루틴 실패` 에러가 빈번하게 발생했다.
2.  **프로세스 오버헤드:** 초기에는 서브프로세스(`subprocess.run`)로 터미널 명령어를 호출하여 오디오를 분리했으나, 이 방식은 매 요청마다 무거운 파이썬 인터프리터와 모델을 메모리에 새로 적재해야 하므로 서버 환경에 부적합했다.
3.  **향후 확장성 문제:** 1차 목표(음원 분리) 달성 후, 2차 목표인 '베이스 타브(TAB) 악보 생성'을 위해 `librosa`, `crepe` 등 복잡한 DSP 라이브러리가 추가될 예정이다. 로컬 환경 유지 시 심각한 '의존성 지옥(Dependency Hell)'이 예상되었다.

## 2. Decision (결정)

위 문제들을 근본적으로 해결하기 위해 다음과 같은 소프트웨어 및 인프라 아키텍처를 최종 채택한다.

1.  **Backend Framework:** Python 기반의 **FastAPI** 도입.
2.  **Inference Method:** 외부 터미널 호출(Subprocess)을 폐기하고, FastAPI 서버 메모리 내에서 Demucs 파이썬 내부 모듈(`demucs.separate.main`)을 **직접 호출(Direct Import)**하는 단일 프로세스 아키텍처로 변경.
3.  **Infrastructure:** 서버 실행 환경을 **Docker (Linux 컨테이너)**로 전면 격리.

## 3. Rationale (의사결정 근거)

### 3.1. 왜 FastAPI인가?
* **비동기 I/O와 스레드풀 분리:** 대용량 오디오의 업로드/다운로드(I/O Bound)는 네이티브 비동기(async/await)로 처리하여 네트워크 병목을 해소하고, 무거운 딥러닝 추론 연산(CPU/GPU Bound)은 FastAPI의 백그라운드 스레드풀(일반 def 엔드포인트 활용)로 오프로딩하여 메인 이벤트 루프의 블로킹을 방지할 수 있는 유연성을 제공한다.
* **개발 생산성:** Pydantic을 통한 데이터 검증과 자동 생성되는 Swagger UI(/docs) 덕분에, 별도의 프론트엔드 없이도 즉각적인 API 통신 및 파일 업로드 테스트가 가능하다.

### 3.2. 왜 Docker인가? (환경 격리)
* **재현 가능한 환경(Reproducibility):** `python:3.10-slim` 기반의 독립된 리눅스 환경을 구축하여 Windows OS 특유의 DLL 에러를 원천 차단했다. 
* **의존성 캡슐화:** 시스템 필수 패키지(`ffmpeg`, `libsndfile1`)를 `Dockerfile` 내에 명시하여, 어떤 PC나 클라우드(AWS, GCP) 서버에 배포하더라도 100% 동일하게 동작함을 보장한다.
* **개발 편의성 유지:** `docker-compose.yml`에 Volume Mount(`- ./app:/app/app`)를 설정하여, 컨테이너를 매번 재빌드할 필요 없이 로컬에서 코드를 수정하면 즉시 서버에 반영(Hot-reloading)되도록 구성했다.

## 4. Consequences (결과)

* **Positive:** * OS 충돌로 인한 서버 다운 현상이 완벽히 해결되었으며, 추후 클라우드 배포를 위한 인프라적 뼈대가 완성되었다.
    * 모델 가중치 파일 다운로드 경로를 Docker Volume으로 로컬 시스템(`model_cache`)과 공유하여, 컨테이너 재시작 시 발생하는 초기 로딩 시간을 대폭 단축했다.
* **Negative & Mitigation:** * Docker(WSL2 백엔드) 구동 자체가 호스트 PC의 RAM을 상당히 점유하는 오버헤드가 발생한다. (로컬 PC 환경에 맞춰 `.wslconfig`를 통해 리눅스 엔진의 최대 메모리를 제한하는 방식으로 대응함)

## 5. Addendum (2026-03-06)
* **Event Loop Blocking Issue Resolved:** 초기 구현 시 `app/main.py`의 엔드포인트가 `async def`로 선언되어, 문서 3.1항의 의도와 달리 Uvicorn의 메인 이벤트 루프를 블로킹하는 치명적 결함이 발견되었다. 이를 일반 `def`로 수정하여 Starlette의 외부 스레드풀(Threadpool)로 추론 연산을 정상 오프로딩하도록 교정 완료함.
* **Storage Leak Prevention:** `BackgroundTasks`를 도입하여 API 응답 직후 임시 파일(WAV)이 디스크에서 안전하게 삭제되도록 조치함.
