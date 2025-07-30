# dependencies.py
"""
FastAPI 의존성 주입용 공통 함수들 정의 (ex: 인증된 사용자)
"""
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from common.auth.jwt_handler import verify_token
from common.errors import InvalidTokenException
from services.user.services.user_service import get_user_by_id

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/user/login")

def get_current_user(token: str = Depends(oauth2_scheme)):
    """토큰 기반 사용자 인증 후 유저 정보 반환"""
    payload = verify_token(token)
    if payload is None:
        raise InvalidTokenException()
    user_id = payload.get("sub")
    return get_user_by_id(user_id)
