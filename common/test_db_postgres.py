"""
비동기 PostgreSQL 연결 및 버전 정보 조회 테스트 코드
"""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from common.config import get_settings
from common.logger import get_logger

logger = get_logger("test_db_postgres")

async def test_async_postgres_connection():
    """
    비동기(PostgreSQL) 엔진으로 DB 연결 및 버전 정보 조회
    """
    settings = get_settings()
    engine = create_async_engine(settings.postgres_recommend_url, echo=True)

    try:
        async with engine.connect() as conn:  # type: AsyncConnection
            result = await conn.execute(text("SELECT version();"))
            version = result.scalar_one()
            logger.info(f"✅ 비동기 DB 연결 성공! PostgreSQL Version: {version}")
    except Exception as e:
        logger.error(f"❌ 비동기 DB 연결 실패: {e}")
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(test_async_postgres_connection())
