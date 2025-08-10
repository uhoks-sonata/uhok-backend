"""
MariaDB 서비스 전반 DB 세션 (service_db)
"""
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from common.config import get_settings
from common.logger import get_logger

logger = get_logger("mariadb_service")

settings = get_settings()
engine = create_async_engine(settings.mariadb_service_url, echo=settings.debug)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

logger.info(f"MariaDB Service engine created with URL: {settings.mariadb_service_url}")
logger.info(f"Debug mode: {settings.debug}")

async def get_maria_service_db() -> AsyncGenerator[AsyncSession, None]:
    """MariaDB 서비스용 세션 반환"""
    logger.debug("Creating MariaDB service database session")
    async with SessionLocal() as session:
        logger.debug("MariaDB service database session created successfully")
        yield session
    logger.debug("MariaDB service database session closed")
