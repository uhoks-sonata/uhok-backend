"""
DB 연결 및 비동기 세션 관리 (Async)
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from common.config import get_settings

settings = get_settings()

# 비동기용 MariaDB 엔진 생성 (asyncmy 사용)
engine = create_async_engine(
    settings.mariadb_auth_url,
    pool_pre_ping=True,
    echo=False  # 필요에 따라 True (SQL 로그)
)

# 비동기 세션 팩토리 생성
AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)

# ORM Base 클래스
Base = declarative_base()

async def get_db():
    """
    비동기 DB 세션(트랜잭션) 생성 및 반환 (FastAPI DI 용)
    - 요청 처리 동안 세션 제공, 요청 끝나면 자동 close
    """
    async with AsyncSessionLocal() as session:
        yield session  # 비동기 컨텍스트로 세션 제공
