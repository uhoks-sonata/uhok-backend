"""
통합 주문 조회/상세/통계 API 라우터 (콕, HomeShopping 모두 지원)
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta
from typing import List

from services.order.schemas.order_schema import OrderRead, OrderCountResponse
from services.order.models.order_model import Order
from services.order.crud.order_crud import get_order_by_id
from common.database.mariadb_service import get_maria_service_db
from common.dependencies import get_current_user


router = APIRouter(prefix="/api/orders", tags=["Orders"])

@router.get("/", response_model=List[OrderRead])
async def list_orders(
    limit: int = Query(10, description="조회 개수"),
    db: AsyncSession = Depends(get_maria_service_db),
    user=Depends(get_current_user)
):
    """
    내 주문 리스트 (공통+서비스별 상세 포함)
    """
    from services.order.models.order_model import Order
    from sqlalchemy.future import select

    result = await db.execute(
        select(Order).where(Order.user_id == user.user_id).order_by(Order.order_time.desc()).limit(limit) # type: ignore
    )
    orders = result.scalars().all()
    return orders


@router.get("/{order_id}", response_model=OrderRead)
async def read_order(
    order_id: int,
    db: AsyncSession = Depends(get_maria_service_db),
    user=Depends(get_current_user)
):
    """
    단일 주문 조회 (공통+콕+HomeShopping 상세 포함)
    """
    order = await get_order_by_id(db, order_id)
    if not order or order.user_id != user.user_id:
        raise HTTPException(status_code=404, detail="주문 내역이 없습니다.")
    return order


@router.get("/count", response_model=OrderCountResponse)
async def order_count(
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
    return OrderCountResponse(order_count=count)

@router.get("/recent", response_model=List[OrderRead])
async def recent_orders(
    days: int = Query(7, description="최근 조회 일수 (default=7)"),
    db: AsyncSession = Depends(get_maria_service_db),
    user=Depends(get_current_user)
):
    """
    최근 N일간 주문 내역 리스트 조회
    """
    since = datetime.now() - timedelta(days=days)
    result = await db.execute(
        select(Order)
        .where(Order.user_id == user.user_id) # type: ignore
        .where(Order.order_time >= since)
        .order_by(desc(Order.order_time))
    )
    orders = result.scalars().all()
    return orders
