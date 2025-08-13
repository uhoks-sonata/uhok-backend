"""
통합 주문 조회/상세/통계 API 라우터 (콕, HomeShopping 모두 지원)
"""
from fastapi import APIRouter, Depends, Query, HTTPException, BackgroundTasks
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta
from typing import List

from services.order.models.order_model import Order, KokOrder, HomeShoppingOrder

from services.order.schemas.order_schema import (
    OrderRead, 
    OrderCountResponse, 
)
from services.order.crud.order_crud import get_order_by_id, get_user_orders

from common.database.mariadb_service import get_maria_service_db
from common.dependencies import get_current_user
from common.log_utils import send_user_log
from common.logger import get_logger

router = APIRouter(prefix="/api/orders", tags=["Orders"])
logger = get_logger("order_router")

@router.get("/", response_model=List[OrderRead])
async def list_orders(
    limit: int = Query(10, description="조회 개수"),
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_maria_service_db),
    user=Depends(get_current_user)
):
    """
    내 주문 리스트 (공통+서비스별 상세 포함)
    """
    order_list = await get_user_orders(db, user.user_id, limit, 0)
    
    # 주문 목록 조회 로그 기록
    if background_tasks:
        background_tasks.add_task(
            send_user_log, 
            user_id=user.user_id, 
            event_type="order_list_view", 
            event_data={"limit": limit, "order_count": len(order_list)}
        )
    
    return order_list


@router.get("/count", response_model=OrderCountResponse)
async def order_count(
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_maria_service_db),
    user=Depends(get_current_user)
):
    """
    로그인 사용자의 전체 주문 개수 조회
    """
    result = await db.execute(
        select(func.count()).select_from(Order).where(Order.user_id == user.user_id) # type: ignore
    )
    count = result.scalar()
    
    # 주문 개수 조회 로그 기록
    if background_tasks:
        background_tasks.add_task(
            send_user_log, 
            user_id=user.user_id, 
            event_type="order_count_view", 
            event_data={"order_count": count}
        )
    
    return OrderCountResponse(order_count=count)

@router.get("/recent", response_model=List[OrderRead])
async def recent_orders(
    days: int = Query(7, description="최근 조회 일수 (default=7)"),
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_maria_service_db),
    user=Depends(get_current_user)
):
    """
    최근 N일간 주문 내역 리스트 조회
    """
    since = datetime.now() - timedelta(days=days)
    
    # 최근 N일간 주문 조회 (get_user_orders 사용)
    order_list = await get_user_orders(db, user.user_id, 100, 0)  # 충분히 큰 limit
    
    # 날짜 필터링
    filtered_orders = [
        order for order in order_list 
        if order["order_time"] >= since
    ]
    
    # 최근 주문 조회 로그 기록
    if background_tasks:
        background_tasks.add_task(
            send_user_log, 
            user_id=user.user_id, 
            event_type="recent_orders_view", 
            event_data={"days": days, "order_count": len(filtered_orders)}
        )
    
    return filtered_orders


@router.get("/{order_id}", response_model=OrderRead)
async def read_order(
        order_id: int,
        background_tasks: BackgroundTasks = None,
        db: AsyncSession = Depends(get_maria_service_db),
        user=Depends(get_current_user)
):
    """
    단일 주문 조회 (공통+콕+HomeShopping 상세 포함)
    """
    order_data = await get_order_by_id(db, order_id)
    if not order_data or order_data["user_id"] != user.user_id:
        raise HTTPException(status_code=404, detail="주문 내역이 없습니다.")

    # 주문 상세 조회 로그 기록
    if background_tasks:
        background_tasks.add_task(
            send_user_log,
            user_id=user.user_id,
            event_type="order_detail_view",
            event_data={"order_id": order_id}
        )

    return order_data
