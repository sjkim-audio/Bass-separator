import os
import sys
from dotenv import load_dotenv
from sqlalchemy.pool import NullPool
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

# 로컬 .env 파일 자동 로드 (override=False로 Docker Compose 환경변수 우선순위 보존)
load_dotenv(override=False)

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://sjkim:8721@localhost:5432/bass_db"
)

# 명시적 환경변수 또는 실행 엔트리포인트(celery CLI) 감지를 통한 워커 프로세스 식별
IS_CELERY_WORKER = (
    os.getenv("IS_CELERY_WORKER", "false").lower() == "true"
    or "celery" in os.path.basename(sys.argv[0]).lower()
)

engine_kwargs = {
    "echo": False,
    "future": True,
    "pool_pre_ping": True,  # DB 재시작 또는 유휴 커넥션 끊김 자동 감지 및 복구
}

if IS_CELERY_WORKER:
    # Celery 워커는 매 태스크마다 asyncio.run()으로 루프를 새로 여닫으므로 NullPool 강제
    engine_kwargs["poolclass"] = NullPool
else:
    # FastAPI 서버는 상시 구동되는 단일 이벤트 루프에서 커넥션 풀링 유지
    engine_kwargs.update({
        "pool_size": 5,
        "max_overflow": 10,
        "pool_recycle": 1800,
    })

engine = create_async_engine(DATABASE_URL, **engine_kwargs)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)

async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
