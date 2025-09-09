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
        # 토큰 형식 기본 검증
        if not token or not isinstance(token, str):
            logger.warning("토큰이 비어있거나 유효하지 않은 형식입니다")
            return None
            
        # 토큰 길이 검증 (JWT는 최소 3개 부분으로 구성)
        token_parts = token.split('.')
        if len(token_parts) != 3:
            logger.warning(f"JWT 토큰 형식이 올바르지 않습니다. 부분 개수: {len(token_parts)}")
            return None
        
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        
        # 토큰 만료 시간 확인
        exp_timestamp = payload.get("exp")
        if exp_timestamp:
            from datetime import datetime, timezone
            exp_datetime = datetime.fromtimestamp(exp_timestamp, tz=timezone.utc)
            now = datetime.now(timezone.utc)
            if exp_datetime < now:
                logger.warning(f"토큰이 만료되었습니다. 만료시간: {exp_datetime}, 현재시간: {now}")
                return None
        
        logger.debug(f"사용자 {payload.get('sub', '알 수 없음')}의 JWT 토큰이 성공적으로 검증되었습니다")
        return payload
    except JWTError as e:
        logger.warning(f"JWT 검증 실패: {type(e).__name__}: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"토큰 검증 중 예상치 못한 오류: {type(e).__name__}: {str(e)}")
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


def is_token_expired(token: str) -> bool:
    """토큰이 만료되었는지 확인"""
    try:
        if not token or not isinstance(token, str):
            return True
            
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        exp_timestamp = payload.get("exp")
        
        if not exp_timestamp:
            logger.warning("토큰에 만료 시간이 설정되지 않았습니다")
            return True
            
        exp_datetime = datetime.fromtimestamp(exp_timestamp, tz=timezone.utc)
        now = datetime.now(timezone.utc)
        
        is_expired = exp_datetime < now
        if is_expired:
            logger.warning(f"토큰이 만료되었습니다. 만료시간: {exp_datetime}, 현재시간: {now}")
        
        return is_expired
        
    except JWTError as e:
        logger.warning(f"토큰 만료 확인 실패: {type(e).__name__}: {str(e)}")
        return True
    except Exception as e:
        logger.error(f"토큰 만료 확인 중 예상치 못한 오류: {type(e).__name__}: {str(e)}")
        return True


def debug_token_info(token: str) -> dict:
    """토큰 디버깅을 위한 정보 반환 (개발/디버깅용)"""
    try:
        if not token or not isinstance(token, str):
            return {"error": "토큰이 비어있거나 유효하지 않은 형식입니다"}
        
        # 토큰 형식 검증
        token_parts = token.split('.')
        if len(token_parts) != 3:
            return {"error": f"JWT 토큰 형식이 올바르지 않습니다. 부분 개수: {len(token_parts)}"}
        
        # 토큰 디코딩 시도
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        
        # 만료 시간 정보
        exp_timestamp = payload.get("exp")
        exp_info = {}
        if exp_timestamp:
            exp_datetime = datetime.fromtimestamp(exp_timestamp, tz=timezone.utc)
            now = datetime.now(timezone.utc)
            exp_info = {
                "expires_at": exp_datetime.isoformat(),
                "is_expired": exp_datetime < now,
                "time_until_expiry": str(exp_datetime - now) if exp_datetime > now else "만료됨"
            }
        
        return {
            "token_format": "valid",
            "user_id": payload.get("sub"),
            "expiration": exp_info,
            "payload_keys": list(payload.keys()),
            "token_length": len(token)
        }
        
    except JWTError as e:
        return {
            "error": f"JWT 디코딩 실패: {type(e).__name__}: {str(e)}",
            "token_format": "invalid"
        }
    except Exception as e:
        return {
            "error": f"예상치 못한 오류: {type(e).__name__}: {str(e)}",
            "token_format": "unknown"
        }
