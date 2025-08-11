"""
PostgreSQL 로그 DB 세션 (log_db)
"""
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from common.config import get_settings
from common.logger import get_logger

logger = get_logger("postgres_log")

settings = get_settings()
engine = create_async_engine(settings.postgres_log_url, echo=settings.debug)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

logger.info(f"PostgreSQL Log 엔진 생성됨, URL: {settings.postgres_log_url}")
logger.info(f"디버그 모드: {settings.debug}")

async def get_postgres_log_db() -> AsyncGenerator[AsyncSession, None]:
    """PostgreSQL 로그용 세션 반환"""
    logger.debug("PostgreSQL 로그 데이터베이스 세션 생성 중")
    async with SessionLocal() as session:
        logger.debug("PostgreSQL 로그 데이터베이스 세션 생성 완료")
        yield session
    logger.debug("PostgreSQL 로그 데이터베이스 세션 종료됨")
