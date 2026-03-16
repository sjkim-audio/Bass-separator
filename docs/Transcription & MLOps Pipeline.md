# 🚀 E2E Bass Transcription & MLOps Pipeline (Final Roadmap)



## Milestone 1. Core E2E Pipeline MVP (도메인 무결성 및 데이터 컨트랙트)
**목표:** 사전 학습된 모델을 활용하여 물리적 타이밍의 손실 없이 오디오 입력부터 최종 데이터 구조체까지 이어지는 핵심 파이프라인을 구축한다.

* **1.1. 추론 아키텍처 확립 (Done):** Demucs(분리) $\rightarrow$ CREPE(피치 추적) $\rightarrow$ 전후처리(Filtering) 파이프라인 통합.
* **1.2. Unquantized 타이밍 및 운지법 디코딩 (Corrected):** * 강제 격자 할당(Quantization) 로직 폐기.
  * Onset Detection 해상도를 밀리초(ms) 단위로 극대화하여 슬랩, 셔플 등 연주의 미세한 타이밍(Micro-timing)을 그대로 보존하는 Unquantized MIDI 추출.
  * 보존된 물리적 시간을 기반으로 Viterbi 최적 운지법 디코딩 수행.
* **1.3. 표준화된 데이터 컨트랙트(DTO) 구현 (Enhanced):**
  * **MLOps 메타데이터 및 정적 서빙 통합:** 파인튜닝 모델 버저닝 추적을 위해 `TranscriptionMetadata` 계층을 신설하고, 클라이언트가 오디오(Bass, MR)와 MIDI 결과물을 즉시 다운로드할 수 있도록 FastAPI 정적 파일 서빙(StaticFiles) URL을 DTO에 내장.
  * **신뢰도(Confidence) 지표 보존:** CREPE 모델의 예측 확률을 보존하여 프론트엔드에서 고스트 노트 및 불확실 구간의 시각적 렌더링(투명도 조절 등)을 지원.
  * **직렬화 오버헤드 방어:** `start_time`, `duration` 등 부동소수점 데이터는 Pydantic `@field_validator`를 통해 소수점 3자리(밀리초)로 강제 반올림하여 Redis 큐 및 네트워크 페이로드 팽창 억제.



## Milestone 2. Asynchronous Serving Infrastructure (비동기 확장성 및 SSE)
**목표:** 대용량 오디오 다중 요청 시 발생하는 병목과 OOM을 완벽히 방어하고, 클라이언트에게 실시간 진행 상태를 스트리밍하는 MSA를 구축한다.



* **2.1. 메시지 브로커 및 Task Queue 일원화:** * FastAPI 서버는 API Gateway 역할만 수행(HTTP 202 반환).
  * 파일 크기와 무관하게 100% 모든 추론 요청을 Redis/Celery 큐로 일원화하여 상태 추적 로직의 파편화 방지.
* **2.2. Priority Queue 기반 워커 최적화:**
  * 1MB 이하의 짧은 오디오를 전담하는 `High-Priority Worker`와 대용량(50MB 이상) 청크(Chunking) 처리를 전담하는 `Heavy-Duty Worker`로 큐를 분리하여 동시성 제어.
  * 좀비 프로세스 방지를 위한 하드/소프트 타임아웃 강제 설정.
* **2.3. SSE (Server-Sent Events) 상태 스트리밍:**
  * Polling의 네트워크 낭비와 WebSocket의 오버스펙을 배제.
  * FastAPI의 `StreamingResponse`를 활용하여 Celery Task의 상태(`PENDING` $\rightarrow$ `PROCESSING: 50%` $\rightarrow$ `SUCCESS`)를 클라이언트에게 단방향으로 푸시(Push)하는 SSE 엔드포인트 구축.

## Milestone 3. Front-End Integration & UX (React 기반 시각화)
**목표:** SSE 스트림을 수신하고 Unquantized 데이터를 클라이언트 단에서 제어할 수 있는 인터랙티브 UI를 배포한다.



* **3.1. React/Vanilla JS 프론트엔드 구축:** Streamlit을 폐기하고, SSE 이벤트를 네이티브하게 수신할 수 있는 웹 아키텍처 도입.
* **3.2. 클라이언트 사이드 렌더링 및 제어:** * 수신된 JSON DTO를 기반으로 인터랙티브 타브 악보 렌더링.
  * 프론트엔드 UI에 '16분음표 스냅(Snap to Grid)' 토글을 구현하여, 사용자가 원할 때만 양자화(Quantization)를 적용할 수 있도록 제어권 이관.
* **3.3. E2E 통합 부하 테스트:** 웹 업로드 $\rightarrow$ Celery 분배 $\rightarrow$ GPU 추론 $\rightarrow$ SSE 진행률 렌더링 사이클 검증.

## Milestone 4. Data-Centric MLOps & Fine-Tuning (모델 품질 고도화)
**목표:** 파이프라인 안정화 이후, 베이스 분리 및 피치 추적의 한계를 돌파하기 위한 데이터 옵스(DataOps)를 수행한다.



* **4.1. 프로그래매틱 데이터 합성:** 타 악기(MR)와 베이스 소스를 시간축 오류 없이 자동 믹싱 및 증강하는 파이프라인 구축.
* **4.2. Training-Serving Skew 방어:** 훈련 데이터 생성 시 서빙 환경과 동일한 Sample Rate 변환 전처리 모듈 강제.
* **4.3. 4-Stem 마스킹 학습 및 실험 추적 (Catastrophic Forgetting 방어):** * 프로덕션 아키텍처와 동일한 4-Stem(`htdemucs`) 모델을 베이스 특화로 파인튜닝하기 위해, 미비된 트랙을 Zero-padding하고 Loss 계산에서 제외(Freezing)하는 부분 최적화(Partial Loss Optimization) 전략 도입.
  * MLflow를 연동하여 하이퍼파라미터 추적 및 최적 가중치 자동 릴리즈 체계 구축.