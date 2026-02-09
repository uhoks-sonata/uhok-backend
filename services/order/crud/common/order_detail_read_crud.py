"""Order detail read CRUD functions."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.logger import get_logger
from services.order.models.order_base_model import Order
from services.order.models.kok.kok_order_model import KokOrder
from services.order.models.homeshopping.hs_order_model import HomeShoppingOrder

logger = get_logger("order_crud")

async def get_order_by_id(db: AsyncSession, order_id: int) -> dict:
    """
    주문 ID로 통합 주문 조회 (최적화: 윈도우 함수 사용)
    
    Args:
        db: 데이터베이스 세션
        order_id: 조회할 주문 ID
    
    Returns:
        dict: 주문 정보 (order_id, user_id, order_time, cancel_time, kok_orders, homeshopping_orders)
        
    Note:
        - CRUD 계층: DB 조회만 담당, 트랜잭션 변경 없음
        - 윈도우 함수를 사용하여 모든 정보를 한 번에 조회
        - 콕 주문과 홈쇼핑 주문 정보를 모두 포함하여 반환
    """
    from sqlalchemy import text
    
    # 최적화된 쿼리: 윈도우 함수를 사용하여 모든 정보를 한 번에 조회
    sql_query = """
    WITH kok_orders_data AS (
        SELECT 
            ko.order_id,
            ko.kok_order_id,
            ko.kok_product_id,
            ko.quantity,
            ko.order_price,
            ko.recipe_id,
            ko.kok_price_id,
            ROW_NUMBER() OVER (PARTITION BY ko.order_id ORDER BY ko.kok_order_id) as rn
        FROM KOK_ORDERS ko
        WHERE ko.order_id = :order_id
    ),
    homeshopping_orders_data AS (
        SELECT 
            ho.order_id,
            ho.homeshopping_order_id,
            ho.product_id,
            ho.quantity,
            ho.order_price,
            ho.dc_price,
            ROW_NUMBER() OVER (PARTITION BY ho.order_id ORDER BY ho.homeshopping_order_id) as rn
        FROM HOMESHOPPING_ORDERS ho
        WHERE ho.order_id = :order_id
    )
    SELECT 
        o.order_id,
        o.user_id,
        o.order_time,
        o.cancel_time,
        COALESCE(kod.kok_order_id, 0) as kok_order_id,
        COALESCE(kod.kok_product_id, 0) as kok_product_id,
        COALESCE(kod.quantity, 0) as kok_quantity,
        COALESCE(kod.order_price, 0) as kok_order_price,
        COALESCE(kod.recipe_id, 0) as recipe_id,
        COALESCE(kod.kok_price_id, 0) as kok_price_id,
        COALESCE(hod.homeshopping_order_id, 0) as homeshopping_order_id,
        COALESCE(hod.product_id, 0) as product_id,
        COALESCE(hod.quantity, 0) as hs_quantity,
        COALESCE(hod.order_price, 0) as hs_order_price,
        COALESCE(hod.dc_price, 0) as dc_price
    FROM ORDERS o
    LEFT JOIN kok_orders_data kod ON o.order_id = kod.order_id AND kod.rn = 1
    LEFT JOIN homeshopping_orders_data hod ON o.order_id = hod.order_id AND hod.rn = 1
    WHERE o.order_id = :order_id
    """
    
    try:
        result = await db.execute(text(sql_query), {"order_id": order_id})
        order_data = result.fetchone()
    except Exception as e:
        logger.error(f"주문 조회 SQL 실행 실패: order_id={order_id}, error={str(e)}")
        return None
    
    if not order_data:
        logger.warning(f"주문을 찾을 수 없음: order_id={order_id}")
        return None
    
    # 콕 주문과 홈쇼핑 주문을 별도로 조회하여 완전한 데이터 구성
    kok_orders = []
    homeshopping_orders = []
    
    # 콕 주문 조회
    try:
        kok_result = await db.execute(
            select(KokOrder).where(KokOrder.order_id == order_id)
        )
        kok_orders = kok_result.scalars().all()
    except Exception as e:
        logger.warning(f"콕 주문 정보 조회 실패: order_id={order_id}, error={str(e)}")
        kok_orders = []
    
    # 홈쇼핑 주문 조회
    try:
        homeshopping_result = await db.execute(
            select(HomeShoppingOrder).where(HomeShoppingOrder.order_id == order_id)
        )
        homeshopping_orders = homeshopping_result.scalars().all()
    except Exception as e:
        logger.warning(f"홈쇼핑 주문 정보 조회 실패: order_id={order_id}, error={str(e)}")
        homeshopping_orders = []
    
    # 딕셔너리 형태로 반환
    return {
        "order_id": order_data.order_id,
        "user_id": order_data.user_id,
        "order_time": order_data.order_time,
        "cancel_time": order_data.cancel_time,
        "kok_orders": kok_orders,
        "homeshopping_orders": homeshopping_orders
    }

