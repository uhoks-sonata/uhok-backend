from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from services.homeshopping.models.interaction_model import HomeshoppingCart
from services.homeshopping.models.core_model import HomeshoppingList
from .shared import logger

async def get_homeshopping_cart_items(
    db: AsyncSession, 
    user_id: int
) -> List:
    """
    사용자의 홈쇼핑 장바구니 아이템 조회
    
    Args:
        db: 데이터베이스 세션
        user_id: 사용자 ID
        
    Returns:
        홈쇼핑 장바구니 아이템 리스트
    """
    # logger.info(f"홈쇼핑 장바구니 조회 시작: user_id={user_id}")
    
    try:
        # 장바구니 테이블과 상품 정보를 조인하여 조회
        stmt = (
            select(
                HomeshoppingCart,
                HomeshoppingList.product_name,
                HomeshoppingList.thumb_img_url
            )
            .outerjoin(
                HomeshoppingList, 
                HomeshoppingCart.product_id == HomeshoppingList.product_id
            )
            .where(HomeshoppingCart.user_id == user_id)
            .order_by(HomeshoppingCart.created_at.desc())
        )
        
        try:
            result = await db.execute(stmt)
            cart_items = result.all()
        except Exception as e:
            logger.error(f"홈쇼핑 장바구니 조회 SQL 실행 실패: user_id={user_id}, error={str(e)}")
            return []
        
        # 결과를 객체 리스트로 변환
        cart_list = []
        for cart, product_name, thumb_img_url in cart_items:
            # cart 객체에 product_name과 thumb_img_url 추가
            cart.product_name = product_name
            cart.thumb_img_url = thumb_img_url
            cart_list.append(cart)
        
        # logger.info(f"홈쇼핑 장바구니 조회 완료: user_id={user_id}, 아이템 수={len(cart_list)}")
        return cart_list
        
    except Exception as e:
        logger.error(f"홈쇼핑 장바구니 조회 실패: user_id={user_id}, error={str(e)}")
        return []
