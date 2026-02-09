"""JWT blacklist maintenance CRUD functions."""

from datetime import datetime

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from common.logger import get_logger
from services.user.models.jwt_blacklist_model import JWTBlacklist

logger = get_logger("jwt_blacklist_crud")


async def cleanup_expired_tokens(db: AsyncSession) -> int:
    """만료된 토큰들을 블랙리스트에서 제거."""
    try:
        now = datetime.utcnow()
        result = await db.execute(delete(JWTBlacklist).where(JWTBlacklist.expires_at < now))

        await db.commit()
        cleaned_count = result.rowcount

        if cleaned_count > 0:
            logger.info(f"Cleaned up {cleaned_count} expired tokens from blacklist")

        return cleaned_count
    except Exception as e:
        logger.error(f"Failed to cleanup expired tokens: {str(e)}")
        await db.rollback()
        raise
