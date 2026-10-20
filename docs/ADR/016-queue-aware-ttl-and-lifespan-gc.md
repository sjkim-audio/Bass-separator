# [ADR-016] 스토리지 OOS 방어를 위한 Queue-Aware TTL 및 Lifespan 가비지 컬렉션

* **Status:** Accepted
* **Date:** 2026-09-02 (Retroactively Documented for Pre-Phase 9)
* **Category:** Backend-Infra / Resource Management
* **Related Documents:** [Backend_devlog.md](../devlogs/Backend_devlog.md)

## 1. Context (배경)

Phase 7에서 다중 요청의 파일 I/O 충돌을 막기 위해 고유 `task_id` 기반의 샌드박스 격리 디렉토리를 도입했다. 하지만 추출이 완료된 오디오(`bass.wav`, `bassless.wav`)와 악보 파일이 서버 디스크(`outputs/`)에 지속적으로 누적됨에 따라, 장기 가동 시 호스트 머신의 스토리지 고갈(OOS, Out of Storage) 위험이 발생했다[cite: 1].

이를 해결하기 위해 단순 타이머(TTL) 기반의 자동 삭제를 도입하려 했으나 두 가지 엣지 케이스가 발견되었다.
1. **큐 지연에 의한 조기 삭제 (Premature Deletion):** 파일 업로드 직후부터 카운트다운을 시작할 경우, 앞선 사용자의 GPU 연산 때문에 세마포어(Semaphore) 대기열에 오래 머문 작업은 추론이 채 끝나기도 전에 샌드박스가 통째로 삭제되어 시스템 크래시를 유발한다[cite: 1].
2. **메모리 휘발에 따른 고아 데이터 (Zombie Task):** FastAPI의 `BackgroundTasks`나 `asyncio.sleep` 기반의 타이머는 컨테이너 재시작이나 강제 종료 시 메모리에서 증발한다[cite: 1]. 이로 인해 삭제 스케줄이 유실된 폴더들은 영구적인 고아(Zombie) 상태로 디스크에 방치된다[cite: 1].

## 2. Decision (결정)

안전한 스토리지 생명주기 관리를 위해 다음 두 가지 가비지 컬렉션(GC) 메커니즘을 이중으로 적용한다.

1. **Queue-Aware TTL 적용:** 카운트다운 트리거를 API 진입점이 아닌, GPU 추론 연산이 모두 끝나고 세마포어 락(Lock)을 해제한 직후인 `run_pipeline_task`의 `finally` 블록에서 가동한다[cite: 1]. (기본값: 완료 후 1시간 뒤 삭제[cite: 1])
2. **FastAPI Lifespan GC 도입:** 서버 부팅 시점에 단 한 번 실행되는 `@asynccontextmanager lifespan` 훅을 활용한다[cite: 1]. 서버 기동 시 즉각적으로 `outputs/` 디렉토리 전체를 스캔하고, 파일 수정 시간(`os.path.getmtime`)이 1시간을 초과한 낡은 폴더를 강제 삭제(Clean-up)한다[cite: 1].

## 3. Rationale (의사결정 근거)

### 3.1. 대기열(Queue) 오버헤드 보상
타이머의 시작점을 '작업 완료 시점'으로 지연시킴으로써, 서버 부하(동시 접속)가 아무리 심하더라도 클라이언트는 연산 완료 후 보장된 시간(1시간) 동안 안전하게 파일을 다운로드할 수 있다. 이는 인프라의 처리량 한계가 사용자 경험 훼손(다운로드 링크 증발)으로 이어지는 것을 방어한다.

### 3.2. 상태 무결성 복구 (Self-healing)
메모리 기반의 비동기 타이머는 근본적으로 런타임 종속적이다. Lifespan GC는 서버 프로세스가 비정상 종료되더라도, 다음 재부팅 시 물리적 디스크 상태를 점검하여 시스템의 스토리지 무결성을 스스로 복구(Self-healing)하는 가장 경제적이고 확실한 안전장치다[cite: 1].

## 4. Consequences (결과)

* **Positive:**
    * 장기 가동 환경에서도 `outputs/` 디렉토리의 용량 팽창이 완벽히 통제된다.
    * 대기열 병목 상태에서도 파일 다운로드 안정성이 보장된다.
* **Negative & Limitations:**
    * 서버 부팅 시 디스크 I/O 탐색(`os.listdir`, `getmtime`)이 발생하므로, 누적된 파일이 극단적으로 많을 경우 런타임 초기화가 수 초 지연될 수 있다[cite: 1]. 단, 현재 서비스 규모에서는 무시할 수 있는 수준이다.
