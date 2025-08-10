"""
JWT 블랙리스트 CRUD 작업
"""

import hashlib
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from services.user.models.jwt_blacklist_model import JWTBlacklist
from common.logger import get_logger

logger = get_logger("jwt_blacklist_crud")


async def add_token_to_blacklist(
    db: AsyncSession, 
    token: str, 
    expires_at: datetime, 
    user_id: str = None,
    metadata: str = None
) -> JWTBlacklist:
    """토큰을 블랙리스트에 추가"""
    try:
        # 토큰의 해시값 생성 (보안을 위해 토큰 자체는 저장하지 않음)
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        
        blacklisted_token = JWTBlacklist(
            token_hash=token_hash,
            expires_at=expires_at,
            user_id=user_id,
            metadata=metadata
        )
        
        db.add(blacklisted_token)
        await db.commit()
        await db.refresh(blacklisted_token)
        
        logger.info(f"Token added to blacklist: user_id={user_id}, metadata={metadata}")
        return blacklisted_token
        
    except Exception as e:
        logger.error(f"Failed to add token to blacklist: {str(e)}")
        await db.rollback()
        raise


async def is_token_blacklisted(db: AsyncSession, token: str) -> bool:
    """토큰이 블랙리스트에 있는지 확인"""
    try:
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        
        result = await db.execute(
            select(JWTBlacklist).where(JWTBlacklist.token_hash == token_hash)
        )
        
        is_blacklisted = result.scalar_one_or_none() is not None
        if is_blacklisted:
            logger.debug(f"Token found in blacklist: {token_hash[:10]}...")
        
        return is_blacklisted
        
    except Exception as e:
        logger.error(f"Failed to check token blacklist status: {str(e)}")
        return False


async def cleanup_expired_tokens(db: AsyncSession) -> int:
    """만료된 토큰들을 블랙리스트에서 제거"""
    try:
        now = datetime.utcnow()
        
        result = await db.execute(
            delete(JWTBlacklist).where(JWTBlacklist.expires_at < now)
        )
        
        await db.commit()
        cleaned_count = result.rowcount
        
        if cleaned_count > 0:
            logger.info(f"Cleaned up {cleaned_count} expired tokens from blacklist")
        
        return cleaned_count
        
    except Exception as e:
        logger.error(f"Failed to cleanup expired tokens: {str(e)}")
        await db.rollback()
        raise


# async def get_blacklist_stats(db: AsyncSession) -> dict:
#     """블랙리스트 통계 정보 반환"""
#     # 전체 블랙리스트된 토큰 수
#     total_result = await db.execute(select(JWTBlacklist))
#     total_tokens = len(total_result.scalars().all())
    
#     # 만료된 토큰 수
#     now = datetime.utcnow()
#     expired_result = await db.execute(
#         select(JWTBlacklist).where(JWTBlacklist.expires_at < now)
#     )
#     expired_tokens = len(expired_result.scalars().all())
    
#     return {
#         "total_blacklisted_tokens": total_tokens,
#         "expired_tokens": expired_tokens,
#         "active_blacklisted_tokens": total_tokens - expired_tokens
#     }
