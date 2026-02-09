"""Order delivery read CRUD functions."""

from sqlalchemy.ext.asyncio import AsyncSession

from common.logger import get_logger

logger = get_logger("order_crud")

async def get_delivery_info(db: AsyncSession, order_type: str, order_id: int) -> tuple[str, str]:
    """
    주문의 배송 상태와 배송완료 날짜를 조회하는 헬퍼 함수 (최적화: Raw SQL 사용)
    
    Args:
        db: 데이터베이스 세션
        order_type: 주문 타입 ("kok" 또는 "homeshopping")
        order_id: 주문 ID (kok_order_id 또는 homeshopping_order_id)
    
    Returns:
        tuple: (delivery_status, delivery_date)
        
    Note:
        - CRUD 계층: DB 조회만 담당, 트랜잭션 변경 없음
        - Raw SQL을 사용하여 성능 최적화
        - 배송완료 상태인 경우 한국어 형식으로 날짜 포맷팅
    """
    from sqlalchemy import text
    
    try:
        if order_type == "kok":
            # 콕 주문의 현재 상태 조회 (최적화된 쿼리)
            sql_query = """
            SELECT 
                sm.status_name,
                kosh.changed_at
            FROM KOK_ORDER_STATUS_HISTORY kosh
            INNER JOIN STATUS_MASTER sm ON kosh.status_id = sm.status_id
            WHERE kosh.kok_order_id = :order_id
            ORDER BY kosh.changed_at DESC
            LIMIT 1
            """
        else:
            # 홈쇼핑 주문의 현재 상태 조회 (최적화된 쿼리)
            sql_query = """
            SELECT 
                sm.status_name,
                hosh.changed_at
            FROM HOMESHOPPING_ORDER_STATUS_HISTORY hosh
            INNER JOIN STATUS_MASTER sm ON hosh.status_id = sm.status_id
            WHERE hosh.homeshopping_order_id = :order_id
            ORDER BY hosh.changed_at DESC
            LIMIT 1
            """
        
        result = await db.execute(text(sql_query), {"order_id": order_id})
        status_data = result.fetchone()
        
        if not status_data:
            return "주문접수", "배송 정보 없음"
        
        current_status = status_data.status_name
        changed_at = status_data.changed_at
        
        # 배송완료 상태인 경우 배송완료 날짜 설정
        if current_status == "배송완료":
            # 배송완료 날짜를 한국어 형식으로 포맷팅
            month = changed_at.month
            day = changed_at.day
            weekday = ["월", "화", "수", "목", "금", "토", "일"][changed_at.weekday()]
            delivery_date = f"{month}/{day}({weekday}) 도착"
        else:
            # 배송완료가 아닌 경우 상태에 따른 메시지
            delivery_date = "배송 정보 없음"
        
        return current_status, delivery_date
        
    except Exception as e:
        logger.warning(f"배송 정보 조회 실패: order_type={order_type}, order_id={order_id}, error={str(e)}")
        return "상태 조회 실패", "배송 정보 없음"

