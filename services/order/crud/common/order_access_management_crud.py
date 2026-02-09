"""Order access management CRUD functions."""

from __future__ import annotations

from typing import Dict, Any

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from common.logger import get_logger
from services.order.crud.common.order_detail_read_crud import get_order_by_id

logger = get_logger("order_crud")

async def _ensure_order_access(db: AsyncSession, order_id: int, user_id: int) -> Dict[str, Any]:
    """
    주문 존재/권한 확인 유틸
    
    Args:
        db: 데이터베이스 세션
        order_id: 확인할 주문 ID
        user_id: 요청한 사용자 ID
    
    Returns:
        Dict[str, Any]: 주문 데이터 (권한이 있는 경우)
        
    Raises:
        HTTPException: 주문이 없거나 권한이 없는 경우 404
        
    Note:
        - CRUD 계층: DB 조회만 담당, 트랜잭션 변경 없음
        - 해당 order_id가 존재하고, 소유자가 user_id인지 확인
        - 권한이 없으면 404 에러 반환
    """
    # logger.info(f"주문 접근 권한 확인: order_id={order_id}, user_id={user_id}")
    
    order_data = await get_order_by_id(db, order_id)
    # logger.info(f"주문 데이터 조회 결과: order_id={order_id}, order_data={order_data is not None}")
    
    if not order_data:
        logger.warning(f"주문을 찾을 수 없음: order_id={order_id}, user_id={user_id}")
        raise HTTPException(status_code=404, detail="주문 내역이 없습니다.")
    
    if order_data["user_id"] != user_id:
        logger.warning(f"주문 접근 권한 없음: order_id={order_id}, order_user_id={order_data['user_id']}, request_user_id={user_id}")
        raise HTTPException(status_code=404, detail="주문 내역이 없습니다.")
    
    # logger.info(f"주문 접근 권한 확인 완료: order_id={order_id}, user_id={user_id}")
    return order_data

