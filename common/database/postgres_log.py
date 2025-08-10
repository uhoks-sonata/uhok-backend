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

logger.info(f"PostgreSQL Log engine created with URL: {settings.postgres_log_url}")
logger.info(f"Debug mode: {settings.debug}")

async def get_postgres_log_db() -> AsyncGenerator[AsyncSession, None]:
    """PostgreSQL 로그용 세션 반환"""
    logger.debug("Creating PostgreSQL log database session")
    async with SessionLocal() as session:
        logger.debug("PostgreSQL log database session created successfully")
        yield session
    logger.debug("PostgreSQL log database session closed")
