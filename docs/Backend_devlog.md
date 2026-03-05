# 🖥️ Backend & Infrastructure Pipeline (DevLog)

> **Status:**
> Phase 1 Completed (Local CLI & Subprocess Execution)
> Phase 2 Completed (FastAPI & Docker Containerization)
> Phase 3 In Progress (End-to-End API Integration & Pydantic Schema)
> Phase 4 Planned (Asynchronous Task Queue for Multi-user Scaling)

## 1. Overview
이 프로젝트는 완성된 오디오 전사(Transcription) 파이프라인을 다수의 클라이언트(웹/앱)가 호출할 수 있도록 **FastAPI 기반의 RESTful API 서버로 전환**하고, 안정적인 서비스 구동을 위한 **Docker 인프라 환경**을 구축하는 과정을 기록합니다.

초기(Phase 1)에는 파이썬 `subprocess`를 통해 터미널 명령어로 모델을 구동했으나, 이는 매 요청마다 파이썬 인터프리터를 새로 적재하는 막대한 오버헤드와 Windows OS 특유의 DLL 충돌(WinError 1114)을 유발하는 한계가 있었습니다. 이를 해결하기 위해(Phase 2) **FastAPI** 프레임워크를 도입하고, 시스템 의존성을 완벽히 격리하는 **Docker(Linux) 컨테이너** 아키텍처로 전면 이관했습니다. 현재(Phase 3)는 CLI용으로 설계된 파이프라인의 출력(Console Print) 계층을 HTTP 통신에 적합한 JSON/DTO 구조로 리팩토링하여 E2E 통합을 진행 중입니다.

---

## 2. Server Architecture Evolution

서버 아키텍처는 성능 병목과 확장성 한계를 극복하기 위해 다음과 같이 진화했습니다.



### Step 1: Subprocess to Direct Import (Phase 1 -> 2)
- **Problem:** 기존 CLI 모델은 외부 셸 명령을 호출하여(Demucs) 결과를 디스크에 쓰고 다시 읽어오는 방식이었습니다.
- **Optimization:** FastAPI 메모리 내에서 `demucs.separate.main`을 직접 호출(Direct Import)하는 단일 프로세스 구조로 변경하여, I/O 오버헤드를 줄이고 프로세스 컨텍스트 스위칭 비용을 제거했습니다.

### Step 2: Threadpool Offloading (Event Loop Unblocking)
- **Problem:** 무거운 PyTorch 추론 함수를 비동기 라우터(`async def`) 내에서 실행하여, 연산이 진행되는 수십 초 동안 Uvicorn의 단일 이벤트 루프가 완전히 마비(Blocked)되는 치명적 결함이 존재했습니다.
- **Optimization:** API 엔드포인트를 동기 함수(`def`)로 선언하여, Starlette 엔진이 CPU-Bound 연산(Demucs, CREPE)을 **외부 스레드풀(Background Threadpool)**로 자동 오프로딩하도록 아키텍처를 교정했습니다. 이를 통해 모델 추론 중에도 다른 클라이언트의 헬스 체크나 가벼운 요청을 정상 처리할 수 있습니다.

### Step 3: API Response Normalization (Phase 3 - In Progress)
- **Problem:** 기존 `TabRenderer`는 ASCII 악보를 콘솔에 직접 출력(`print()`)하도록 설계되어 HTTP Body에 데이터를 담을 수 없었습니다. 또한 텍스트만 반환할 경우 프론트엔드에서의 악보 상호작용(인터랙티브 UI)이 불가능합니다.
- **Optimization:** 시각화용 텍스트(`ascii_tab`)와 데이터 파싱용 JSON 배열(`notes`)을 동시에 반환하는 하이브리드 Pydantic 응답 스키마를 도입하여 프론트엔드 확장성을 보장합니다.

---

## 3. Challenges & Solutions (Troubleshooting)

서버 및 인프라 구축 과정에서 발생한 주요 문제점과 해결 방안입니다.

| Issue | Cause | Solution |
| :--- | :--- | :--- |
| **Phase 1 (Local Environment)** | | |
| **`[WinError 1114]` DLL 초기화 실패** | Windows 환경에서 PyTorch와 C++ 기반 오디오 라이브러리(`ffmpeg`, `libsndfile` 등)의 환경 변수 및 DLL 충돌. | 로컬 OS 의존성을 탈피하고, `python:3.10-slim` 기반의 독립된 **Docker Linux 컨테이너**로 서버 구동 환경을 전면 격리. |
| **Phase 2 (FastAPI Migration)** | | |
| **Event Loop Blocking (서버 마비)** | `async def` 엔드포인트 내부에서 무거운 딥러닝 추론(Demucs)을 동기적으로 실행하여 ASGI 서버 루프가 차단됨. | 엔드포인트를 **일반 `def`로 변경**하여 Starlette의 백그라운드 스레드풀을 활용한 CPU 연산 오프로딩 적용. |
| **Storage Leak (디스크 용량 초과)** | API 응답 완료 후에도 업로드된 원본 WAV와 처리된 임시 오디오 파일이 디스크에 지속적으로 누적됨. | FastAPI의 **`BackgroundTasks`**를 활용하여, 클라이언트에게 응답(FileResponse)을 반환한 직후 백그라운드에서 임시 파일들을 안전하게 `os.remove` 하도록 삭제 파이프라인 구축. |
| **Phase 3 (API Integration)** | | |
| **데이터 직렬화(Serialization) 불가** | E2E 파이프라인의 종착지인 `TabRenderer`가 순수 함수(Pure Function)가 아닌 상태 변이형(Console Print)으로 작성됨. | `print()` 로직을 제거하고, 완성된 악보를 **문자열(String)로 조립하여 반환**하도록 렌더러 인터페이스를 리팩토링. |
| **프론트엔드 UI 확장성 한계** | API가 텍스트(`\n`이 포함된 긴 문자열)만 반환할 경우, 클라이언트 측에서 16분음표 격자 단위의 하이라이팅이나 노트 수정이 불가능함. | **Pydantic DTO**를 도입하여, 시각적 악보 텍스트뿐만 아니라 개별 `NoteEvent` 객체의 상세 정보(시간, 프렛, 격자 인덱스)를 배열 형태의 JSON으로 함께 직렬화하여 제공. |

---

## 4. Future Works (Roadmap)

다음 단계의 백엔드 목표입니다.

- [ ] **Pydantic Schema & DTO:** E2E 파이프라인의 결과를 캡슐화할 `TranscriptionResponse` 및 `NoteDto` 모델 구현.
- [ ] **Renderer Return Refactoring:** `TabRenderer`가 콘솔 출력이 아닌 렌더링된 문자열을 반환하도록 수정.
- [ ] **E2E Pipeline Integration:** `app/main.py` 라우터에 `run_transcription_pipeline`을 연결하여 완전한 JSON 응답 도출.
- [ ] **Asynchronous Task Queue (Phase 4):** 다중 사용자 동시 접속 시 발생하는 CUDA OOM(VRAM 부족)을 방지하기 위해, **Celery + Redis** 기반의 백그라운드 작업 큐(Task Queue) 아키텍처 도입 및 폴링(Polling) 로직 구현.
