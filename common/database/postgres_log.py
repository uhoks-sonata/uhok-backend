"""
PostgreSQL 로그 DB 세션 (log_db)
"""
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from common.config import get_settings

settings = get_settings()
engine = create_async_engine(settings.postgres_log_url, echo=settings.debug)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def get_postgres_log_db() -> AsyncGenerator[AsyncSession, None]:
    """PostgreSQL 로그용 세션 반환"""
    async with SessionLocal() as session:
        yield session
