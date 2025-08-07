"""
ORDERS + 서비스별 주문 상세를 트랜잭션으로 한 번에 생성/조회 (HomeShopping 명칭 통일)
"""
import asyncio
from datetime import datetime, timedelta
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from services.order.models.order_model import Order, KokOrder, StatusMaster, KokOrderStatusHistory
# from services.order.models.order_model import HomeShoppingOrder
from services.kok.models.kok_model import KokPriceInfo
from common.database.mariadb_auth import get_maria_auth_db

async def initialize_status_master(db: AsyncSession):
    """
    STATUS_MASTER 테이블에 기본 상태 코드들을 초기화
    """
    status_codes = [
        {"status_code": "PAYMENT_COMPLETED", "status_name": "결제완료"},
        {"status_code": "PREPARING", "status_name": "상품준비중"},
        {"status_code": "SHIPPING", "status_name": "배송중"},
        {"status_code": "DELIVERED", "status_name": "배송완료"},
        {"status_code": "CANCELLED", "status_name": "주문취소"},
        {"status_code": "REFUND_REQUESTED", "status_name": "환불요청"},
        {"status_code": "REFUND_COMPLETED", "status_name": "환불완료"}
    ]
    
    for status_data in status_codes:
        # 기존 상태 코드 확인
        existing = await get_status_by_code(db, status_data["status_code"])
        if not existing:
            # 새 상태 코드 추가
            new_status = StatusMaster(
                status_code=status_data["status_code"],
                status_name=status_data["status_name"]
            )
            db.add(new_status)
    
    await db.commit()

async def validate_user_exists(user_id: int, db: AsyncSession) -> bool:
    """
    사용자 ID가 유효한지 검증 (AUTH_DB.USERS 테이블 확인)
    """
    from services.user.models.user_model import User
    
    # AUTH_DB에서 사용자 조회
    auth_db = get_maria_auth_db()
    async for auth_session in auth_db:
        result = await auth_session.execute(
            select(User).where(User.user_id == user_id)
        )
        user = result.scalars().first()
        return user is not None
    
    return False

async def get_status_by_code(db: AsyncSession, status_code: str) -> StatusMaster:
    """
    상태 코드로 상태 정보 조회
    """
    result = await db.execute(
        select(StatusMaster).where(StatusMaster.status_code == status_code)
    )
    return result.scalars().first()

async def get_current_status(db: AsyncSession, kok_order_id: int) -> KokOrderStatusHistory:
    """
    주문의 현재 상태 조회 (가장 최근 이력)
    """
    result = await db.execute(
        select(KokOrderStatusHistory)
        .where(KokOrderStatusHistory.kok_order_id == kok_order_id)
        .order_by(desc(KokOrderStatusHistory.changed_at))
        .limit(1)
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
    try:
        # 0. 사용자 ID 유효성 검증
        if not await validate_user_exists(user_id, db):
            raise Exception("유효하지 않은 사용자 ID입니다")
        
        # 1. 할인 가격 조회
        result = await db.execute(
            select(KokPriceInfo.kok_discounted_price)
            .where(KokPriceInfo.kok_price_id == kok_price_id) # type: ignore
        )
        discounted_price = result.scalar_one_or_none()
        if discounted_price is None:
            raise Exception(f"해당 kok_price_id({kok_price_id})에 해당하는 할인 가격 없음")

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
            order_price=order_price
        )
        db.add(new_kok_order)
        await db.flush()  # kok_order_id 생성

        # 4-3. 상태 변경 이력 생성 (초기 상태)
        status_history = KokOrderStatusHistory(
            kok_order_id=new_kok_order.kok_order_id,
            status_id=payment_completed_status.status_id,
            changed_by=user_id
        )
        db.add(status_history)

        await db.commit()
        await db.refresh(new_order)
        return new_order
        
    except Exception as e:
        await db.rollback()
        print(f"주문 생성 실패: {str(e)}")
        raise e

async def update_kok_order_status(
        db: AsyncSession,
        kok_order_id: int,
        new_status_code: str,
        changed_by: int = None
) -> KokOrder:
    """
    콕 주문 상태 업데이트 (INSERT만 사용)
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

    # 3. 상태 변경 이력 생성 (UPDATE 없이 INSERT만)
    status_history = KokOrderStatusHistory(
        kok_order_id=kok_order_id,
        status_id=new_status.status_id,
        changed_by=changed_by
    )
    db.add(status_history)

    await db.commit()
    await db.refresh(kok_order)
    return kok_order

async def get_kok_order_with_current_status(db: AsyncSession, kok_order_id: int):
    """
    콕 주문과 현재 상태 정보를 함께 조회 (가장 최근 이력 사용)
    """
    # 주문 조회
    result = await db.execute(
        select(KokOrder).where(KokOrder.kok_order_id == kok_order_id)
    )
    kok_order = result.scalars().first()
    
    if not kok_order:
        return None
    
    # 현재 상태 조회 (가장 최근 이력)
    current_status_history = await get_current_status(db, kok_order_id)
    
    if current_status_history:
        # 상태 정보 조회
        status_result = await db.execute(
            select(StatusMaster).where(StatusMaster.status_id == current_status_history.status_id)
        )
        current_status = status_result.scalars().first()
        return kok_order, current_status, current_status_history
    
    # 상태 이력이 없는 경우 기본 상태 반환
    return kok_order, None, None

async def get_kok_order_status_history(db: AsyncSession, kok_order_id: int):
    """
    콕 주문의 상태 변경 이력 조회
    """
    result = await db.execute(
        select(KokOrderStatusHistory, StatusMaster)
        .join(StatusMaster, KokOrderStatusHistory.status_id == StatusMaster.status_id)
        .where(KokOrderStatusHistory.kok_order_id == kok_order_id)
        .order_by(desc(KokOrderStatusHistory.changed_at))
    )
    
    # Row 객체들을 KokOrderStatusHistorySchema 형태로 변환
    history_list = []
    for row in result.all():
        history_obj, status_obj = row
        # KokOrderStatusHistory 객체에 status 속성 추가
        history_obj.status = status_obj
        history_list.append(history_obj)
    
    return history_list

async def auto_update_order_status(kok_order_id: int, db: AsyncSession):
    """
    주문 후 자동으로 상태를 업데이트하는 임시 함수
    PAYMENT_COMPLETED -> PREPARING -> SHIPPING -> DELIVERED 순서로 업데이트
    """
    status_sequence = [
        "PAYMENT_COMPLETED",
        "PREPARING", 
        "SHIPPING",
        "DELIVERED"
    ]
    
    for i, status_code in enumerate(status_sequence):
        try:
            # 5초 대기 (첫 번째 상태는 이미 설정되어 있으므로 건너뜀)
            if i > 0:
                await asyncio.sleep(5)
            
            # 상태 업데이트
            await update_kok_order_status(
                db=db,
                kok_order_id=kok_order_id,
                new_status_code=status_code,
                changed_by=1  # 시스템 자동 업데이트
            )
            
            print(f"주문 {kok_order_id} 상태가 '{status_code}'로 업데이트되었습니다.")
            
        except Exception as e:
            print(f"주문 {kok_order_id} 상태 업데이트 실패: {str(e)}")
            break

async def start_auto_status_update(kok_order_id: int, db_session_generator):
    """
    백그라운드에서 자동 상태 업데이트를 시작하는 함수
    """
    async for db in db_session_generator:
        try:
            await auto_update_order_status(kok_order_id, db)
        except Exception as e:
            print(f"자동 상태 업데이트 중 오류 발생: {str(e)}")
        finally:
            await db.close()
        break  # 한 번만 실행

# async def create_homeshopping_order(db: AsyncSession, user_id: int, live_id: int) -> Order:
#     """
#     HomeShopping 주문 생성 (트랜잭션)
#     """
#     # 사용자 ID 유효성 검증
#     if not await validate_user_exists(user_id, db):
#         raise Exception("유효하지 않은 사용자 ID입니다")
#     
#     order = Order(user_id=user_id, order_time=datetime.now())
#     db.add(order)
#     await db.flush()
#     homeshopping_order = HomeShoppingOrder(order_id=order.order_id, live_id=live_id)
#     db.add(homeshopping_order)
#     await db.commit()
#     await db.refresh(order)
#     return order

async def get_order_by_id(db: AsyncSession, order_id: int) -> dict:
    """
    주문 ID로 통합 주문 조회 (공통 정보 + 서비스별 상세)
    """
    # 주문 기본 정보 조회
    result = await db.execute(
        select(Order).where(Order.order_id == order_id)
    )
    order = result.scalars().first()
    
    if not order:
        return None
    
    # 콕 주문 정보 조회
    kok_result = await db.execute(
        select(KokOrder).where(KokOrder.order_id == order.order_id)
    )
    kok_order = kok_result.scalars().first()
    
    # 딕셔너리 형태로 반환
    return {
        "order_id": order.order_id,
        "user_id": order.user_id,
        "order_time": order.order_time,
        "cancel_time": order.cancel_time,
        "kok_order": kok_order,
        "homeshopping_order": None
    }
