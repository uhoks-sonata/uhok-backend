"""Recipe-related product lookup CRUD functions."""

from __future__ import annotations

from typing import Dict, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.logger import get_logger
from services.homeshopping.models.core_model import (
    HomeshoppingList,
    HomeshoppingProductInfo,
)

logger = get_logger("recipe_crud")

async def get_homeshopping_products_by_ingredient(
    db: AsyncSession, 
    ingredient: str
) -> List[Dict]:
    """
    홈쇼핑 쇼핑몰 내 ingredient(식재료명) 관련 상품 정보 조회
    - 상품 이미지, 상품명, 브랜드명, 가격 포함
    """
    # logger.info(f"홈쇼핑 상품 검색 시작: ingredient={ingredient}")
    
    try:
        stmt = (
            select(
                HomeshoppingList.product_id,
                HomeshoppingList.product_name,
                HomeshoppingList.thumb_img_url,
                HomeshoppingProductInfo.dc_price,
                HomeshoppingProductInfo.sale_price
            )
            .join(
                HomeshoppingProductInfo, 
                HomeshoppingList.product_id == HomeshoppingProductInfo.product_id
            )
            .where(HomeshoppingList.product_name.contains(ingredient))
            .order_by(HomeshoppingList.product_name)
        )
        
        result = await db.execute(stmt)
        products = result.all()
        
        # 결과를 딕셔너리 리스트로 변환
        product_list = []
        for product in products:
            product_dict = {
                "product_id": product.product_id,
                "product_name": product.product_name,
                "brand_name": None,  # 홈쇼핑 모델에 브랜드명 필드가 없음
                "price": product.dc_price or product.sale_price or 0,
                "thumb_img_url": product.thumb_img_url
            }
            product_list.append(product_dict)
        
    # logger.info(f"홈쇼핑 상품 검색 완료: ingredient={ingredient}, 상품 개수={len(product_list)}")
        return product_list
        
    except Exception as e:
        logger.error(f"홈쇼핑 상품 검색 실패: ingredient={ingredient}, error={e}")
        return []

