"""Order image support CRUD functions."""

from __future__ import annotations

from typing import Dict, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.logger import get_logger
from services.kok.models.product_model import KokImageInfo
from services.homeshopping.models.core_model import HomeshoppingImgUrl

logger = get_logger("order_crud")

async def _batch_fetch_kok_images(db: AsyncSession, product_ids: List[int]) -> Dict[int, str]:
    """
    콕 상품 이미지를 배치로 조회 (성능 최적화)
    
    Args:
        db: 데이터베이스 세션
        product_ids: 조회할 상품 ID 목록
    
    Returns:
        Dict[int, str]: product_id를 키로 하는 이미지 URL
    """
    if not product_ids:
        return {}
    
    # 각 상품의 첫 번째 이미지를 한 번에 조회
    stmt = (
        select(KokImageInfo.kok_product_id, KokImageInfo.kok_img_url)
        .where(KokImageInfo.kok_product_id.in_(product_ids))
        .distinct(KokImageInfo.kok_product_id)
        .order_by(KokImageInfo.kok_product_id, KokImageInfo.sort_order)
    )
    
    result = await db.execute(stmt)
    rows = result.all()
    
    # product_id를 키로 하는 딕셔너리로 변환
    return {row.kok_product_id: row.kok_img_url for row in rows}


async def _batch_fetch_hs_images(db: AsyncSession, product_ids: List[int]) -> Dict[int, str]:
    """
    홈쇼핑 상품 이미지를 배치로 조회 (성능 최적화)
    
    Args:
        db: 데이터베이스 세션
        product_ids: 조회할 상품 ID 목록
    
    Returns:
        Dict[int, str]: product_id를 키로 하는 이미지 URL
    """
    if not product_ids:
        return {}
    
    # 각 상품의 첫 번째 이미지를 한 번에 조회
    stmt = (
        select(HomeshoppingImgUrl.product_id, HomeshoppingImgUrl.img_url)
        .where(HomeshoppingImgUrl.product_id.in_(product_ids))
        .distinct(HomeshoppingImgUrl.product_id)
        .order_by(HomeshoppingImgUrl.product_id, HomeshoppingImgUrl.sort_order)
    )
    
    result = await db.execute(stmt)
    rows = result.all()
    
    # product_id를 키로 하는 딕셔너리로 변환
    return {row.product_id: row.img_url for row in rows}
