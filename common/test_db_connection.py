"""
MariaDB 서버 연결(인증)만 테스트하는 스크립트
- 특정 데이터베이스가 없어도 접속/인증 성공 여부만 확인
"""

import pymysql
from sqlalchemy import create_engine, text
from common.config import get_settings
import re

def extract_conn_info(db_url):
    """
    SQLAlchemy 형태의 DB URL에서 접속 정보를 파싱해서 반환
    예: mysql+pymysql://user:pass@host:port/dbname
    """
    m = re.match(
        r"mysql\+pymysql://(?P<user>[^:]+):(?P<password>[^@]+)@(?P<host>[^:/]+):(?P<port>\d+)",
        db_url
    )
    return m.groupdict() if m else None

def test_mariadb_server_connection():
    """
    MariaDB 서버 자체 연결(로그인)만 확인. DB 존재 여부는 무시.
    """
    settings = get_settings()
    conn_info = extract_conn_info(settings.mariadb_auth_url)
    if not conn_info:
        print("❌ DB URL 파싱 실패!")
        return

    try:
        conn = pymysql.connect(
            host=conn_info['host'],
            port=int(conn_info['port']),
            user=conn_info['user'],
            password=conn_info['password'],
            # db 파라미터 생략 (DB명 필요 없음!)
        )
        print(f"✅ MariaDB 서버 연결(로그인) 성공! ({conn_info['host']}:{conn_info['port']})")
        conn.close()
    except Exception as e:
        print(f"❌ MariaDB 서버 연결 실패: {e}")

def test_db_connection():
    """
    .env와 config.py 기반으로 mariadb_auth_url에 DB 연결 시도,
    버전 정보 쿼리 후 결과 출력
    """
    settings = get_settings()
    engine = create_engine(settings.mariadb_auth_url)
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT VERSION();"))
            version = result.scalar()
            print(f"✅ DB 연결 성공! MariaDB/MySQL Version: {version}")
    except Exception as e:
        print(f"❌ DB 연결 실패: {e}")

if __name__ == "__main__":
    test_mariadb_server_connection()
    test_db_connection()
