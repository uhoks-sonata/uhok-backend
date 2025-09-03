"""
JWT 블랙리스트 CRUD 작업
"""

import hashlib
from datetime import datetime
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from common.logger import get_logger

from services.user.models.jwt_blacklist_model import JWTBlacklist

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
        logger.error(f"토큰을 블랙리스트에 추가하는데 실패했습니다: {str(e)}")
        await db.rollback()
        raise


async def is_token_blacklisted(db: AsyncSession, token: str) -> bool:
    """토큰이 블랙리스트에 있는지 확인"""
    try:
        # 토큰 유효성 기본 검증
        if not token or not isinstance(token, str):
            logger.warning("블랙리스트 확인: 토큰이 비어있거나 유효하지 않은 형식입니다")
            return False
            
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        
        # 만료된 토큰도 함께 확인하여 정확한 상태 파악
        from datetime import datetime
        now = datetime.utcnow()
        
        result = await db.execute(
            select(JWTBlacklist).where(
                JWTBlacklist.token_hash == token_hash,
                JWTBlacklist.expires_at > now  # 아직 만료되지 않은 블랙리스트 토큰만 확인
            )
        )
        
        blacklisted_token = result.scalar_one_or_none()
        is_blacklisted = blacklisted_token is not None
        
        if is_blacklisted:
            logger.warning(f"토큰이 블랙리스트에 등록되어 있습니다: {token_hash[:10]}..., 만료시간: {blacklisted_token.expires_at}")
        else:
            logger.debug(f"토큰이 블랙리스트에 없습니다: {token_hash[:10]}...")
        
        return is_blacklisted
        
    except Exception as e:
        logger.error(f"토큰 블랙리스트 확인 중 오류 발생: {str(e)}")
        # 오류 발생 시 보안을 위해 토큰을 차단하지 않음 (인증은 다른 방식으로 처리)
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
