"""
ORDERS + 서비스별 주문 상세를 트랜잭션으로 한 번에 생성/조회 (HomeShopping 명칭 통일)
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from services.order.models.order_model import Order, KokOrder, HomeShoppingOrder
from services.kok.models.kok_model import KokPriceInfo

async def create_kok_order(
        db: AsyncSession,
        user_id: int,
        kok_price_id: int,
        kok_product_id: int,
        quantity: int = 1
) -> Order:
    """
    콕 상품 주문 생성 및 할인 가격 반영
    - kok_price_id로 할인 가격 조회 후 quantity 곱해서 order_price 자동계산
    """
    # 1. 할인 가격 조회
    result = await db.execute(
        select(KokPriceInfo.kok_discounted_price)
        .where(KokPriceInfo.kok_price_id == kok_price_id) # type: ignore
    )
    discounted_price = result.scalar_one_or_none()
    if discounted_price is None:
        raise Exception("해당 kok_price_id에 해당하는 할인 가격 없음")

    # 2. 주문가격 계산
    order_price = discounted_price * quantity

    # 3. 주문 데이터 생성
    new_order = KokOrder(
        user_id=user_id,
        kok_price_id=kok_price_id,
        kok_product_id=kok_product_id,
        quantity=quantity,
        order_price=order_price,
    )
    db.add(new_order)
    await db.commit()
    await db.refresh(new_order)
    return new_order


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
