"""Kok order pricing/debug CRUD functions."""

from typing import List

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from common.logger import get_logger
from services.kok.models.interaction_model import KokCart
from services.kok.models.product_model import KokPriceInfo, KokProductInfo

logger = get_logger("kok_order_crud")

async def calculate_kok_order_price(
    db: AsyncSession,
    kok_price_id: int,
    kok_product_id: int,
    quantity: int = 1
) -> dict:
    """
    콕 주문 금액 계산 (최적화: Raw SQL 사용)
    
    Args:
        db: 데이터베이스 세션
        kok_price_id: 콕 가격 정보 ID
        kok_product_id: 콕 상품 ID
        quantity: 수량 (기본값: 1)
    
    Returns:
        dict: 가격 정보 (kok_price_id, kok_product_id, unit_price, quantity, order_price, product_name)
        
    Note:
        - CRUD 계층: DB 조회만 담당, 트랜잭션 변경 없음
        - Raw SQL을 사용하여 성능 최적화
        - 할인 가격이 있으면 할인 가격 사용, 없으면 상품 기본 가격 사용
        - 최종 주문 금액 = 단가 × 수량
    """
    from sqlalchemy import text
    
    # 최적화된 쿼리: Raw SQL 사용 (모델 기반으로 수정)
    sql_query = """
    SELECT 
        kpi.kok_price_id,
        kpi.kok_product_id,
        kpi.kok_discounted_price,
        kpi.kok_discount_rate,
        kpr.kok_product_price,
        kpr.kok_product_name,
        COALESCE(kpi.kok_discounted_price, kpr.kok_product_price, 0) as unit_price
    FROM FCT_KOK_PRICE_INFO kpi
    LEFT JOIN FCT_KOK_PRODUCT_INFO kpr ON kpi.kok_product_id = kpr.kok_product_id
    WHERE kpi.kok_price_id = :kok_price_id
    """
    
    try:
        result = await db.execute(text(sql_query), {"kok_price_id": kok_price_id})
        price_data = result.fetchone()
    except Exception as e:
        logger.error(f"콕 가격 정보 조회 SQL 실행 실패: kok_price_id={kok_price_id}, error={str(e)}")
        raise
    
    if not price_data:
        logger.warning(f"콕 할인 가격 정보를 찾을 수 없음: kok_price_id={kok_price_id}")
        raise ValueError("할인 가격 정보를 찾을 수 없습니다.")
    
    # 주문 금액 계산
    unit_price = price_data.unit_price
    order_price = unit_price * quantity
    
    return {
        "kok_price_id": kok_price_id,
        "kok_product_id": kok_product_id,
        "unit_price": unit_price,
        "quantity": quantity,
        "order_price": order_price,
        "product_name": price_data.kok_product_name or f"상품_{kok_product_id}"
    }



async def debug_cart_status(db: AsyncSession, user_id: int, kok_cart_ids: List[int]) -> dict:
    """
    장바구니 상태를 디버깅하기 위한 함수
    
    Args:
        db: 데이터베이스 세션
        user_id: 사용자 ID
        kok_cart_ids: 확인할 장바구니 ID 목록
    
    Returns:
        dict: 디버깅 정보
    """
    debug_info = {
        "user_id": user_id,
        "requested_cart_ids": kok_cart_ids,
        "cart_status": {},
        "database_tables": {}
    }
    
    # 1. 장바구니 테이블 상태 확인
    for kok_cart_id in kok_cart_ids:
        try:
            cart_stmt = select(KokCart).where(KokCart.kok_cart_id == kok_cart_id)
            cart_result = await db.execute(cart_stmt)
            cart = cart_result.scalars().first()
        except Exception as e:
            logger.warning(f"장바구니 조회 실패: kok_cart_id={kok_cart_id}, error={str(e)}")
            cart = None
        
        if cart:
            debug_info["cart_status"][kok_cart_id] = {
                "exists": True,
                "kok_product_id": cart.kok_product_id,
                "recipe_id": cart.recipe_id,
                "user_id": cart.user_id
            }
            
            # 상품 정보 확인
            if cart.kok_product_id:
                try:
                    product_stmt = select(KokProductInfo).where(KokProductInfo.kok_product_id == cart.kok_product_id)
                    product_result = await db.execute(product_stmt)
                    product = product_result.scalars().first()
                except Exception as e:
                    logger.warning(f"상품 정보 조회 실패: kok_product_id={cart.kok_product_id}, error={str(e)}")
                    product = None
                
                if product:
                    debug_info["cart_status"][kok_cart_id]["product"] = {
                        "exists": True,
                        "name": product.kok_product_name,
                        "description": product.kok_product_description
                    }
                else:
                    debug_info["cart_status"][kok_cart_id]["product"] = {"exists": False}
                
                # 가격 정보 확인
                try:
                    price_stmt = select(KokPriceInfo).where(KokPriceInfo.kok_product_id == cart.kok_product_id)
                    price_result = await db.execute(price_stmt)
                    price = price_result.scalars().all()
                except Exception as e:
                    logger.warning(f"가격 정보 조회 실패: kok_product_id={cart.kok_product_id}, error={str(e)}")
                    price = []
                
                if price:
                    debug_info["cart_status"][kok_cart_id]["price"] = {
                        "exists": True,
                        "count": len(price),
                        "price_ids": [p.kok_price_id for p in price]
                    }
                else:
                    debug_info["cart_status"][kok_cart_id]["price"] = {"exists": False}
        else:
            debug_info["cart_status"][kok_cart_id] = {"exists": False}
    
    # 2. 사용자의 전체 장바구니 항목 확인
    try:
        all_carts_stmt = select(KokCart).where(KokCart.user_id == user_id)
        all_carts_result = await db.execute(all_carts_stmt)
        all_user_carts = all_carts_result.scalars().all()
    except Exception as e:
        logger.warning(f"사용자 전체 장바구니 조회 실패: user_id={user_id}, error={str(e)}")
        all_user_carts = []
    
    debug_info["database_tables"]["user_carts"] = {
        "total_count": len(all_user_carts),
        "cart_ids": [c.kok_cart_id for c in all_user_carts],
        "product_ids": [c.kok_product_id for c in all_user_carts]
    }
    
    # 3. 전체 상품 정보 개수 확인
    try:
        product_count_stmt = select(func.count(KokProductInfo.kok_product_id))
        product_count_result = await db.execute(product_count_stmt)
        total_products = product_count_result.scalar()
    except Exception as e:
        logger.warning(f"전체 상품 개수 조회 실패: error={str(e)}")
        total_products = 0
    
    # 4. 전체 가격 정보 개수 확인
    try:
        price_count_stmt = select(func.count(KokPriceInfo.kok_price_id))
        price_count_result = await db.execute(price_count_stmt)
        total_prices = price_count_result.scalar()
    except Exception as e:
        logger.warning(f"전체 가격 정보 개수 조회 실패: error={str(e)}")
        total_prices = 0
    
    debug_info["database_tables"]["summary"] = {
        "total_products": total_products,
        "total_prices": total_prices
    }
    
    return debug_info
