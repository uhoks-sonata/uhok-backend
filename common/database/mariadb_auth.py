"""
MariaDB 인증 관련 DB 세션 (auth_db)
"""
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from common.config import get_settings
from common.logger import get_logger

logger = get_logger("mariadb_auth")

settings = get_settings()
engine = create_async_engine(settings.mariadb_auth_url, echo=settings.debug)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

logger.info(f"MariaDB Auth engine created with URL: {settings.mariadb_auth_url}")
logger.info(f"Debug mode: {settings.debug}")

async def get_maria_auth_db() -> AsyncGenerator[AsyncSession, None]:
    """MariaDB 인증용 세션 반환"""
    logger.debug("Creating MariaDB auth database session")
    async with SessionLocal() as session:
        logger.debug("MariaDB auth database session created successfully")
        yield session
    logger.debug("MariaDB auth database session closed")
