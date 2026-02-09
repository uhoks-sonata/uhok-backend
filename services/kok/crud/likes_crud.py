from datetime import datetime
from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from services.kok.models.interaction_model import KokLikes
from services.kok.models.product_model import KokPriceInfo, KokProductInfo

from .shared import get_latest_kok_price_id, logger

async def toggle_kok_likes(
    db: AsyncSession,
    user_id: int,
    kok_product_id: int
) -> bool:
    """
    찜 등록/해제 토글
    """
    # logger.info(f"찜 토글 시작: user_id={user_id}, product_id={kok_product_id}")
    
    # 기존 찜 확인
    stmt = select(KokLikes).where(
        KokLikes.user_id == user_id,
        KokLikes.kok_product_id == kok_product_id
    )
    try:
        result = await db.execute(stmt)
        existing_like = result.scalar_one_or_none()
    except Exception as e:
        logger.error(f"찜 상태 확인 SQL 실행 실패: user_id={user_id}, kok_product_id={kok_product_id}, error={str(e)}")
        raise
    
    if existing_like:
        # 찜 해제
        await db.delete(existing_like)
    # logger.info(f"찜 해제 완료: user_id={user_id}, product_id={kok_product_id}")
        return False
    else:
        # 찜 등록
        created_at = datetime.now()
        
        new_like = KokLikes(
            user_id=user_id,
            kok_product_id=kok_product_id,
            kok_created_at=created_at
        )
        
        db.add(new_like)
    # logger.info(f"찜 등록 완료: user_id={user_id}, product_id={kok_product_id}")
        return True


async def get_kok_liked_products(
    db: AsyncSession,
    user_id: int,
    limit: int = 50
) -> List[dict]:
    """
    사용자가 찜한 상품 목록 조회
    """
    stmt = (
        select(KokLikes, KokProductInfo)
        .join(KokProductInfo, KokLikes.kok_product_id == KokProductInfo.kok_product_id)
        .where(KokLikes.user_id == user_id)
        .order_by(KokLikes.kok_created_at.desc())
        .limit(limit)
    )
    
    try:
        results = (await db.execute(stmt)).all()
    except Exception as e:
        logger.error(f"찜한 상품 목록 조회 SQL 실행 실패: user_id={user_id}, limit={limit}, error={str(e)}")
        return []
    
    liked_products = []
    for like, product in results:
        # 최신 가격 정보 조회
        latest_price_id = await get_latest_kok_price_id(db, product.kok_product_id)
        if latest_price_id:
            # 최신 가격 정보로 상세 정보 조회
            price_stmt = select(KokPriceInfo).where(KokPriceInfo.kok_price_id == latest_price_id)
            try:
                price_result = await db.execute(price_stmt)
                price = price_result.scalar_one_or_none()
            except Exception as e:
                logger.warning(f"찜한 상품 가격 정보 조회 실패: kok_product_id={product.kok_product_id}, latest_price_id={latest_price_id}, error={str(e)}")
                price = None
            
            liked_products.append({
                "kok_product_id": product.kok_product_id,
                "kok_product_name": product.kok_product_name,
                "kok_thumbnail": product.kok_thumbnail,
                "kok_product_price": product.kok_product_price,
                "kok_discount_rate": price.kok_discount_rate if price else 0,
                "kok_discounted_price": price.kok_discounted_price if price else product.kok_product_price,
                "kok_store_name": product.kok_store_name,
            })
    
    return liked_products


# -----------------------------
# 장바구니 관련 CRUD 함수
# -----------------------------

