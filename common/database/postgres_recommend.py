"""
PostgreSQL 추천 DB 세션 (recommend_db)
"""
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from common.config import get_settings
from common.logger import get_logger

logger = get_logger("postgres_recommend")

settings = get_settings()
engine = create_async_engine(settings.postgres_recommend_url, echo=False)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

logger.info(f"PostgreSQL Recommend 엔진 생성됨, URL: {settings.postgres_recommend_url}")
logger.info(f"디버그 모드: {settings.debug}")

async def get_postgres_recommend_db() -> AsyncGenerator[AsyncSession, None]:
    """PostgreSQL 추천용 세션 반환"""
    logger.debug("PostgreSQL 추천 데이터베이스 세션 생성 중")
    async with SessionLocal() as session:
        logger.debug("PostgreSQL 추천 데이터베이스 세션 생성 완료")
        yield session
    logger.debug("PostgreSQL 추천 데이터베이스 세션 종료됨")
