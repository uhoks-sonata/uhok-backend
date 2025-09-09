"""
MariaDB 서비스 전반 DB 세션 (service_db)
"""
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from common.config import get_settings
from common.logger import get_logger

logger = get_logger("mariadb_service")

settings = get_settings()
engine = create_async_engine(
    settings.mariadb_service_url, 
    echo=False,
    pool_size=20,  # 연결 풀 크기 증가
    max_overflow=30,  # 최대 오버플로우 연결
    pool_pre_ping=True,  # 연결 상태 확인
    pool_recycle=3600,  # 1시간마다 연결 재생성
    connect_args={
        "connect_timeout": 10,  # 연결 타임아웃
        "read_timeout": 30,  # 읽기 타임아웃
        "autocommit": True,  # 자동 커밋
    }
)
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
