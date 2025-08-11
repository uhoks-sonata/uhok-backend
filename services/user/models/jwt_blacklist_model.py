"""
JWT 토큰 블랙리스트 모델
로그아웃된 토큰을 추적하여 재사용을 방지합니다.
"""

from sqlalchemy import Column, String, DateTime, Text
from sqlalchemy.sql import func
from common.database.base_mariadb import MariaBase


class JWTBlacklist(MariaBase):
    __tablename__ = "JWT_BLACKLIST"
    
    # JWT 토큰의 해시값 (토큰 자체를 저장하지 않음)
    token_hash = Column("TOKEN_HASH", String(255), primary_key=True, index=True)
    
    # 토큰이 블랙리스트에 추가된 시간
    blacklisted_at = Column("BLACKLISTED_AT", DateTime(timezone=True), server_default=func.now())
    
    # 토큰 만료 시간 (JWT의 exp 클레임에서 추출)
    expires_at = Column("EXPIRES_AT", DateTime(timezone=True), nullable=False)
    
    # 사용자 ID (선택적, 로그 추적용)
    user_id = Column("USER_ID", String(36), nullable=True, index=True)
    
    # 추가 메타데이터 (선택적)
    meta_data = Column("METADATA", Text, nullable=True)
