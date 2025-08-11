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

logger.info(f"MariaDB Service 엔진 생성됨, URL: {settings.mariadb_service_url}")
logger.info(f"디버그 모드: {settings.debug}")

async def get_maria_service_db() -> AsyncGenerator[AsyncSession, None]:
    """MariaDB 서비스용 세션 반환"""
    logger.debug("MariaDB 서비스 데이터베이스 세션 생성 중")
    async with SessionLocal() as session:
        logger.debug("MariaDB 서비스 데이터베이스 세션 생성 완료")
        yield session
    logger.debug("MariaDB 서비스 데이터베이스 세션 종료됨")
