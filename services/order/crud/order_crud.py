"""
주문 관련 DB CRUD 함수 정의 (비동기, 변수명 소문자/DB 컬럼 대문자 매핑)
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from datetime import datetime
from services.order.models.order_model import Order
from services.order.schemas.order_schema import OrderCreate

async def create_order(db: AsyncSession, order_data: OrderCreate) -> Order:
    """
    주문 생성 및 DB에 저장 (order_time은 현재 시간으로 자동 입력)
    """
    new_order = Order(
        user_id=order_data.user_id,
        price_id=order_data.price_id,
        order_time=datetime.now()
    )
    db.add(new_order)
    await db.commit()
    await db.refresh(new_order)
    return new_order

async def get_order_by_id(db: AsyncSession, order_id: int) -> Order:
    """
    order_id로 주문 단일 조회
    """
    result = await db.execute(select(Order).where(Order.order_id == order_id))
    return result.scalars().first()

async def cancel_order(db: AsyncSession, order_id: int) -> Order:
    """
    주문 취소 (cancel_time을 현재 시각으로 업데이트)
    """
    result = await db.execute(select(Order).where(Order.order_id == order_id))
    order = result.scalars().first()
    if order:
        order.cancel_time = datetime.now()
        await db.commit()
        await db.refresh(order)
    return order
