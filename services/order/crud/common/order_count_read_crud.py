"""Order count read CRUD functions."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.logger import get_logger
from services.order.models.order_base_model import Order

logger = get_logger("order_crud")

async def get_user_order_counts(db: AsyncSession, user_id: int) -> int:
    """
    사용자별 주문 개수만 조회 (성능 최적화)
    
    Args:
        db: 데이터베이스 세션
        user_id: 조회할 사용자 ID
    
    Returns:
        int: 사용자의 주문 개수
        
    Note:
        - CRUD 계층: DB COUNT 쿼리만 실행하여 성능 최적화
        - 전체 주문 데이터를 가져오지 않고 개수만 계산
    """
    from sqlalchemy import func
    
    try:
        result = await db.execute(
            select(func.count(Order.order_id))
            .where(Order.user_id == user_id)
        )
        return result.scalar()
    except Exception as e:
        logger.error(f"사용자 주문 개수 조회 SQL 실행 실패: user_id={user_id}, error={str(e)}")
        return 0



