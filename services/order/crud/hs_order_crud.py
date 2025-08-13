"""
홈쇼핑 주문 관련 CRUD 함수들
"""

import asyncio
from datetime import datetime
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from services.order.models.order_model import (
    Order, HomeShoppingOrder, HomeShoppingOrderStatusHistory, StatusMaster
)
from services.homeshopping.models.homeshopping_model import (
    HomeshoppingProductInfo, HomeshoppingList, HomeshoppingNotification
)

from services.order.crud.order_crud import (
    validate_user_exists, get_status_by_code,
    NOTIFICATION_TITLES, NOTIFICATION_MESSAGES
)

from common.logger import get_logger
from typing import List

logger = get_logger(__name__)


async def get_hs_current_status(db: AsyncSession, homeshopping_order_id: int) -> HomeShoppingOrderStatusHistory:
    """
    홈쇼핑 주문의 현재 상태(가장 최근 상태 이력) 조회
    """
    result = await db.execute(
        select(HomeShoppingOrderStatusHistory)
        .where(HomeShoppingOrderStatusHistory.homeshopping_order_id == homeshopping_order_id)
        .order_by(desc(HomeShoppingOrderStatusHistory.changed_at))
        .limit(1)
    )
    return result.scalars().first()


async def create_hs_notification_for_status_change(
    db: AsyncSession, 
    homeshopping_order_id: int, 
    status_id: int, 
    user_id: int
):
    """
    홈쇼핑 주문 상태 변경 시 알림 생성
    """
    # 상태 정보 조회
    status_result = await db.execute(
        select(StatusMaster).where(StatusMaster.status_id == status_id)
    )
    status = status_result.scalars().first()
    
    if not status:
        return
    
    # 알림 제목과 메시지 생성
    title = NOTIFICATION_TITLES.get(status.status_code, "주문 상태 변경")
    message = NOTIFICATION_MESSAGES.get(status.status_code, f"주문 상태가 '{status.status_name}'로 변경되었습니다.")
    
    # 알림 생성
    notification = HomeshoppingNotification(
        user_id=user_id,
        homeshopping_order_id=homeshopping_order_id,
        status_id=status_id,
        title=title,
        message=message
    )
    
    db.add(notification)
    await db.commit()


async def update_hs_order_status(
        db: AsyncSession,
        homeshopping_order_id: int,
        new_status_code: str,
        changed_by: int = None
) -> HomeShoppingOrder:
    """
    홈쇼핑 주문 상태 업데이트 (INSERT만 사용) + 알림 생성
    """
    # 1. 새로운 상태 조회
    new_status = await get_status_by_code(db, new_status_code)
    if not new_status:
        raise Exception(f"상태 코드 '{new_status_code}'를 찾을 수 없습니다")

    # 2. 주문 조회
    result = await db.execute(
        select(HomeShoppingOrder).where(HomeShoppingOrder.homeshopping_order_id == homeshopping_order_id)
    )
    hs_order = result.scalars().first()
    if not hs_order:
        raise Exception("해당 주문을 찾을 수 없습니다")

    # 3. 주문자 ID 조회
    order_result = await db.execute(
        select(Order).where(Order.order_id == hs_order.order_id)
    )
    order = order_result.scalars().first()
    if not order:
        raise Exception("주문 정보를 찾을 수 없습니다")

    # 4. 상태 변경 이력 생성 (UPDATE 없이 INSERT만)
    status_history = HomeShoppingOrderStatusHistory(
        homeshopping_order_id=homeshopping_order_id,
        status_id=new_status.status_id,
        changed_at=datetime.now(),
        changed_by=changed_by or order.user_id
    )
    
    db.add(status_history)
    
    # 5. 알림 생성
    await create_hs_notification_for_status_change(
        db=db,
        homeshopping_order_id=homeshopping_order_id,
        status_id=new_status.status_id,
        user_id=order.user_id
    )
    
    await db.commit()
    logger.info(f"홈쇼핑 주문 상태 변경 완료: homeshopping_order_id={homeshopping_order_id}, status={new_status_code}")
    
    return hs_order
