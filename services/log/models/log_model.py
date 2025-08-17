"""
USER_LOG (PostgreSQL) ORM 모델
- DB 테이블/컬럼명은 대문자, Python 변수는 소문자
"""
from sqlalchemy import Column, Integer, String, DateTime, JSON, text
from common.database.base_postgres import PostgresBase

class UserLog(PostgresBase):
    """
    USER_LOG 테이블의 ORM 모델 (PostgreSQL)
    """
    __tablename__ = "USER_LOG"  # 테이블명 대문자

    log_id = Column("LOG_ID", Integer, primary_key=True, autoincrement=True, comment="로그 ID")                   # 컬럼명 대문자
    user_id = Column("USER_ID", Integer, nullable=True, index=True, comment="사용자 ID")
    event_type = Column("EVENT_TYPE", String(50), nullable=False, comment="이벤트 유형")
    event_data = Column("EVENT_DATA", JSON, nullable=True, comment="이벤트 상세 데이터(JSON)")
    created_at = Column("CREATED_AT", DateTime, nullable=False, server_default=text('NOW()'), comment="이벤트 발생 시각")
