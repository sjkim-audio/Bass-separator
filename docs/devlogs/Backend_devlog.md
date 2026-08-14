# 🖥️ Backend & Infrastructure Pipeline (DevLog)

> **Status:**
> Phase 1 Completed (Local CLI & Subprocess Execution)
> Phase 2 Completed (FastAPI & Docker Containerization)
> Phase 3 Completed (End-to-End API Integration & Pydantic Schema)
> Phase 4 Completed (Single-node Concurrency Control & Polling)
> Phase 4.5 Completed (4-Stem Audio Separation & OS-Agnostic Subprocess)
> Phase 5 Completed (Data Diversification & Streamlit MVP Frontend)
> Phase 6 Completed (DSP Parameter Optimization & E2E Debugging)
> Phase 7 Completed (Task Isolation & VRAM Recovery Mechanism)
> Phase 8 Completed (DataOps Streaming Architecture & Evaluation Framework)
> Phase 9 Planned (Baseline Quantification & Standard Notation Engine)

## 1. Overview
이 프로젝트는 완성된 오디오 전사(Transcription) 파이프라인을 다수의 클라이언트(웹/앱)가 호출할 수 있도록 **FastAPI 기반의 RESTful API 서버로 전환**하고, 안정적인 서비스 구동을 위한 **Docker 인프라 환경**을 구축하는 과정을 기록합니다.

초기(Phase 1)에는 파이썬 `subprocess`를 통해 터미널 명령어로 모델을 구동했으나, 이는 매 요청마다 파이썬 인터프리터를 새로 적재하는 막대한 오버헤드와 Windows OS 특유의 DLL 충돌(WinError 1114)을 유발하는 한계가 있었습니다. 이를 해결하기 위해(Phase 2) **FastAPI** 프레임워크를 도입하고, 시스템 의존성을 완벽히 격리하는 **Docker(Linux) 컨테이너** 아키텍처로 전면 이관했습니다. 

중기(Phase 3, 4)는 CLI용으로 설계된 파이프라인을 객체 지향적으로 완벽히 분리(`src/core/pipeline.py`)하고, HTTP 통신에 적합한 JSON/DTO 구조로 리팩토링함과 동시에 **다중 사용자 접속 시 발생하는 서버 다운(OOM) 현상을 비동기 폴링과 세마포어로 억제**하는 데 성공했습니다.

최근(Phase 4.5, 5)에는 4-Stem 모델을 도입하고 고해상도 MR(Bassless) 음원을 병합 생성하는 로직을 통합했습니다. 이 과정에서 발생한 Windows 환경의 비동기 이벤트 루프 충돌(`NotImplementedError`)과 VRAM 누수 문제를 회피하기 위해, 플랫폼 독립적인 동기 호출(`subprocess.run`)을 비동기 스레드 풀(`loop.run_in_executor`)에 위임하는 하이브리드 아키텍처를 구축했습니다. 또한, **정적 파일 서빙 라우터**와 **Streamlit 기반의 MVP 프론트엔드 웹 데모**를 결합하여 디커플링(Decoupling)된 E2E 클라이언트-서버 시각화 환경을 완성했습니다.

최근(Phase 6, 7)에는 시스템을 프로덕션 레벨로 끌어올리기 위한 **안정성 경화(Hardening)** 및 **오디오 도메인 최적화** 작업에 집중했습니다. 다중 사용자 환경의 경쟁 상태(Race Condition)를 억제하는 **Task 샌드박스(Sandbox) 격리 아키텍처**를 도입하고, OOM 발생 시 파편화된 VRAM을 동적으로 회수하는 메커니즘을 적용했습니다.

최근(Phase 8)에는 대규모 정량 평가를 위한 **DataOps 파이프라인 및 평가 프레임워크**를 구축했습니다. 100GB에 달하는 벤치마크 데이터셋(Slakh2100)을 로컬 환경의 스토리지 및 메모리 병목 없이 처리하기 위해, 2-Pass 스트리밍 추출 아키텍처를 설계했습니다. 또한 정답 데이터의 옥타브 편향과 위상 지연을 교정하는 도메인 정규화 로직을 평가기(Evaluator) 인프라에 내장하여, 향후 MLOps 고도화를 위한 객관적 기반을 마련했습니다.

---

## 2. Server Architecture Evolution

서버 아키텍처는 성능 병목과 확장성 한계를 극복하기 위해 다음과 같이 진화했습니다.

### Step 1: Subprocess to Direct Import (Phase 1 -> 2)
- **Problem:** 기존 CLI 모델은 외부 셸 명령을 호출하여(Demucs) 결과를 디스크에 쓰고 다시 읽어오는 방식이었습니다.
- **Optimization:** FastAPI 메모리 내에서 `demucs.separate.main`을 직접 호출(Direct Import)하는 단일 프로세스 구조로 변경하여, I/O 오버헤드를 줄이고 프로세스 컨텍스트 스위칭 비용을 제거했습니다.

### Step 2: Threadpool Offloading (Event Loop Unblocking)
- **Problem:** 무거운 PyTorch 추론 함수를 비동기 라우터(`async def`) 내에서 실행하여, 연산이 진행되는 수십 초 동안 Uvicorn의 단일 이벤트 루프가 완전히 마비(Blocked)되는 치명적 결함이 존재했습니다.
- **Optimization:** 스타렛(Starlette) 엔진이 CPU-Bound 연산(Demucs, CREPE)을 **외부 스레드풀(Background Threadpool)**로 자동 오프로딩하도록 아키텍처를 교정하여, 모델 추론 중에도 헬스 체크나 다른 클라이언트의 요청을 정상 처리하도록 구성했습니다.

### Step 3: API Response Normalization & Validation (Phase 3)
- **Problem:** 기존 렌더러는 악보를 콘솔에 직접 출력(`print()`)하여 HTTP Body로 응답할 수 없었으며, `float64` 기반의 오디오 분석 데이터(시간, 신뢰도 등)가 무한 소수점으로 직렬화되어 네트워크 페이로드가 팽창하는 문제가 있었습니다.
- **Optimization:** Pydantic `TranscriptionResponse` DTO를 도입하고, `@field_validator`를 사용해 모든 부동소수점 데이터를 **밀리초 해상도(소수점 3자리)로 강제 반올림**하여 직렬화 비용과 응답 크기를 최소화했습니다.

### Step 4: Asynchronous Polling & Concurrency Control (Phase 4)
- **Problem:** 단일 노드(FastAPI)에서 무거운 딥러닝 연산을 처리할 때, 복수의 클라이언트가 동시에 파일을 업로드하면 GPU VRAM과 시스템 메모리가 고갈(OOM)되며 서버가 다운되는 현상이 발생했습니다.
- **Optimization:** 1. 라우터에 `asyncio.Semaphore(1)`를 적용하여 GPU 추론 파이프라인 실행을 강제로 직렬화(Sequential)했습니다.
  2. 요청 수락 시 즉시 **HTTP 202(Accepted)와 `task_id`를 반환**하고, 연산은 백그라운드로 넘기는 **비동기 폴링(Polling) 아키텍처**로 개편하여 장시간 연결(Timeout) 및 서버 마비를 회피했습니다.

### Step 5: OS-Agnostic Subprocess & External Process Isolation (Phase 4.5)
- **Problem:** Direct Import 방식은 FastAPI 워커 메모리와 PyTorch 텐서 자원이 결합되면서 서버 장기 가동 시 치명적인 VRAM 누수(Memory Leak)를 유발할 위험이 있었습니다. 이를 회피하고자 도입한 `asyncio.create_subprocess_exec` 호출 방식은 Windows 환경에서 Uvicorn의 `SelectorEventLoop`와 충돌하는 인프라 종속적 결함을 발현시켰습니다.
- **Optimization:** 완벽한 GPU 메모리 반환(OS 레벨 격리)을 위해 파이프라인을 다시 외부 서브프로세스로 분리하되, OS 호환성 문제가 없는 동기형 `subprocess.run`을 채택하고 이를 Uvicorn의 **비동기 스레드 풀(`loop.run_in_executor`)에 위임**하는 하이브리드 아키텍처를 구축하여 메모리 릭(Leak)과 이벤트 루프 충돌을 동시에 방어했습니다.

### Step 6: Data Output Diversification & MVP UI (Phase 5)
- **Problem:** 단순 JSON 및 텍스트 데이터만으로는 사용자가 오디오 분석 품질을 검증하거나 다른 DAW와 연동할 수 없었습니다.
- **Optimization:** 물리적 타이밍이 보존된 `.mid` 파일 추출 로직을 신설하고, FastAPI 내부 정적 파일 서빙(`StaticFiles`) 라우터를 마운트하여 Streamlit 전용 프론트엔드(`app.py`)와 통합된 오디오 플레이어 및 악보 렌더링 환경을 구축했습니다.

### Step 7: Task Isolation & Advanced VRAM Recovery (Phase 6.5 ~ 7)
- **Problem:** 기존의 공유 디렉토리 구조는 동시성 한도를 높일 경우 임시 파일 클린업 시 **경쟁 상태(Race Condition)**를 유발할 위험이 있었고, OOM 발생 시 단순 배치 사이즈 감소만으로는 VRAM 파편화를 해결하기 어려웠습니다.
- **Optimization:** 모든 요청이 고유한 **샌드박스 디렉토리** 내에서만 수행되도록 경로 계층을 재설계하여 스레드 안전(Thread-safe) 환경을 구축했습니다. 피치 트래커에는 `torch.cuda.ipc_collect()`와 `gc.collect()`를 결합한 명시적 메모리 해제 로직을 추가했습니다.

### Step 8: DataOps & Streaming Extraction Architecture (Phase 8)
- **Problem:** 정량 평가 프레임워크 구축 시, 100GB 규모의 벤치마크 데이터셋(Slakh2100)을 로컬 환경에서 압축 해제하고 파이썬 오디오 라이브러리(`librosa`)로 처리할 때 스토리지 부족(OOS) 및 대규모 메모리 할당으로 인한 RAM 병목(OOM)이 발생했습니다.
- **Optimization:** 아카이브(`.tar.gz`)를 디스크에 풀지 않고 파일 포인터만 순회하여 메타데이터를 1차 스캔한 뒤, 타겟 파일만 2차 추출하여 시스템 `FFmpeg` 서브프로세스로 변환하고 즉시 삭제하는 **2-Pass 스트리밍 추출 아키텍처(`prepare_slakh_local.py`)**를 구축했습니다. 이를 통해 파이썬 가비지 컬렉션을 우회하고 대규모 데이터 전처리 파이프라인의 인프라 무결성을 달성했습니다.

---

## 3. Challenges & Solutions (Troubleshooting)

서버 및 인프라 구축 과정에서 발생한 주요 문제점과 방어 내역입니다.

| Issue | Cause | Solution |
| :--- | :--- | :--- |
| **Phase 1~2 (Infra & FastAPI Base)** | | |
| **`[WinError 1114]` DLL 초기화 실패** | Windows 환경에서 PyTorch와 C++ 기반 오디오 라이브러리(`ffmpeg` 등)의 환경 변수 및 DLL 충돌. | `python:3.10-slim` 기반의 독립된 **Docker Linux 컨테이너**로 서버 구동 환경을 전면 격리. |
| **Storage Leak (임시 파일 누적)** | API 응답 완료 후 업로드된 원본 및 임시 처리 파일이 디스크에 지속적으로 누적됨. | FastAPI의 **`BackgroundTasks`**와 `finally` 블록을 활용하여, 파이프라인 종료 시 안전하게 파일 시스템을 정리하는 로직 구축. |
| **Phase 3~4 (Architecture & E2E Integration)** | | |
| **네임스페이스 파편화 및 단절** | 레거시 코드와 신규 아키텍처가 `app/main.py`에 혼재되어 동일 함수명 충돌 및 파이프라인 붕괴 유발. | API 컨텍스트와 코어 로직의 의존성을 분리. `src/core/pipeline.py`를 단일 진실 공급원(SSOT)으로 신설. |
| **단일 노드 다중 요청 OOM 다운** | 제한된 VRAM 환경에서 2개 이상의 딥러닝 프로세스가 동시 실행되어 할당량 초과. | **Semaphore**를 통한 락(Lock) 획득 구조와 비동기 폴링 큐잉 도입으로 직렬화(Sequential) 처리. |
| **API Response Data Drop (DTO 누락)** | 백엔드 연산 결과(타브 악보, BPM)가 최종 응답 모델(`TranscriptionResponse`) 필드에 미정의되어 직렬화 시 소실됨. | DTO 스키마에 `bpm` 및 `ascii_tab` 필드를 명시적으로 추가하여 데이터 컨트랙트(Data Contract) 복원. |
| **`[NotImplementedError]` OS 이벤트 루프 충돌** | Windows 환경에서 Uvicorn의 `SelectorEventLoop`가 `asyncio` 서브프로세스 생성을 지원하지 않아 크래시 유발. | 플랫폼 비종속적인 동기 함수 `subprocess.run`을 사용하고, `loop.run_in_executor`를 통해 백그라운드 스레드에 위임하여 OS 락 우회. |
| **Artifact Evaporation (결과물 증발)** | `finally` 블록의 가비지 컬렉션 로직이 처리가 완료된 유효 결과물까지 무차별적으로 삭제함. | 삭제 대상을 '초기 임시 업로드 파일'과 '중간 부산물 트랙'으로 한정하고, 렌더링된 최종 결과물은 보존되도록 로직 세분화. |
| **Phase 5~7 (Output, Stability, DSP Mismatch)** | | |
| **Infinite 404 Polling & Timeout** | 라우터 엔드포인트(`status` vs `tasks`) 및 경로 파편화(`app/outputs/` vs `outputs/`)로 인한 폴링 타임아웃. | 저장소 디렉토리를 루트 `outputs/`로 강제 통합(SSOT)하고, API URL 규약을 프론트엔드와 일치시킴. |
| **Time Desync in Pitch Tracking** | CREPE Chunking 입력 시, 경계 프레임이 중복 적재되어 타임스탬프가 점진적으로 밀리는(Desync) 현상. | 마지막 청크를 제외한 모든 청크 결과물의 마지막 프레임을 기계적으로 절삭(`[:-1]`)하여 슬라이싱 로직 교정. |
| **Massive Note Omission** | 과도한 `fmin` 하향 조정으로 인해 초저역대 럼블 노이즈가 온셋 마스크를 붕괴시킴. | HPF 컷오프를 35Hz, `fmin`을 40Hz의 **Golden State**로 롤백하여 신호 왜곡 방지. |
| **Race Condition in File Cleanup** | 다중 클라이언트 접속 시, 공유 폴더의 임시 파일을 삭제하는 로직이 다른 스레드의 파일을 훼손할 위험 존재. | 각 태스크별 고유 `task_id` 기반의 **샌드박스 환경**을 구축하여 스레드 안전성(Thread-safety) 확보. |
| **Phase 8 (DataOps & Evaluation Infra)** | | |
| **대용량 데이터셋 OOM 및 Storage 부족** | 100GB 압축 파일을 풀고 파이썬 메모리에 적재하여 리샘플링 시 디스크 및 RAM 고갈. | 아카이브를 직접 풀지 않고 메타데이터 스캔 후 FFmpeg 서브프로세스를 호출하여 변환/삭제하는 **2-Pass 스트리밍 아키텍처** 적용. |
| **Windows File Lock 및 삭제 지연** | 스트리밍 변환 후 임시 폴더 통삭제(`shutil.rmtree`) 시, 백그라운드 프로세스의 파일 락(Lock)으로 인한 삭제 실패. | `os.chmod`를 통한 쓰기 권한 강제 부여 및 삭제 재시도(Retry) 헬퍼 로직을 추가하여 I/O 예외 방어. |
| **GT 도메인 왜곡 및 위상 지연** | 정답 악보가 물리 주파수보다 1옥타브 높게 기보되어 있고, Demucs 추론 시 수십 ms의 오디오 위상 지연 발생. | 평가 인프라(`evaluator.py`) 내부 데이터 로더에 옥타브 정규화(`/ 2.0`) 및 상호상관도(Cross-correlation) 기반 위상 동기화 로직 내장. |

---

## 4. Future Works (Roadmap)

다음 단계의 프로젝트 목표입니다.

- [x] **Pydantic Schema & DTO:** E2E 파이프라인 결과를 캡슐화한 `TranscriptionResponse` 모델 구현.
- [x] **Single-node Concurrency (Phase 4):** `Semaphore` 및 `BackgroundTasks`를 활용한 단일 노드 기반 비동기 폴링 큐 구축.
- [x] **Subprocess Isolation (`demucs_runner.py`):** 메모리 누수 방지 및 OS 독립적 프로세스 실행을 위한 스레드 위임 아키텍처 구현.
- [x] **Streamlit Web Demo (MVP):** FastAPI와 통신하여 오디오 플레이어와 악보를 렌더링하는 시각화 클라이언트 완성.
- [x] **Subprocess Isolation & Concurrency Tuning (Phase 7):** Task 샌드박싱 및 VRAM 강제 반환 메커니즘 구축.
- [x] **DataOps Streaming Pipeline (Phase 8):** Slakh2100 데이터셋 2-Pass 스트리밍 추출 및 평가 도메인 정규화 인프라 확립.
- [ ] **Action 1: Baseline F1-Score Quantification (High Priority):** 정규화된 `src/evaluation.py`를 가동하여 양자화 전후(Raw vs Quantized)의 **Onset/Pitch F1-Score 초기 기준값(Baseline)**을 문서화하고 오답을 체계화(Taxonomy).
- [ ] **Action 2: Standard Notation Serialization Engine:** 단순히 텍스트를 출력하는 ASCII 타브를 넘어, **MusicXML 또는 GuitarPro 파일(.gp5)** 포맷을 직접 생성하는 `guitarpro_renderer.py` 구축.
- [ ] **Action 3: Articulation Classification ML:** Slap, Pop, Slide 등의 타현 주법을 태깅하기 위해, 별도의 전처리 없이 딥러닝 임베딩 레이어를 재활용하는 경량 주법 분류기(Transfer Learning) 설계.
- [ ] **Distributed Task Queue:** 단일 노드의 한계를 넘어, Worker 노드 스케일 아웃(Scale-out)이 가능하도록 **Celery + Redis** 기반의 비동기 분산 큐잉 시스템으로 전환.
- [ ] **Storage TTL Cron Job:** 샌드박스에 지속적으로 누적되는 로컬 결과물의 디스크 팽창을 막기 위해, 일정 시간(예: 24시간) 경과 후 자동 삭제하는 TTL(Time-To-Live) 데몬 도입.
