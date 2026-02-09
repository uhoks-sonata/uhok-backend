"""HomeShopping order pricing CRUD functions."""

from sqlalchemy.ext.asyncio import AsyncSession

from common.logger import get_logger

logger = get_logger("hs_order_crud")

async def calculate_homeshopping_order_price(
    db: AsyncSession,
    product_id: int,
    quantity: int = 1
) -> dict:
    """
    홈쇼핑 주문 금액 계산 (최적화: 윈도우 함수로 최신 상품 정보 조회)
    
    Args:
        db: 데이터베이스 세션
        product_id: 상품 ID
        quantity: 수량 (기본값: 1)
    
    Returns:
        dict: 가격 정보 (product_id, product_name, dc_price, quantity, order_price)
        
    Note:
        - CRUD 계층: DB 조회만 담당, 트랜잭션 변경 없음
        - 윈도우 함수를 사용하여 최신 상품 정보를 한 번에 조회
        - 할인가(dc_price) 우선 사용, 없으면 할인율 적용하여 계산
        - 최종 주문 금액 = 할인가 × 수량
    """
    from sqlalchemy import text
    
    # 최적화된 쿼리: 윈도우 함수를 사용하여 최신 상품 정보를 한 번에 조회
    sql_query = """
    WITH latest_product_info AS (
        SELECT 
            hl.product_id,
            hl.product_name,
            ROW_NUMBER() OVER (
                PARTITION BY hl.product_id 
                ORDER BY hl.live_date DESC, hl.live_start_time DESC
            ) as rn
        FROM FCT_HOMESHOPPING_LIST hl
        WHERE hl.product_id = :product_id
    )
    SELECT 
        hpi.product_id,
        hpi.sale_price,
        hpi.dc_price,
        hpi.dc_rate,
        COALESCE(lpi.product_name, CONCAT('상품_', hpi.product_id)) as product_name
    FROM FCT_HOMESHOPPING_PRODUCT_INFO hpi
    LEFT JOIN latest_product_info lpi ON hpi.product_id = lpi.product_id AND lpi.rn = 1
    WHERE hpi.product_id = :product_id
    """
    
    try:
        result = await db.execute(text(sql_query), {"product_id": product_id})
        product_data = result.fetchone()
    except Exception as e:
        logger.error(f"홈쇼핑 상품 정보 조회 SQL 실행 실패: product_id={product_id}, error={str(e)}")
        raise
    
    if not product_data:
        logger.warning(f"홈쇼핑 상품을 찾을 수 없음: product_id={product_id}")
        raise ValueError("상품을 찾을 수 없습니다.")
    
    # 주문 금액 계산
    dc_price = product_data.dc_price or (product_data.sale_price * (1 - (product_data.dc_rate or 0) / 100)) or 0
    order_price = dc_price * quantity
    
    return {
        "product_id": product_id,
        "product_name": product_data.product_name,
        "dc_price": dc_price,
        "quantity": quantity,
        "order_price": order_price
    }
