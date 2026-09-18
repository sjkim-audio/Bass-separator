import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

# 개발 환경을 위한 기본 URL (추후 .env 연동)
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://user:password@localhost:5432/bass_db")

# 비동기 엔진 생성 (커넥션 풀링 최적화)
engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    future=True,
    pool_size=5,
    max_overflow=10,
    pool_recycle=1800, # 30분마다 커넥션 재생성 (DB 킬 방어)
)

# 세션 팩토리 생성
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)

# FastAPI 의존성 주입(DI)을 위한 세션 제너레이터
async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
