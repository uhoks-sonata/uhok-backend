"""Order price management CRUD functions."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.logger import get_logger
from services.order.models.kok.kok_order_model import KokOrder
from services.order.models.homeshopping.hs_order_model import HomeShoppingOrder
from services.order.crud.kok.kok_order_price_crud import calculate_kok_order_price
from services.order.crud.homeshopping.hs_order_pricing_crud import calculate_homeshopping_order_price

logger = get_logger("order_crud")

async def calculate_order_total_price(db: AsyncSession, order_id: int) -> int:
    """
    주문 ID로 총 주문 금액 계산 (최적화: Raw SQL 사용)
    
    Args:
        db: 데이터베이스 세션
        order_id: 계산할 주문 ID
    
    Returns:
        int: 총 주문 금액
        
    Note:
        - CRUD 계층: DB 조회만 담당, 트랜잭션 변경 없음
        - Raw SQL을 사용하여 성능 최적화
        - 각 주문 타입별로 이미 계산된 order_price 사용
        - order_price가 없는 경우 계산 함수를 통해 재계산
        - 계산 실패 시 기본값(dc_price * quantity) 사용
    """
    from sqlalchemy import text
    
    # 최적화된 쿼리: Raw SQL을 사용하여 모든 주문 금액을 한 번에 계산
    sql_query = """
    SELECT 
        COALESCE(SUM(ko.order_price), 0) as kok_total,
        COALESCE(SUM(ho.order_price), 0) as homeshopping_total
    FROM ORDERS o
    LEFT JOIN KOK_ORDERS ko ON o.order_id = ko.order_id
    LEFT JOIN HOMESHOPPING_ORDERS ho ON o.order_id = ho.order_id
    WHERE o.order_id = :order_id
    """
    
    try:
        result = await db.execute(text(sql_query), {"order_id": order_id})
        price_data = result.fetchone()
        
        if not price_data:
            logger.warning(f"주문을 찾을 수 없음: order_id={order_id}")
            return 0
        
        total_price = (price_data.kok_total or 0) + (price_data.homeshopping_total or 0)
        
        # order_price가 없는 주문들에 대해 개별 계산
        if total_price == 0:
            # 콕 주문 개별 계산
            try:
                kok_result = await db.execute(
                    select(KokOrder).where(KokOrder.order_id == order_id)
                )
                kok_orders = kok_result.scalars().all()
            except Exception as e:
                logger.error(f"콕 주문 총액 계산 조회 SQL 실행 실패: order_id={order_id}, error={str(e)}")
                kok_orders = []
            
            for kok_order in kok_orders:
                if not kok_order.order_price:
                    try:
                        price_info = await calculate_kok_order_price(
                            db, 
                            kok_order.kok_price_id, 
                            kok_order.kok_product_id, 
                            kok_order.quantity
                        )
                        total_price += price_info["order_price"]
                    except Exception as e:
                        logger.warning(f"콕 주문 금액 계산 실패: kok_order_id={kok_order.kok_order_id}, error={str(e)}")
                        total_price += 0
                else:
                    total_price += kok_order.order_price
            
            # 홈쇼핑 주문 개별 계산
            try:
                homeshopping_result = await db.execute(
                    select(HomeShoppingOrder).where(HomeShoppingOrder.order_id == order_id)
                )
                homeshopping_orders = homeshopping_result.scalars().all()
            except Exception as e:
                logger.error(f"홈쇼핑 주문 총액 계산 조회 SQL 실행 실패: order_id={order_id}, error={str(e)}")
                homeshopping_orders = []
            
            for hs_order in homeshopping_orders:
                if not hs_order.order_price:
                    try:
                        price_info = await calculate_homeshopping_order_price(
                            db, 
                            hs_order.product_id, 
                            hs_order.quantity
                        )
                        total_price += price_info["order_price"]
                    except Exception as e:
                        logger.warning(f"홈쇼핑 주문 금액 계산 실패: homeshopping_order_id={hs_order.homeshopping_order_id}, error={str(e)}")
                        fallback_price = getattr(hs_order, 'dc_price', 0) * getattr(hs_order, 'quantity', 1)
                        total_price += fallback_price
                else:
                    total_price += hs_order.order_price
        
        return total_price
        
    except Exception as e:
        logger.error(f"주문 총액 계산 SQL 실행 실패: order_id={order_id}, error={str(e)}")
        return 0


