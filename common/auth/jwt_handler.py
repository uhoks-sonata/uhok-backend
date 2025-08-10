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
    # sub을 str로 강제 변환
    ## JWT 표준 스펙에선 sub가 **반드시 문자열(str)**이어야 함.
    if "sub" in to_encode:
        to_encode["sub"] = str(to_encode["sub"])
    expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)

def verify_token(token: str):
    """JWT 토큰 검증 및 payload 반환"""
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        # print("jwt_handler.py  settings.jwt_secret:", settings.jwt_secret)
        # print(payload)
        return payload
    except JWTError as e:
        print("[DEBUG] JWTError 발생:", repr(e))
        return None

def get_token_expiration(token: str) -> datetime:
    """JWT 토큰의 만료 시간을 반환"""
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        exp_timestamp = payload.get("exp")
        if exp_timestamp:
            return datetime.fromtimestamp(exp_timestamp)
        return None
    except JWTError:
        return None

def extract_user_id_from_token(token: str) -> str:
    """JWT 토큰에서 사용자 ID를 추출"""
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        return payload.get("sub")
    except JWTError:
        return None
