"""
MariaDB 인증 관련 DB 세션 (auth_db)
"""
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from common.config import get_settings
from common.logger import get_logger

logger = get_logger("mariadb_auth", sqlalchemy_logging={'enable': False})

settings = get_settings()
engine = create_async_engine(settings.mariadb_auth_url, echo=settings.debug)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

logger.info(f"MariaDB Auth 엔진 생성됨, URL: {settings.mariadb_auth_url}")
logger.info(f"디버그 모드: {settings.debug}")

async def get_maria_auth_db() -> AsyncGenerator[AsyncSession, None]:
    """MariaDB 인증용 세션 반환"""
    logger.debug("MariaDB 인증 데이터베이스 세션 생성 중")
    async with SessionLocal() as session:
        logger.debug("MariaDB 인증 데이터베이스 세션 생성 완료")
        yield session
    logger.debug("MariaDB 인증 데이터베이스 세션 종료됨")
