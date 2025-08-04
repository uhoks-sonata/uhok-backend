"""
ORDERS + 서비스별 주문 상세를 트랜잭션으로 한 번에 생성/조회 (HomeShopping 명칭 통일)
"""
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from services.order.models.order_model import Order, KokOrder, HomeShoppingOrder

async def create_kok_order(db: AsyncSession, user_id: int, price_id: int) -> Order:
    """
    콕 주문 생성 (트랜잭션)
    """
    order = Order(user_id=user_id, order_time=datetime.now())
    db.add(order)
    await db.flush()
    kok_order = KokOrder(order_id=order.order_id, price_id=price_id)
    db.add(kok_order)
    await db.commit()
    await db.refresh(order)
    return order

async def create_homeshopping_order(db: AsyncSession, user_id: int, live_id: int) -> Order:
    """
    HomeShopping 주문 생성 (트랜잭션)
    """
    order = Order(user_id=user_id, order_time=datetime.now())
    db.add(order)
    await db.flush()
    homeshopping_order = HomeShoppingOrder(order_id=order.order_id, live_id=live_id)
    db.add(homeshopping_order)
    await db.commit()
    await db.refresh(order)
    return order

async def get_order_by_id(db: AsyncSession, order_id: int) -> Order:
    """
    주문 ID로 통합 주문 조회 (공통 정보 + 서비스별 상세)
    """
    from sqlalchemy.future import select
    result = await db.execute(
        select(Order).where(Order.order_id == order_id) # type: ignore
    )
    return result.scalars().first()
