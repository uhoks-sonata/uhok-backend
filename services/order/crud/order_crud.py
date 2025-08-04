"""
주문 내역 관련 비동기 DB CRUD 함수
"""

from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, and_
from datetime import datetime, timedelta

from services.order.models.order_model import Order
# 상품 테이블 import 필요: from services.product.models.product_model import Product

async def get_order_count_by_user(db: AsyncSession, user_id: int) -> int:
    """
    특정 사용자의 전체 주문 개수 조회
    """
    result = await db.execute(
        select(func.count()).select_from(Order).where(Order.user_id == user_id) # type: ignore
    )
    return result.scalar()

async def get_recent_orders_by_user(db: AsyncSession, user_id: int, days: int = 7):
    """
    최근 N일간의 주문 내역 리스트 조회
    """
    since = datetime.now() - timedelta(days=days)
    result = await db.execute(
        select(Order)
        .where(and_(Order.user_id == user_id, Order.order_time >= since))
        .order_by(desc(Order.order_time))
    )
    return result.scalars().all()

async def get_orders_by_user(
    db: AsyncSession, user_id: int, status: Optional[str] = None,
    start_date: Optional[datetime] = None, end_date: Optional[datetime] = None,
    sort_by: str = "order_time", sort_order: str = "desc",
    page: int = 1, size: int = 10
):
    """
    주문 목록(페이지네이션) 조회
    """
    q = select(Order).where(Order.user_id == user_id)

    if status:
        q = q.where(Order.status == status)
    if start_date:
        q = q.where(Order.order_time >= start_date)
    if end_date:
        q = q.where(Order.order_time <= end_date)

    # 정렬 옵션 처리
    order_by_col = getattr(Order, sort_by)
    if sort_order == "desc":
        q = q.order_by(desc(order_by_col))
    else:
        q = q.order_by(order_by_col)

    # 페이지네이션
    total = await db.execute(select(func.count()).select_from(q.subquery()))
    total_count = total.scalar()

    result = await db.execute(
        q.offset((page-1)*size).limit(size)
    )
    orders = result.scalars().all()

    return total_count, orders

async def get_order_detail(db: AsyncSession, user_id: int, order_id: int):
    """
    특정 주문 상세 조회 (상품정보 조인)
    """
    # 실제로는 상품/결제 등 여러 테이블 join 필요!
    result = await db.execute(
        select(Order)
        .where(and_(Order.order_id == order_id, Order.user_id == user_id))
    )
    return result.scalars().first()
