"""
JWT 토큰 생성 및 검증을 담당하는 유틸 모듈
"""

from datetime import datetime, timedelta
from jose import jwt, JWTError
from common.config import get_settings

settings = get_settings()  # 설정 캐싱된 인스턴스 불러오기

def create_access_token(data: dict):
    """JWT 액세스 토큰 생성"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)

def verify_token(token: str):
    """JWT 토큰 검증 및 payload 반환"""
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        return payload
    except JWTError:
        return None
