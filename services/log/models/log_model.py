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
    __tablename__ = "USER_LOG"

    log_id = Column("LOG_ID", Integer, primary_key=True, autoincrement=True, comment="로그 ID")
    user_id = Column("USER_ID", Integer, nullable=True, index=True, comment="사용자 ID")
    event_type = Column("EVENT_TYPE", String(50), nullable=False, comment="이벤트 유형")
    event_data = Column("EVENT_DATA", JSON, nullable=True, comment="이벤트 상세 데이터(JSON)")
    created_at = Column("CREATED_AT", DateTime, nullable=False, server_default=text('NOW()'), comment="이벤트 발생 시각")
    
    # HTTP 관련 컬럼들
    http_method = Column("HTTP_METHOD", String(10), nullable=True, comment="HTTP 메서드 (GET, POST, PUT, DELETE 등)")
    api_url = Column("API_URL", String(500), nullable=True, comment="API 엔드포인트 URL")
    request_time = Column("REQUEST_TIME", DateTime, nullable=True, comment="API 요청 시작 시간")
    response_time = Column("RESPONSE_TIME", DateTime, nullable=True, comment="API 응답 완료 시간")
    response_code = Column("RESPONSE_CODE", Integer, nullable=True, comment="HTTP 응답 상태 코드 (200, 404, 500 등)")
    client_ip = Column("CLIENT_IP", String(45), nullable=True, comment="요청자 IP 주소 (IPv4/IPv6 지원)")
    