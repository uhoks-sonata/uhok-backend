"""
DB 연결 및 세션 관리
"""

from sqlalchemy import create_engine  # DB 엔진(연결 객체) 생성 함수 임포트
from sqlalchemy.ext.declarative import declarative_base  # ORM Base 클래스 생성 함수 임포트
from sqlalchemy.orm import sessionmaker  # 세션 팩토리 함수 임포트
from common.config import get_settings  # 환경변수/설정 정보 불러오는 함수 임포트

settings = get_settings()  # .env 등에서 설정 불러오기 (DB URL 등)

engine = create_engine(settings.mariadb_auth_url, pool_pre_ping=True)  # MariaDB 엔진(연결) 생성, 커넥션 재사용 및 연결 끊김 자동 감지
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)  # DB 세션 팩토리, 트랜잭션 단위 제어 (commit 직접)
Base = declarative_base()  # ORM 모델의 부모 클래스 (모든 ORM 모델이 이걸 상속)

def get_db():
    """
    DB 세션(트랜잭션) 생성 및 반환 (FastAPI DI 용)
    - 요청 처리 동안 세션 제공, 요청 끝나면 자동 close
    """
    db = SessionLocal()  # 세션 인스턴스 생성
    try:
        yield db         # 의존성 주입으로 세션 제공 (with문 처럼 동작)
    finally:
        db.close()       # 요청 끝나면 세션 자원 반납 (커넥션 close)
