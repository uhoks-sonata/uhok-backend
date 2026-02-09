"""JWT blacklist query CRUD functions."""

import hashlib
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.logger import get_logger
from services.user.models.jwt_blacklist_model import JWTBlacklist

logger = get_logger("jwt_blacklist_crud")


async def is_token_blacklisted(db: AsyncSession, token: str) -> bool:
    """토큰이 블랙리스트에 있는지 확인."""
    try:
        if not token or not isinstance(token, str):
            logger.warning("블랙리스트 확인: 토큰이 비어있거나 유효하지 않은 형식입니다")
            return False

        token_hash = hashlib.sha256(token.encode()).hexdigest()
        now = datetime.utcnow()

        result = await db.execute(
            select(JWTBlacklist).where(
                JWTBlacklist.token_hash == token_hash,
                JWTBlacklist.expires_at > now,
            )
        )

        blacklisted_token = result.scalar_one_or_none()
        is_blacklisted = blacklisted_token is not None

        if is_blacklisted:
            logger.warning(
                f"토큰이 블랙리스트에 등록되어 있습니다: {token_hash[:10]}..., 만료시간: {blacklisted_token.expires_at}"
            )
        else:
            logger.debug(f"토큰이 블랙리스트에 없습니다: {token_hash[:10]}...")

        return is_blacklisted
    except Exception as e:
        logger.error(f"토큰 블랙리스트 확인 중 오류 발생: {str(e)}")
        return False
