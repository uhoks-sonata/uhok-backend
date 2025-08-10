from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from common.auth.jwt_handler import verify_token
from common.errors import InvalidTokenException, NotFoundException
from services.user.crud.user_crud import get_user_by_id
from services.user.crud.jwt_blacklist_crud import is_token_blacklisted
from common.database.mariadb_auth import get_maria_auth_db
from common.logger import get_logger

from common.config import get_settings
settings = get_settings()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/user/login")
logger = get_logger("dependencies")

async def get_current_user(
        token: str = Depends(oauth2_scheme),
        db: AsyncSession  = Depends(get_maria_auth_db),
):
    """토큰 기반 사용자 인증 후 유저 정보 반환"""
    try:
        # logger.debug(f"Token verification started: {token[:10]}...")
        
        payload = verify_token(token)
        if payload is None:
            logger.warning("Token verification failed: invalid token")
            raise InvalidTokenException()

        # 토큰이 블랙리스트에 있는지 확인
        if await is_token_blacklisted(db, token):
            logger.warning(f"Token is blacklisted: {token[:10]}...")
            raise InvalidTokenException("로그아웃된 토큰입니다.")

        user_id = payload.get("sub")
        if not user_id:
            logger.warning("Token payload missing user_id")
            raise InvalidTokenException("토큰에 사용자 정보가 없습니다.")

        user = await get_user_by_id(db, user_id)
        if user is None:
            logger.warning(f"User not found for user_id: {user_id}")
            raise NotFoundException("사용자")

        logger.debug(f"User authenticated successfully: user_id={user_id}")
        return user
        
    except Exception as e:
        logger.error(f"Authentication failed: {str(e)}")
        raise
