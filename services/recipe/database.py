"""
레시피 서비스 전용 DB 세션 및 엔진 관리 모듈
- 비동기 SQLAlchemy (async_engine, AsyncSession) 지원
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from common.config import get_settings

settings = get_settings()

# 비동기 엔진 생성
engine = create_async_engine(
    settings.mariadb_service_url,
    echo=False,  # 개발/디버깅시 True로
    future=True
)

# 비동기 세션 팩토리
AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)

async def get_db():
    """
    FastAPI dependency로 사용하는 비동기 DB 세션 생성/종료 함수
    """
    async with AsyncSessionLocal() as session:
        yield session
