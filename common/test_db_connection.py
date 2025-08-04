"""
비동기 MariaDB 서버 연결(인증) 및 버전 정보 조회 테스트 코드
"""

import asyncio
import asyncmy
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy import text
from common.config import get_settings
import re

def extract_conn_info(db_url):
    """
    SQLAlchemy 형태의 DB URL에서 접속 정보를 파싱해서 반환
    예: mysql+aiomysql://user:pass@host:port/dbname
    """
    m = re.match(
        r"mysql\+(aiomysql|pymysql|asyncmy)://(?P<user>[^:]+):(?P<password>[^@]+)@(?P<host>[^:/]+):(?P<port>\d+)(/(?P<dbname>[^?]+))?",
        db_url
    )

    return m.groupdict() if m else None

async def test_mariadb_server_connection_async():
    """
    비동기 MariaDB 서버 자체 연결(로그인)만 확인. DB 존재 여부는 무시.
    """
    settings = get_settings()
    conn_info = extract_conn_info(settings.mariadb_auth_url)
    if not conn_info:
        print("❌ DB URL 파싱 실패!")
        return

    try:
        conn = await asyncmy.connect(
            host=conn_info['host'],
            port=int(conn_info['port']),
            user=conn_info['user'],
            password=conn_info['password'],
            # db 파라미터 생략 (DB명 필요 없음!)
        )
        print(f"✅ 비동기 MariaDB 서버 연결(로그인) 성공! ({conn_info['host']}:{conn_info['port']})")
        conn.close()
    except Exception as e:
        print(f"❌ 비동기 MariaDB 서버 연결 실패: {e}")

async def test_db_connection_async():
    """
    .env와 config.py 기반으로 mariadb_auth_url에 DB 연결 시도,
    버전 정보 쿼리 후 결과 출력 (비동기)
    """
    settings = get_settings()
    engine = create_async_engine(settings.mariadb_auth_url, echo=True)

    try:
        async with engine.connect() as conn:  # type: AsyncConnection
            result = await conn.execute(text("SELECT VERSION();"))
            version = result.scalar_one()
            print(f"✅ 비동기 DB 연결 성공! MariaDB/MySQL Version: {version}")
    except Exception as e:
        print(f"❌ 비동기 DB 연결 실패: {e}")
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(test_mariadb_server_connection_async())
    asyncio.run(test_db_connection_async())
