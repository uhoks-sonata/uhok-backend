"""JWT blacklist write CRUD functions."""

import hashlib
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from common.logger import get_logger
from services.user.models.jwt_blacklist_model import JWTBlacklist

logger = get_logger("jwt_blacklist_crud")


async def add_token_to_blacklist(
    db: AsyncSession,
    token: str,
    expires_at: datetime,
    user_id: str = None,
    metadata: str = None,
) -> JWTBlacklist:
    """토큰을 블랙리스트에 추가."""
    try:
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        blacklisted_token = JWTBlacklist(
            token_hash=token_hash,
            expires_at=expires_at,
            user_id=user_id,
            metadata=metadata,
        )

        db.add(blacklisted_token)
        await db.commit()
        await db.refresh(blacklisted_token)
        return blacklisted_token
    except Exception as e:
        logger.error(f"토큰을 블랙리스트에 추가하는데 실패했습니다: {str(e)}")
        await db.rollback()
        raise
