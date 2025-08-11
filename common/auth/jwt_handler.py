"""
JWT 토큰 생성 및 검증 함수
"""
from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
from common.config import get_settings
from common.logger import get_logger

settings = get_settings()
logger = get_logger("jwt_handler")

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """JWT 액세스 토큰 생성"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    logger.info(f"사용자 {data.get('sub', '알 수 없음')}에 대한 액세스 토큰이 생성되었습니다")
    return encoded_jwt


def verify_token(token: str):
    """JWT 토큰 검증 및 payload 반환"""
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        # logger.debug(f"사용자 {payload.get('sub', '알 수 없음')}의 JWT 토큰이 성공적으로 검증되었습니다")
        return payload
    except JWTError as e:
        logger.debug(f"JWT 검증 실패: {repr(e)}")
        return None


def get_token_expiration(token: str) -> Optional[datetime]:
    """토큰의 만료 시간 반환"""
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        exp_timestamp = payload.get("exp")
        if exp_timestamp:
            return datetime.fromtimestamp(exp_timestamp, tz=timezone.utc)
        return None
    except JWTError as e:
        logger.debug(f"토큰 만료 시간 조회 실패: {repr(e)}")
        return None


def extract_user_id_from_token(token: str) -> Optional[str]:
    """토큰에서 사용자 ID 추출"""
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        return payload.get("sub")
    except JWTError as e:
        logger.debug(f"토큰에서 사용자 ID 추출 실패: {repr(e)}")
        return None
