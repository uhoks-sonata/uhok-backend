from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from common.auth.jwt_handler import verify_token
from common.errors import InvalidTokenException, NotFoundException
from services.user.crud.user_crud import get_user_by_id
from services.user.database import get_maria_auth_db

from common.config import get_settings
settings = get_settings()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/user/login")

async def get_current_user(
        token: str = Depends(oauth2_scheme),
        db: AsyncSession  = Depends(get_maria_auth_db),
):
    """토큰 기반 사용자 인증 후 유저 정보 반환"""
    # print(f"[DEBUG] Incoming token: {token}")
    # print("dependencies.py settings.jwt_secret:", settings.jwt_secret)

    payload = verify_token(token)
    # print(f"[DEBUG] Decoded payload: {payload}")
    if payload is None:
        raise InvalidTokenException()

    user_id = payload.get("sub")
    user = await  get_user_by_id(db, user_id)
    if user is None:
        raise NotFoundException("사용자")

    return user
