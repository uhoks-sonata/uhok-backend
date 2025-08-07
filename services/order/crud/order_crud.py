"""
ORDERS + 서비스별 주문 상세를 트랜잭션으로 한 번에 생성/조회 (HomeShopping 명칭 통일)
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from services.order.models.order_model import Order, KokOrder, HomeShoppingOrder, StatusMaster, KokOrderStatusHistory
from services.kok.models.kok_model import KokPriceInfo

async def get_status_by_code(db: AsyncSession, status_code: str) -> StatusMaster:
    """
    상태 코드로 상태 정보 조회
    """
    result = await db.execute(
        select(StatusMaster).where(StatusMaster.status_code == status_code)
    )
    return result.scalars().first()

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
    - 기본 상태는 'PAYMENT_COMPLETED'로 설정
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

    # 3. 결제완료 상태 조회
    payment_completed_status = await get_status_by_code(db, "PAYMENT_COMPLETED")
    if not payment_completed_status:
        raise Exception("결제완료 상태 코드를 찾을 수 없습니다")

    # 4. 주문 데이터 생성 (트랜잭션)
    # 4-1. 상위 주문 생성
    new_order = Order(
        user_id=user_id,
        order_time=datetime.now()
    )
    db.add(new_order)
    await db.flush()  # order_id 생성

    # 4-2. 콕 주문 상세 생성
    new_kok_order = KokOrder(
        order_id=new_order.order_id,
        kok_price_id=kok_price_id,
        kok_product_id=kok_product_id,
        quantity=quantity,
        order_price=order_price,
        current_status_id=payment_completed_status.status_id
    )
    db.add(new_kok_order)
    await db.flush()  # kok_order_id 생성

    # 4-3. 상태 변경 이력 생성
    status_history = KokOrderStatusHistory(
        kok_order_id=new_kok_order.kok_order_id,
        status_id=payment_completed_status.status_id,
        changed_by=user_id
    )
    db.add(status_history)

    await db.commit()
    await db.refresh(new_order)
    return new_order

async def update_kok_order_status(
        db: AsyncSession,
        kok_order_id: int,
        new_status_code: str,
        changed_by: int = None
) -> KokOrder:
    """
    콕 주문 상태 업데이트
    """
    # 1. 새로운 상태 조회
    new_status = await get_status_by_code(db, new_status_code)
    if not new_status:
        raise Exception(f"상태 코드 '{new_status_code}'를 찾을 수 없습니다")

    # 2. 주문 조회
    result = await db.execute(
        select(KokOrder).where(KokOrder.kok_order_id == kok_order_id)
    )
    kok_order = result.scalars().first()
    if not kok_order:
        raise Exception("해당 주문을 찾을 수 없습니다")

    # 3. 상태 업데이트
    kok_order.current_status_id = new_status.status_id

    # 4. 상태 변경 이력 생성
    status_history = KokOrderStatusHistory(
        kok_order_id=kok_order_id,
        status_id=new_status.status_id,
        changed_by=changed_by
    )
    db.add(status_history)

    await db.commit()
    await db.refresh(kok_order)
    return kok_order

async def get_kok_order_with_status(db: AsyncSession, kok_order_id: int):
    """
    콕 주문과 현재 상태 정보를 함께 조회
    """
    result = await db.execute(
        select(KokOrder, StatusMaster)
        .join(StatusMaster, KokOrder.current_status_id == StatusMaster.status_id)
        .where(KokOrder.kok_order_id == kok_order_id)
    )
    return result.first()

async def get_kok_order_status_history(db: AsyncSession, kok_order_id: int):
    """
    콕 주문의 상태 변경 이력 조회
    """
    result = await db.execute(
        select(KokOrderStatusHistory, StatusMaster)
        .join(StatusMaster, KokOrderStatusHistory.status_id == StatusMaster.status_id)
        .where(KokOrderStatusHistory.kok_order_id == kok_order_id)
        .order_by(KokOrderStatusHistory.changed_at.desc())
    )
    return result.all()

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
