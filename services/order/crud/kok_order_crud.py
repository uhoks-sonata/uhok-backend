"""
콕 주문 관련 CRUD 함수들
CRUD 계층: 모든 DB 트랜잭션 처리 담당
"""
import asyncio
from typing import List
from datetime import datetime
from sqlalchemy import select, desc, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from common.database.mariadb_service import get_maria_service_db
from common.logger import get_logger

from services.order.models.order_model import (
    Order, 
    KokOrder, 
    StatusMaster, 
    KokOrderStatusHistory
)
from services.kok.models.kok_model import (
    KokPriceInfo, 
    KokCart, 
    KokProductInfo,
    KokNotification
)
from services.order.crud.order_common import (
    get_status_by_code,
    NOTIFICATION_TITLES, NOTIFICATION_MESSAGES
)

logger = get_logger("kok_order_crud")

async def calculate_kok_order_price(
    db: AsyncSession,
    kok_price_id: int,
    kok_product_id: int,
    quantity: int = 1
) -> dict:
    """
    콕 주문 금액 계산 (최적화: Raw SQL 사용)
    
    Args:
        db: 데이터베이스 세션
        kok_price_id: 콕 가격 정보 ID
        kok_product_id: 콕 상품 ID
        quantity: 수량 (기본값: 1)
    
    Returns:
        dict: 가격 정보 (kok_price_id, kok_product_id, unit_price, quantity, order_price, product_name)
        
    Note:
        - CRUD 계층: DB 조회만 담당, 트랜잭션 변경 없음
        - Raw SQL을 사용하여 성능 최적화
        - 할인 가격이 있으면 할인 가격 사용, 없으면 상품 기본 가격 사용
        - 최종 주문 금액 = 단가 × 수량
    """
    from sqlalchemy import text
    
    # 최적화된 쿼리: Raw SQL 사용 (모델 기반으로 수정)
    sql_query = """
    SELECT 
        kpi.kok_price_id,
        kpi.kok_product_id,
        kpi.kok_discounted_price,
        kpi.kok_discount_rate,
        kpr.kok_product_price,
        kpr.kok_product_name,
        COALESCE(kpi.kok_discounted_price, kpr.kok_product_price, 0) as unit_price
    FROM FCT_KOK_PRICE_INFO kpi
    LEFT JOIN FCT_KOK_PRODUCT_INFO kpr ON kpi.kok_product_id = kpr.kok_product_id
    WHERE kpi.kok_price_id = :kok_price_id
    """
    
    try:
        result = await db.execute(text(sql_query), {"kok_price_id": kok_price_id})
        price_data = result.fetchone()
    except Exception as e:
        logger.error(f"콕 가격 정보 조회 SQL 실행 실패: kok_price_id={kok_price_id}, error={str(e)}")
        raise
    
    if not price_data:
        logger.warning(f"콕 할인 가격 정보를 찾을 수 없음: kok_price_id={kok_price_id}")
        raise ValueError("할인 가격 정보를 찾을 수 없습니다.")
    
    # 주문 금액 계산
    unit_price = price_data.unit_price
    order_price = unit_price * quantity
    
    return {
        "kok_price_id": kok_price_id,
        "kok_product_id": kok_product_id,
        "unit_price": unit_price,
        "quantity": quantity,
        "order_price": order_price,
        "product_name": price_data.kok_product_name or f"상품_{kok_product_id}"
    }


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

async def get_kok_current_status(db: AsyncSession, kok_order_id: int) -> KokOrderStatusHistory:
    """
    콕 주문의 현재 상태(가장 최근 상태 이력) 조회 (최적화: JOIN으로 N+1 문제 해결)
    
    Args:
        db: 데이터베이스 세션
        kok_order_id: 콕 주문 ID
    
    Returns:
        KokOrderStatusHistory: 가장 최근 상태 이력 객체 (없으면 None)
        
    Note:
        - CRUD 계층: DB 조회만 담당, 트랜잭션 변경 없음
        - JOIN을 사용하여 상태 정보를 한 번에 조회하여 N+1 문제 해결
        - changed_at 기준으로 내림차순 정렬하여 가장 최근 상태 반환
    """
    from sqlalchemy import text
    
    # 최적화된 쿼리: JOIN을 사용하여 상태 정보를 한 번에 조회
    sql_query = """
    SELECT 
        kosh.history_id,
        kosh.kok_order_id,
        kosh.status_id,
        kosh.changed_at,
        kosh.changed_by,
        sm.status_code,
        sm.status_name
    FROM KOK_ORDER_STATUS_HISTORY kosh
    INNER JOIN STATUS_MASTER sm ON kosh.status_id = sm.status_id
    WHERE kosh.kok_order_id = :kok_order_id
    ORDER BY kosh.changed_at DESC
    LIMIT 1
    """
    
    try:
        result = await db.execute(text(sql_query), {"kok_order_id": kok_order_id})
        status_data = result.fetchone()
    except Exception as e:
        logger.error(f"콕 주문 현재 상태 조회 SQL 실행 실패: kok_order_id={kok_order_id}, error={str(e)}")
        return None
    
    if not status_data:
        return None
    
    # KokOrderStatusHistory 객체 생성
    status_history = KokOrderStatusHistory()
    status_history.history_id = status_data.history_id
    status_history.kok_order_id = status_data.kok_order_id
    status_history.status_id = status_data.status_id
    status_history.changed_at = status_data.changed_at
    status_history.changed_by = status_data.changed_by
    
    # StatusMaster 객체 생성 및 설정
    status = StatusMaster()
    status.status_id = status_data.status_id
    status.status_code = status_data.status_code
    status.status_name = status_data.status_name
    status_history.status = status
    
    return status_history


async def create_kok_notification_for_status_change(
    db: AsyncSession, 
    kok_order_id: int, 
    status_id: int, 
    user_id: int
):
    """
    주문 상태 변경 시 알림 생성
    
    Args:
        db: 데이터베이스 세션
        kok_order_id: 콕 주문 ID
        status_id: 상태 ID
        user_id: 사용자 ID
    
    Returns:
        None
        
    Note:
        - 주문 상태 변경 시 자동으로 알림 생성
        - NOTIFICATION_TITLES와 NOTIFICATION_MESSAGES에서 상태별 메시지 조회
        - KokNotification 테이블에 알림 정보 저장
    """
    # 상태 정보 조회
    try:
        status_result = await db.execute(
            select(StatusMaster).where(StatusMaster.status_id == status_id)
        )
        status = status_result.scalars().first()
    except Exception as e:
        logger.error(f"상태 정보 조회 SQL 실행 실패: status_id={status_id}, error={str(e)}")
        return
    
    if not status:
        logger.warning(f"상태 정보를 찾을 수 없음: status_id={status_id}")
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
    
    Args:
        db: 데이터베이스 세션
        kok_order_id: 콕 주문 ID
        new_status_code: 새로운 상태 코드
        changed_by: 상태 변경을 수행한 사용자 ID (기본값: None)
    
    Returns:
        KokOrder: 업데이트된 콕 주문 객체
        
    Note:
        - 기존 상태를 UPDATE하지 않고 새로운 상태 이력을 INSERT
        - 상태 변경 시 자동으로 알림 생성
        - 트랜잭션으로 처리하여 일관성 보장
    """
    # 1. 새로운 상태 조회
    new_status = await get_status_by_code(db, new_status_code)
    if not new_status:
        logger.warning(f"상태 코드를 찾을 수 없음: new_status_code={new_status_code}, kok_order_id={kok_order_id}")
        raise Exception(f"상태 코드 '{new_status_code}'를 찾을 수 없습니다")

    # 2. 주문 조회
    try:
        result = await db.execute(
            select(KokOrder).where(KokOrder.kok_order_id == kok_order_id)
        )
        kok_order = result.scalars().first()
    except Exception as e:
        logger.error(f"콕 주문 조회 SQL 실행 실패: kok_order_id={kok_order_id}, error={str(e)}")
        raise
    
    if not kok_order:
        logger.warning(f"콕 주문을 찾을 수 없음: kok_order_id={kok_order_id}")
        raise Exception("해당 주문을 찾을 수 없습니다")

    # 3. 주문자 ID 조회
    try:
        order_result = await db.execute(
            select(Order).where(Order.order_id == kok_order.order_id)
        )
        order = order_result.scalars().first()
    except Exception as e:
        logger.error(f"주문 정보 조회 SQL 실행 실패: order_id={kok_order.order_id}, error={str(e)}")
        raise
    
    if not order:
        logger.warning(f"주문 정보를 찾을 수 없음: order_id={kok_order.order_id}")
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
    콕 주문과 현재 상태 정보를 함께 조회 (최적화: 윈도우 함수 사용)
    
    Args:
        db: 데이터베이스 세션
        kok_order_id: 콕 주문 ID
    
    Returns:
        tuple: (kok_order, current_status, current_status_history) 또는 (kok_order, None, None)
        
    Note:
        - 윈도우 함수를 사용하여 주문 정보와 최신 상태 정보를 한 번에 조회
        - N+1 문제 해결 및 쿼리 성능 최적화
    """
    from sqlalchemy import text
    
    # 최적화된 쿼리: 윈도우 함수를 사용하여 주문 정보와 최신 상태 정보를 한 번에 조회
    sql_query = """
    WITH latest_status_info AS (
        SELECT 
            kosh.kok_order_id,
            kosh.status_id,
            kosh.changed_at,
            kosh.changed_by,
            sm.status_code,
            sm.status_name,
            ROW_NUMBER() OVER (
                PARTITION BY kosh.kok_order_id 
                ORDER BY kosh.changed_at DESC
            ) as rn
        FROM KOK_ORDER_STATUS_HISTORY kosh
        INNER JOIN STATUS_MASTER sm ON kosh.status_id = sm.status_id
        WHERE kosh.kok_order_id = :kok_order_id
    )
    SELECT 
        ko.kok_order_id,
        ko.order_id,
        ko.kok_price_id,
        ko.kok_product_id,
        ko.quantity,
        ko.order_price,
        ko.recipe_id,
        COALESCE(ls.status_id, 1) as current_status_id,
        COALESCE(ls.status_code, 'ORDER_RECEIVED') as current_status_code,
        COALESCE(ls.status_name, '주문 접수') as current_status_name,
        ls.changed_at as status_changed_at,
        ls.changed_by as status_changed_by
    FROM KOK_ORDERS ko
    LEFT JOIN latest_status_info ls ON ko.kok_order_id = ls.kok_order_id AND ls.rn = 1
    WHERE ko.kok_order_id = :kok_order_id
    """
    
    try:
        result = await db.execute(text(sql_query), {"kok_order_id": kok_order_id})
        order_data = result.fetchone()
    except Exception as e:
        logger.error(f"콕 주문 조회 SQL 실행 실패: kok_order_id={kok_order_id}, error={str(e)}")
        return None
    
    if not order_data:
        logger.warning(f"콕 주문을 찾을 수 없음: kok_order_id={kok_order_id}")
        return None
    
    # KokOrder 객체 생성
    kok_order = KokOrder()
    kok_order.kok_order_id = order_data.kok_order_id
    kok_order.order_id = order_data.order_id
    kok_order.kok_price_id = order_data.kok_price_id
    kok_order.kok_product_id = order_data.kok_product_id
    kok_order.quantity = order_data.quantity
    kok_order.order_price = order_data.order_price
    kok_order.recipe_id = order_data.recipe_id
    
    # 상태 정보가 있는 경우
    if order_data.current_status_id and order_data.current_status_code != 'ORDER_RECEIVED':
        # StatusMaster 객체 생성
        current_status = StatusMaster()
        current_status.status_id = order_data.current_status_id
        current_status.status_code = order_data.current_status_code
        current_status.status_name = order_data.current_status_name
        
        # KokOrderStatusHistory 객체 생성
        current_status_history = KokOrderStatusHistory()
        current_status_history.kok_order_id = order_data.kok_order_id
        current_status_history.status_id = order_data.current_status_id
        current_status_history.changed_at = order_data.status_changed_at
        current_status_history.changed_by = order_data.status_changed_by
        current_status_history.status = current_status
        
        return kok_order, current_status, current_status_history
    
    # 상태 이력이 없는 경우 기본 상태 반환
    return kok_order, None, None


async def get_kok_order_status_history(db: AsyncSession, kok_order_id: int):
    """
    콕 주문의 상태 변경 이력 조회 (최적화: Raw SQL 사용)
    
    Args:
        db: 데이터베이스 세션
        kok_order_id: 콕 주문 ID
    
    Returns:
        list: 상태 변경 이력 목록 (KokOrderStatusHistory 객체들)
        
    Note:
        - Raw SQL을 사용하여 성능 최적화
        - 주문의 모든 상태 변경 이력을 시간순으로 조회
        - StatusMaster와 조인하여 상태 정보 포함
        - changed_at 기준으로 내림차순 정렬
    """
    from sqlalchemy import text
    
    # 최적화된 쿼리: Raw SQL 사용
    sql_query = """
    SELECT 
        kosh.history_id,
        kosh.kok_order_id,
        kosh.status_id,
        kosh.changed_at,
        kosh.changed_by,
        sm.status_code,
        sm.status_name
    FROM KOK_ORDER_STATUS_HISTORY kosh
    INNER JOIN STATUS_MASTER sm ON kosh.status_id = sm.status_id
    WHERE kosh.kok_order_id = :kok_order_id
    ORDER BY kosh.changed_at DESC
    """
    
    try:
        result = await db.execute(text(sql_query), {"kok_order_id": kok_order_id})
        status_histories_data = result.fetchall()
    except Exception as e:
        logger.error(f"콕 주문 상태 이력 조회 SQL 실행 실패: kok_order_id={kok_order_id}, error={str(e)}")
        return []
    
    # 결과를 KokOrderStatusHistory 객체로 변환
    history_list = []
    for row in status_histories_data:
        # KokOrderStatusHistory 객체 생성
        history_obj = KokOrderStatusHistory()
        history_obj.history_id = row.history_id
        history_obj.kok_order_id = row.kok_order_id
        history_obj.status_id = row.status_id
        history_obj.changed_at = row.changed_at
        history_obj.changed_by = row.changed_by
        
        # StatusMaster 객체 생성 및 설정
        status_obj = StatusMaster()
        status_obj.status_id = row.status_id
        status_obj.status_code = row.status_code
        status_obj.status_name = row.status_name
        history_obj.status = status_obj
        
        history_list.append(history_obj)
    
    return history_list


async def auto_update_order_status(kok_order_id: int, db: AsyncSession):
    """
    주문 후 자동으로 상태를 업데이트하는 임시 함수
    
    Args:
        kok_order_id: 콕 주문 ID
        db: 데이터베이스 세션
    
    Returns:
        None
        
    Note:
        - PAYMENT_COMPLETED -> PREPARING -> SHIPPING -> DELIVERED 순서로 자동 업데이트
        - 각 단계마다 5초 대기
        - 첫 단계(PAYMENT_COMPLETED)는 이미 설정되어 있을 수 있으므로 건너뜀
        - 시스템 자동 업데이트 (changed_by=1)
    """
    status_sequence = [
        "PAYMENT_COMPLETED",
        "PREPARING", 
        "SHIPPING",
        "DELIVERED"
    ]
    
    logger.info(f"콕 주문 자동 상태 업데이트 시작: order_id={kok_order_id}")
    
    for i, status_code in enumerate(status_sequence):
        try:
            # 첫 단계는 이미 설정되었을 수 있으므로 건너뜀
            if i == 0:
                logger.info(f"콕 주문 {kok_order_id} 상태가 '{status_code}'로 이미 설정되어 있습니다.")
                continue
                
            # 2초 대기
            logger.info(f"콕 주문 {kok_order_id} 상태 업데이트 대기 중... (2초 후 '{status_code}'로 변경)")
            await asyncio.sleep(2)
            
            # 상태 업데이트
            logger.info(f"콕 주문 {kok_order_id} 상태를 '{status_code}'로 업데이트 중...")
            await update_kok_order_status(
                db=db,
                kok_order_id=kok_order_id,
                new_status_code=status_code,
                changed_by=1  # 시스템 자동 업데이트
            )
            
            logger.info(f"콕 주문 {kok_order_id} 상태가 '{status_code}'로 성공적으로 업데이트되었습니다.")
            
        except Exception as e:
            logger.error(f"콕 주문 {kok_order_id} 상태 업데이트 실패: {str(e)}")
            break
    
    logger.info(f"🏁 콕 주문 자동 상태 업데이트 완료: order_id={kok_order_id}")


async def start_auto_kok_order_status_update(kok_order_id: int):
    """
    백그라운드에서 자동 상태 업데이트를 시작하는 함수
    
    Args:
        kok_order_id: 콕 주문 ID
    
    Returns:
        None
        
    Note:
        - 새로운 DB 세션을 생성하여 자동 상태 업데이트 실행
        - 백그라운드 작업 실패는 전체 프로세스를 중단하지 않음
        - 첫 번째 세션만 사용하여 리소스 효율성 확보
    """
    try:
        logger.info(f"🚀 콕 주문 자동 상태 업데이트 백그라운드 작업 시작: order_id={kok_order_id}")
        
        # 새로운 DB 세션 생성
        async for db in get_maria_service_db():
            await auto_update_order_status(kok_order_id, db)
            break  # 첫 번째 세션만 사용
            
    except Exception as e:
        logger.error(f"❌ 콕 주문 자동 상태 업데이트 백그라운드 작업 실패: kok_order_id={kok_order_id}, error={str(e)}")
        # 백그라운드 작업 실패는 전체 프로세스를 중단하지 않음


async def get_kok_order_notifications_history(
    db: AsyncSession, 
    user_id: int, 
    limit: int = 20, 
    offset: int = 0
) -> tuple[List[dict], int]:
    """
    사용자의 콕 상품 주문 내역 현황 알림 조회 (최적화: Raw SQL 사용)
    
    Args:
        db: 데이터베이스 세션
        user_id: 사용자 ID
        limit: 조회할 알림 개수 (기본값: 20)
        offset: 건너뛸 알림 개수 (기본값: 0)
    
    Returns:
        tuple: (알림 목록, 전체 개수)
        
    Note:
        - Raw SQL을 사용하여 성능 최적화
        - 주문완료, 배송출발, 배송완료 알림만 조회
        - 주문상태, 상품이름, 알림 메시지, 알림 날짜 포함
        - created_at 기준으로 내림차순 정렬
        - 페이지네이션 지원 (limit, offset)
    """    
    from sqlalchemy import text
    
    # 주문 현황 관련 상태 코드들
    order_status_codes = ["PAYMENT_COMPLETED", "SHIPPING", "DELIVERED"]
    
    # 최적화된 쿼리: Raw SQL 사용
    sql_query = """
    SELECT 
        kn.notification_id,
        kn.user_id,
        kn.kok_order_id,
        kn.status_id,
        kn.title,
        kn.message,
        kn.created_at,
        sm.status_code,
        sm.status_name,
        kpi.kok_product_name
    FROM KOK_NOTIFICATION kn
    INNER JOIN STATUS_MASTER sm ON kn.status_id = sm.status_id
    INNER JOIN KOK_ORDERS ko ON kn.kok_order_id = ko.kok_order_id
    INNER JOIN FCT_KOK_PRODUCT_INFO kpi ON ko.kok_product_id = kpi.kok_product_id
    WHERE kn.user_id = :user_id
    AND sm.status_code IN :order_status_codes
    ORDER BY kn.created_at DESC
    LIMIT :limit OFFSET :offset
    """
    
    # 전체 개수 조회
    count_sql = """
    SELECT COUNT(*)
    FROM KOK_NOTIFICATION kn
    INNER JOIN STATUS_MASTER sm ON kn.status_id = sm.status_id
    WHERE kn.user_id = :user_id
    AND sm.status_code IN :order_status_codes
    """
    
    try:
        # 전체 개수 조회
        count_result = await db.execute(text(count_sql), {
            "user_id": user_id,
            "order_status_codes": tuple(order_status_codes)
        })
        total_count = count_result.scalar()
        
        # 알림 목록 조회
        result = await db.execute(text(sql_query), {
            "user_id": user_id,
            "order_status_codes": tuple(order_status_codes),
            "limit": limit,
            "offset": offset
        })
        notifications_data = result.fetchall()
    except Exception as e:
        logger.error(f"콕 알림 조회 SQL 실행 실패: user_id={user_id}, limit={limit}, offset={offset}, error={str(e)}")
        return [], 0
    
    # 결과를 딕셔너리로 변환
    notifications = []
    for row in notifications_data:
        notification_dict = {
            "notification_id": row.notification_id,
            "user_id": row.user_id,
            "kok_order_id": row.kok_order_id,
            "status_id": row.status_id,
            "title": row.title,
            "message": row.message,
            "created_at": row.created_at,
            "order_status": row.status_code,
            "order_status_name": row.status_name,
            "product_name": row.kok_product_name
        }
        notifications.append(notification_dict)
    
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

async def debug_cart_status(db: AsyncSession, user_id: int, kok_cart_ids: List[int]) -> dict:
    """
    장바구니 상태를 디버깅하기 위한 함수
    
    Args:
        db: 데이터베이스 세션
        user_id: 사용자 ID
        kok_cart_ids: 확인할 장바구니 ID 목록
    
    Returns:
        dict: 디버깅 정보
    """
    debug_info = {
        "user_id": user_id,
        "requested_cart_ids": kok_cart_ids,
        "cart_status": {},
        "database_tables": {}
    }
    
    # 1. 장바구니 테이블 상태 확인
    for kok_cart_id in kok_cart_ids:
        try:
            cart_stmt = select(KokCart).where(KokCart.kok_cart_id == kok_cart_id)
            cart_result = await db.execute(cart_stmt)
            cart = cart_result.scalars().first()
        except Exception as e:
            logger.warning(f"장바구니 조회 실패: kok_cart_id={kok_cart_id}, error={str(e)}")
            cart = None
        
        if cart:
            debug_info["cart_status"][kok_cart_id] = {
                "exists": True,
                "kok_product_id": cart.kok_product_id,
                "recipe_id": cart.recipe_id,
                "user_id": cart.user_id
            }
            
            # 상품 정보 확인
            if cart.kok_product_id:
                try:
                    product_stmt = select(KokProductInfo).where(KokProductInfo.kok_product_id == cart.kok_product_id)
                    product_result = await db.execute(product_stmt)
                    product = product_result.scalars().first()
                except Exception as e:
                    logger.warning(f"상품 정보 조회 실패: kok_product_id={cart.kok_product_id}, error={str(e)}")
                    product = None
                
                if product:
                    debug_info["cart_status"][kok_cart_id]["product"] = {
                        "exists": True,
                        "name": product.kok_product_name,
                        "description": product.kok_product_description
                    }
                else:
                    debug_info["cart_status"][kok_cart_id]["product"] = {"exists": False}
                
                # 가격 정보 확인
                try:
                    price_stmt = select(KokPriceInfo).where(KokPriceInfo.kok_product_id == cart.kok_product_id)
                    price_result = await db.execute(price_stmt)
                    price = price_result.scalars().all()
                except Exception as e:
                    logger.warning(f"가격 정보 조회 실패: kok_product_id={cart.kok_product_id}, error={str(e)}")
                    price = []
                
                if price:
                    debug_info["cart_status"][kok_cart_id]["price"] = {
                        "exists": True,
                        "count": len(price),
                        "price_ids": [p.kok_price_id for p in price]
                    }
                else:
                    debug_info["cart_status"][kok_cart_id]["price"] = {"exists": False}
        else:
            debug_info["cart_status"][kok_cart_id] = {"exists": False}
    
    # 2. 사용자의 전체 장바구니 항목 확인
    try:
        all_carts_stmt = select(KokCart).where(KokCart.user_id == user_id)
        all_carts_result = await db.execute(all_carts_stmt)
        all_user_carts = all_carts_result.scalars().all()
    except Exception as e:
        logger.warning(f"사용자 전체 장바구니 조회 실패: user_id={user_id}, error={str(e)}")
        all_user_carts = []
    
    debug_info["database_tables"]["user_carts"] = {
        "total_count": len(all_user_carts),
        "cart_ids": [c.kok_cart_id for c in all_user_carts],
        "product_ids": [c.kok_product_id for c in all_user_carts]
    }
    
    # 3. 전체 상품 정보 개수 확인
    try:
        product_count_stmt = select(func.count(KokProductInfo.kok_product_id))
        product_count_result = await db.execute(product_count_stmt)
        total_products = product_count_result.scalar()
    except Exception as e:
        logger.warning(f"전체 상품 개수 조회 실패: error={str(e)}")
        total_products = 0
    
    # 4. 전체 가격 정보 개수 확인
    try:
        price_count_stmt = select(func.count(KokPriceInfo.kok_price_id))
        price_count_result = await db.execute(price_count_stmt)
        total_prices = price_count_result.scalar()
    except Exception as e:
        logger.warning(f"전체 가격 정보 개수 조회 실패: error={str(e)}")
        total_prices = 0
    
    debug_info["database_tables"]["summary"] = {
        "total_products": total_products,
        "total_prices": total_prices
    }
    
    return debug_info
