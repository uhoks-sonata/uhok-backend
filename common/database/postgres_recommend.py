"""
PostgreSQL 추천 DB 세션 (recommend_db)
"""
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from common.config import get_settings

settings = get_settings()
engine = create_async_engine(settings.postgres_recommend_url, echo=settings.debug)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def get_postgres_recommend_db() -> AsyncGenerator[AsyncSession, None]:
    """PostgreSQL 추천용 세션 반환"""
    async with SessionLocal() as session:
        yield session
