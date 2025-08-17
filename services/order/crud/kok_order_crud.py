import asyncio
from datetime import datetime
from sqlalchemy import select, desc, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from services.order.models.order_model import (
    Order, KokOrder, StatusMaster, KokOrderStatusHistory
)
from services.kok.models.kok_model import (
    KokPriceInfo, KokNotification, KokCart, KokProductInfo
)
from services.order.crud.order_crud import (
    validate_user_exists, get_status_by_code,
    NOTIFICATION_TITLES, NOTIFICATION_MESSAGES
)

from common.logger import get_logger
from typing import List

logger = get_logger(__name__)

async def create_orders_from_selected_carts(
    db: AsyncSession,
    user_id: int,
    selected_items: List[dict],  # [{"cart_id": int, "quantity": int}]
) -> dict:
    """
    장바구니에서 선택된 항목들로 한 번에 주문 생성
    - 각 선택 항목에 대해 kok_price_id를 조회하여 KokOrder를 생성
    - KokCart.recipe_id가 있으면 KokOrder.recipe_id로 전달
    - 처리 후 선택된 장바구니 항목 삭제
    """
    if not selected_items:
        raise ValueError("선택된 항목이 없습니다.")

    main_order = Order(user_id=user_id, order_time=datetime.now())
    db.add(main_order)
    await db.flush()

    # 필요한 데이터 일괄 조회
    cart_ids = [item["cart_id"] for item in selected_items]

    stmt = (
        select(KokCart, KokProductInfo, KokPriceInfo)
        .join(KokProductInfo, KokCart.kok_product_id == KokProductInfo.kok_product_id)
        .outerjoin(KokPriceInfo, KokProductInfo.kok_product_id == KokPriceInfo.kok_product_id)
        .where(KokCart.kok_cart_id.in_(cart_ids))
        .where(KokCart.user_id == user_id)
    )
    rows = (await db.execute(stmt)).all()
    if not rows:
        raise ValueError("선택된 장바구니 항목을 찾을 수 없습니다.")

    # 초기 상태: 주문접수
    order_received_status = await get_status_by_code(db, "ORDER_RECEIVED")
    if not order_received_status:
        raise ValueError("주문접수 상태 코드를 찾을 수 없습니다.")

    total_created = 0
    created_kok_order_ids: List[int] = []
    for cart, product, price in rows:
        # 선택 항목의 수량 찾기
        quantity = next((i["quantity"] for i in selected_items if i["cart_id"] == cart.kok_cart_id), None)
        if quantity is None:
            continue
        if not price:
            continue

        # 주문 항목 생성
        new_kok_order = KokOrder(
            order_id=main_order.order_id,
            kok_price_id=price.kok_price_id,
            kok_product_id=product.kok_product_id,
            quantity=quantity,
            order_price=(price.kok_discounted_price or product.kok_product_price) * quantity,
            recipe_id=cart.recipe_id,
        )
        db.add(new_kok_order)
        # kok_order_id 확보
        await db.flush()
        total_created += 1

        # 상태 이력 기록 (주문접수)
        status_history = KokOrderStatusHistory(
            kok_order_id=new_kok_order.kok_order_id,
            status_id=order_received_status.status_id,
            changed_by=user_id,
        )
        db.add(status_history)

        # 초기 알림 생성 (주문접수)
        await create_kok_notification_for_status_change(
            db=db,
            kok_order_id=new_kok_order.kok_order_id,
            status_id=order_received_status.status_id,
            user_id=user_id,
        )

        created_kok_order_ids.append(new_kok_order.kok_order_id)

    await db.flush()

    # 선택된 장바구니 삭제
    await db.execute(delete(KokCart).where(KokCart.kok_cart_id.in_(cart_ids)))
    await db.commit()
    
    # 1초 후 PAYMENT_REQUESTED 상태로 변경 (백그라운드 작업)
    
    async def update_status_to_payment_requested():
        await asyncio.sleep(1)  # 1초 대기
        
        try:
            # 각 주문에 대해 상태 변경 및 알림 생성
            for kok_order_id in created_kok_order_ids:
                await update_kok_order_status(
                    db=db,
                    kok_order_id=kok_order_id,
                    new_status_code="PAYMENT_REQUESTED",
                    changed_by=user_id
                )
            
            logger.info(f"콕 주문 상태 변경 완료: order_id={main_order.order_id}, status=PAYMENT_REQUESTED, count={len(created_kok_order_ids)}")
                
        except Exception as e:
            logger.error(f"콕 주문 상태 변경 실패: order_id={main_order.order_id}, error={str(e)}")
    
    # 백그라운드에서 상태 변경 실행
    asyncio.create_task(update_status_to_payment_requested())

    return {
        "order_id": main_order.order_id,
        "order_count": total_created,
        "message": f"{total_created}개의 상품이 주문되었습니다.",
        "kok_order_ids": created_kok_order_ids,
    }


async def get_kok_current_status(db: AsyncSession, kok_order_id: int) -> KokOrderStatusHistory:
    """
    콕 주문의 현재 상태(가장 최근 상태 이력) 조회
    """
    result = await db.execute(
        select(KokOrderStatusHistory)
        .where(KokOrderStatusHistory.kok_order_id == kok_order_id)
        .order_by(desc(KokOrderStatusHistory.changed_at))
        .limit(1)
    )
    return result.scalars().first()

async def create_kok_notification_for_status_change(
    db: AsyncSession, 
    kok_order_id: int, 
    status_id: int, 
    user_id: int
):
    """
    주문 상태 변경 시 알림 생성
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
    notification = KokNotification(
        user_id=user_id,
        kok_order_id=kok_order_id,
        status_id=status_id,
        title=title,
        message=message
    )
    
    db.add(notification)
    await db.commit()


async def update_kok_order_status(
        db: AsyncSession,
        kok_order_id: int,
        new_status_code: str,
        changed_by: int = None
) -> KokOrder:
    """
    콕 주문 상태 업데이트 (INSERT만 사용) + 알림 생성
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

    # 3. 주문자 ID 조회
    order_result = await db.execute(
        select(Order).where(Order.order_id == kok_order.order_id)
    )
    order = order_result.scalars().first()
    if not order:
        raise Exception("주문 정보를 찾을 수 없습니다")

    # 4. 상태 변경 이력 생성 (UPDATE 없이 INSERT만)
    status_history = KokOrderStatusHistory(
        kok_order_id=kok_order_id,
        status_id=new_status.status_id,
        changed_by=changed_by
    )
    db.add(status_history)

    # 5. 알림 생성
    await create_kok_notification_for_status_change(
        db=db,
        kok_order_id=kok_order_id,
        status_id=new_status.status_id,
        user_id=order.user_id
    )

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
    current_status_history = await get_kok_current_status(db, kok_order_id)
    
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
            # 첫 단계는 이미 설정되었을 수 있으므로 건너뜀
            if i == 0:
                logger.info(f"주문 {kok_order_id} 상태가 '{status_code}'로 이미 설정되어 있습니다.")
                continue
                
            # 5초 대기
            await asyncio.sleep(5)
            
            # 상태 업데이트
            await update_kok_order_status(
                db=db,
                kok_order_id=kok_order_id,
                new_status_code=status_code,
                changed_by=1  # 시스템 자동 업데이트
            )
            
            logger.info(f"주문 {kok_order_id} 상태가 '{status_code}'로 업데이트되었습니다.")
            
        except Exception as e:
            logger.error(f"주문 {kok_order_id} 상태 업데이트 실패: {str(e)}")
            break


async def start_auto_kok_order_status_update(kok_order_id: int, db_session_generator):
    """
    백그라운드에서 자동 상태 업데이트를 시작하는 함수
    """
    async for db in db_session_generator:
        try:
            await auto_update_order_status(kok_order_id, db)
        except Exception as e:
            logger.error(f"자동 상태 업데이트 중 오류 발생: {str(e)}")
        finally:
            await db.close()
        break  # 한 번만 실행


async def get_kok_order_notifications_history(
    db: AsyncSession, 
    user_id: int, 
    limit: int = 20, 
    offset: int = 0
) -> tuple[List[KokNotification], int]:
    """
    사용자의 콕 상품 주문 내역 현황 알림 조회
    주문완료, 배송출발, 배송완료 알림만 조회
    """
    # 주문 현황 관련 상태 코드들
    order_status_codes = ["PAYMENT_COMPLETED", "SHIPPING", "DELIVERED"]
    
    # 전체 개수 조회
    count_result = await db.execute(
        select(func.count(KokNotification.notification_id))
        .join(StatusMaster, KokNotification.status_id == StatusMaster.status_id)
        .where(KokNotification.user_id == user_id)
        .where(StatusMaster.status_code.in_(order_status_codes))
    )
    total_count = count_result.scalar()
    
    # 알림 목록 조회 (주문 현황 관련 알림만)
    result = await db.execute(
        select(KokNotification)
        .join(StatusMaster, KokNotification.status_id == StatusMaster.status_id)
        .where(KokNotification.user_id == user_id)
        .where(StatusMaster.status_code.in_(order_status_codes))
        .order_by(desc(KokNotification.created_at))
        .limit(limit)
        .offset(offset)
    )
    notifications = result.scalars().all()
    
    return notifications, total_count


# ------------------------------------------------------------------------------------------------
# 콕 주문 생성 함수
# ------------------------------------------------------------------------------------------------  
# async def create_kok_order(
#         db: AsyncSession,
#         user_id: int,
#         kok_price_id: int,
#         kok_product_id: int,
#         quantity: int = 1,
#         recipe_id: int | None = None
# ) -> Order:
#     """
#     콕 상품 주문 생성 및 할인 가격 반영
#     - kok_price_id로 할인 가격 조회 후 quantity 곱해서 order_price 자동계산
#     - 기본 상태는 'PAYMENT_COMPLETED'로 설정
#     - 주문 생성 시 초기 알림도 생성
#     """
#     try:
#         # 0. 사용자 ID 유효성 검증
#         if not await validate_user_exists(user_id, db):
#             raise Exception("유효하지 않은 사용자 ID입니다")
        
#         # 1. 할인 가격 조회
#         result = await db.execute(
#             select(KokPriceInfo.kok_discounted_price)
#             .where(KokPriceInfo.kok_price_id == kok_price_id) # type: ignore
#         )
#         discounted_price = result.scalar_one_or_none()
#         if discounted_price is None:
#             raise Exception(f"해당 kok_price_id({kok_price_id})에 해당하는 할인 가격 없음")

#         # 2. 주문가격 계산
#         order_price = discounted_price * quantity

#         # 3. 주문접수 상태 조회
#         order_received_status = await get_status_by_code(db, "ORDER_RECEIVED")
#         if not order_received_status:
#             raise Exception("주문접수 상태 코드를 찾을 수 없습니다")

#         # 4. 주문 데이터 생성 (트랜잭션)
#         # 4-1. 상위 주문 생성
#         new_order = Order(
#             user_id=user_id,
#             order_time=datetime.now()
#         )
#         db.add(new_order)
#         await db.flush()  # order_id 생성

#         # 4-2. 콕 주문 상세 생성
#         new_kok_order = KokOrder(
#             order_id=new_order.order_id,
#             kok_price_id=kok_price_id,
#             kok_product_id=kok_product_id,
#             quantity=quantity,
#             order_price=order_price,
#             recipe_id=recipe_id
#         )
#         db.add(new_kok_order)
#         await db.flush()  # kok_order_id 생성

#         # 4-3. 상태 변경 이력 생성 (초기 상태: ORDER_RECEIVED)
#         status_history = KokOrderStatusHistory(
#             kok_order_id=new_kok_order.kok_order_id,
#             status_id=order_received_status.status_id,
#             changed_by=user_id
#         )
#         db.add(status_history)

#         # 4-4. 초기 알림 생성 (ORDER_RECEIVED)
#         await create_kok_notification_for_status_change(
#             db=db,
#             kok_order_id=new_kok_order.kok_order_id,
#             status_id=order_received_status.status_id,
#             user_id=user_id
#         )

#         await db.commit()
        
#         # 5. 1초 후 PAYMENT_REQUESTED 상태로 변경 (백그라운드 작업)
#         async def update_status_to_payment_requested():
#             await asyncio.sleep(1)  # 1초 대기
            
#             try:
#                 # PAYMENT_REQUESTED 상태 조회
#                 payment_requested_status = await get_status_by_code(db, "PAYMENT_REQUESTED")
#                 if payment_requested_status:
#                     # 상태 이력 추가
#                     new_status_history = KokOrderStatusHistory(
#                         kok_order_id=new_kok_order.kok_order_id,
#                         status_id=payment_requested_status.status_id,
#                         changed_by=user_id
#                     )
                    
#                     # 결제 요청 알림 생성
#                     await create_kok_notification_for_status_change(
#                         db=db,
#                         kok_order_id=new_kok_order.kok_order_id,
#                         status_id=payment_requested_status.status_id,
#                         user_id=user_id
#                     )
                    
#                     db.add(new_status_history)
#                     await db.commit()
                    
#                     logger.info(f"콕 주문 상태 변경 완료: order_id={new_order.order_id}, status=PAYMENT_REQUESTED")
                    
#             except Exception as e:
#                 logger.error(f"콕 주문 상태 변경 실패: order_id={new_order.order_id}, error={str(e)}")
        
#         # 백그라운드에서 상태 변경 실행
#         asyncio.create_task(update_status_to_payment_requested())
        
#         await db.refresh(new_order)
#         return new_order
        
#     except Exception as e:
#         await db.rollback()
#         logger.error(f"주문 생성 실패: {str(e)}")
#         raise e
