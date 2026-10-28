import os
from celery import Celery

# 윈도우 및 리눅스 환경의 OpenMP 라이브러리 중복 로드 충돌 방지
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

# 로컬 네이티브(localhost) 및 Docker(redis) 환경 이원화 지원
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "bass_transcription_worker",
    broker=CELERY_BROKER_URL,
)

celery_app.conf.update(
    # 직렬화 보안 및 규격 통일
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # 상태 및 메타데이터 영속성은 PostgreSQL(SSOT)이 전담하므로 Redis 결과 저장 비활성화
    task_ignore_result=True,
    # 단일 GPU 워커 보호: 한 번에 1개의 태스크만 가져오며, 작업 완료 후 ACK 전송
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    broker_connection_retry_on_startup=True,
)


@celery_app.task(name="worker.ping")
def ping_worker() -> str:
    """브로커-워커 간 연결 무결성 검증을 위한 헬스체크 태스크"""
    print("⚡ [Celery Worker] Ping 수신 완료 - 워커가 정상 대기 중입니다.")
    return "pong"
