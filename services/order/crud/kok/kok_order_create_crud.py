"""Kok order creation CRUD functions."""

from typing import List
from datetime import datetime

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from common.logger import get_logger
from services.order.models.order_base_model import Order
from services.order.models.kok.kok_order_model import KokOrder, KokOrderStatusHistory
from services.kok.models.interaction_model import KokCart
from services.kok.models.product_model import KokProductInfo
from services.order.crud.order_common import get_status_by_code
from services.order.crud.kok.kok_order_price_crud import calculate_kok_order_price, debug_cart_status
from services.order.crud.kok.kok_order_status_crud import create_kok_notification_for_status_change

logger = get_logger("kok_order_crud")

async def create_orders_from_selected_carts(
    db: AsyncSession,
    user_id: int,
    selected_items: List[dict],  # [{"kok_cart_id": int, "quantity": int}]
) -> dict:
    """
    장바구니에서 선택된 항목들로 한 번에 주문 생성
    
    Args:
        db: 데이터베이스 세션
        user_id: 주문하는 사용자 ID
        selected_items: 선택된 장바구니 항목 목록 [{"kok_cart_id": int, "quantity": int}]
    
    Returns:
        dict: 주문 생성 결과 (order_id, total_amount, order_count, order_details, message, order_time, kok_order_ids)
        
    Note:
        - CRUD 계층: DB 트랜잭션 처리 담당
        - 각 선택 항목에 대해 KokCart.kok_price_id를 직접 사용하여 KokOrder를 생성
        - KokCart.recipe_id가 있으면 KokOrder.recipe_id로 전달
        - 처리 후 선택된 장바구니 항목 삭제
        - 주문 접수 상태로 초기화하고 알림 생성
    """
    if not selected_items:
        raise ValueError("선택된 항목이 없습니다.")

    main_order = Order(user_id=user_id, order_time=datetime.now())
    db.add(main_order)
    await db.flush()

    # 필요한 데이터 일괄 조회
    kok_cart_ids = [item["kok_cart_id"] for item in selected_items]

    stmt = (
        select(KokCart, KokProductInfo)
        .join(KokProductInfo, KokCart.kok_product_id == KokProductInfo.kok_product_id)
        .where(KokCart.kok_cart_id.in_(kok_cart_ids))
        .where(KokCart.user_id == user_id)
    )
    try:
        rows = (await db.execute(stmt)).all()
    except Exception as e:
        logger.error(f"선택된 장바구니 항목 조회 SQL 실행 실패: user_id={user_id}, kok_cart_ids={kok_cart_ids}, error={str(e)}")
        raise
    
    if not rows:
        logger.warning(f"선택된 장바구니 항목을 찾을 수 없음: user_id={user_id}, kok_cart_ids={kok_cart_ids}")
        
        # 디버깅 정보 수집
        debug_info = await debug_cart_status(db, user_id, kok_cart_ids)
        logger.warning(f"장바구니 디버깅 정보: {debug_info}")
        
        raise ValueError("선택된 장바구니 항목을 찾을 수 없습니다.")

    # 초기 상태: 주문접수
    order_received_status = await get_status_by_code(db, "ORDER_RECEIVED")
    if not order_received_status:
        logger.warning(f"주문접수 상태 코드를 찾을 수 없음: user_id={user_id}")
        raise ValueError("주문접수 상태 코드를 찾을 수 없습니다.")

    total_created = 0
    total_amount = 0
    order_details: List[dict] = []
    created_kok_order_ids: List[int] = []
    
    for cart, product in rows:
        # 선택 항목의 수량 찾기
        quantity = next((i["quantity"] for i in selected_items if i["kok_cart_id"] == cart.kok_cart_id), None)
        if quantity is None:
            continue
        
        # KokCart의 kok_price_id를 직접 사용
        if not cart.kok_price_id:
            logger.warning(f"장바구니에 가격 정보가 없음: kok_cart_id={cart.kok_cart_id}, user_id={user_id}")
            continue

        # 주문 금액 계산 (별도 함수 사용)
        price_info = await calculate_kok_order_price(db, cart.kok_price_id, product.kok_product_id, quantity)
        order_price = price_info["order_price"]
        unit_price = price_info["unit_price"]

        # 주문 항목 생성
        new_kok_order = KokOrder(
            order_id=main_order.order_id,
            kok_price_id=cart.kok_price_id,
            kok_product_id=product.kok_product_id,
            quantity=quantity,
            order_price=order_price,
            recipe_id=cart.recipe_id,
        )
        db.add(new_kok_order)
        # kok_order_id 확보
        await db.flush()
        total_created += 1
        total_amount += order_price

        # 주문 상세 정보 저장
        order_details.append({
            "kok_order_id": new_kok_order.kok_order_id,
            "kok_product_id": product.kok_product_id,
            "kok_product_name": product.kok_product_name,
            "quantity": quantity,
            "unit_price": unit_price,
            "total_price": order_price
        })

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
    await db.execute(delete(KokCart).where(KokCart.kok_cart_id.in_(kok_cart_ids)))
    await db.commit()

    return {
        "order_id": main_order.order_id,
        "total_amount": total_amount,
        "order_count": total_created,
        "order_details": order_details,
        "message": f"{total_created}개의 상품이 주문되었습니다.",
        "order_time": main_order.order_time,
        "kok_order_ids": created_kok_order_ids,
    }

