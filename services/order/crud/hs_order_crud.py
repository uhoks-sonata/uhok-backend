"""
홈쇼핑 주문 관련 CRUD 함수들
"""

import asyncio
from datetime import datetime, timedelta
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from services.order.models.order_model import (
    Order, HomeShoppingOrder, HomeShoppingOrderStatusHistory, StatusMaster
)
from services.homeshopping.models.homeshopping_model import (
    HomeshoppingList, HomeshoppingProductInfo, HomeshoppingNotification
)   

from services.order.crud.order_crud import (
    validate_user_exists, get_status_by_code,
    NOTIFICATION_TITLES, NOTIFICATION_MESSAGES
)

from common.logger import get_logger

logger = get_logger(__name__)


async def get_hs_current_status(db: AsyncSession, homeshopping_order_id: int) -> HomeShoppingOrderStatusHistory:
    """
    홈쇼핑 주문의 현재 상태(가장 최근 상태 이력) 조회
    """
    result = await db.execute(
        select(HomeShoppingOrderStatusHistory)
        .where(HomeShoppingOrderStatusHistory.homeshopping_order_id == homeshopping_order_id)
        .order_by(desc(HomeShoppingOrderStatusHistory.changed_at))
        .limit(1)
    )
    status_history = result.scalars().first()
    
    # 상태 이력이 없는 경우 기본 상태 반환
    if not status_history:
        # 기본 상태 조회 (ORDER_RECEIVED)
        default_status_result = await db.execute(
            select(StatusMaster).where(StatusMaster.status_code == "ORDER_RECEIVED")
        )
        default_status = default_status_result.scalars().first()
        
        if default_status:
            # 기본 상태로 상태 이력 생성
            from datetime import datetime
            status_history = HomeShoppingOrderStatusHistory(
                homeshopping_order_id=homeshopping_order_id,
                status_id=default_status.status_id,
                changed_at=datetime.now(),
                changed_by=None
            )
            
            # 기본 상태 정보를 status 관계에 설정
            status_history.status = default_status
    else:
        # 기존 상태 이력이 있는 경우, status 관계를 명시적으로 로드
        status_result = await db.execute(
            select(StatusMaster).where(StatusMaster.status_id == status_history.status_id)
        )
        status_history.status = status_result.scalars().first()
    
    return status_history


async def create_hs_notification_for_status_change(
    db: AsyncSession, 
    homeshopping_order_id: int, 
    status_id: int, 
    user_id: int
):
    """
    홈쇼핑 주문 상태 변경 시 알림 생성
    """
    # 상태 정보 조회
    status_result = await db.execute(
        select(StatusMaster).where(StatusMaster.status_id == status_id)
    )
    status = status_result.scalars().first()
    
    if not status:
        logger.warning(f"상태 정보를 찾을 수 없음: status_id={status_id}")
        return
    
    # 알림 제목과 메시지 생성
    title = NOTIFICATION_TITLES.get(status.status_code, "주문 상태 변경")
    message = NOTIFICATION_MESSAGES.get(status.status_code, f"주문 상태가 '{status.status_name}'로 변경되었습니다.")
    
    # 알림 생성
    notification = HomeshoppingNotification(
        user_id=user_id,
        homeshopping_order_id=homeshopping_order_id,
        status_id=status_id,
        title=title,
        message=message
    )
    
    db.add(notification)
    await db.commit()


async def update_hs_order_status(
        db: AsyncSession,
        homeshopping_order_id: int,
        new_status_code: str,
        changed_by: int = None
) -> HomeShoppingOrder:
    """
    홈쇼핑 주문 상태 업데이트 (INSERT만 사용) + 알림 생성
    """
    # 1. 새로운 상태 조회
    new_status = await get_status_by_code(db, new_status_code)
    if not new_status:
        raise ValueError(f"상태 코드 '{new_status_code}'를 찾을 수 없습니다")

    # 2. 주문 조회
    result = await db.execute(
        select(HomeShoppingOrder).where(HomeShoppingOrder.homeshopping_order_id == homeshopping_order_id)
    )
    hs_order = result.scalars().first()
    if not hs_order:
        raise Exception("해당 주문을 찾을 수 없습니다")

    # 3. 주문자 ID 조회
    order_result = await db.execute(
        select(Order).where(Order.order_id == hs_order.order_id)
    )
    order = order_result.scalars().first()
    if not order:
        raise Exception("주문 정보를 찾을 수 없습니다")

    # 4. 상태 변경 이력 생성 (UPDATE 없이 INSERT만)
    status_history = HomeShoppingOrderStatusHistory(
        homeshopping_order_id=homeshopping_order_id,
        status_id=new_status.status_id,
        changed_at=datetime.now(),
        changed_by=changed_by or order.user_id
    )
    
    db.add(status_history)
    
    # 5. 알림 생성
    await create_hs_notification_for_status_change(
        db=db,
        homeshopping_order_id=homeshopping_order_id,
        status_id=new_status.status_id,
        user_id=order.user_id
    )
    
    await db.commit()
    logger.info(f"홈쇼핑 주문 상태 변경 완료: homeshopping_order_id={homeshopping_order_id}, status={new_status_code}")
    
    return hs_order


async def get_hs_order_status_history(
    db: AsyncSession,
    homeshopping_order_id: int
) -> list[HomeShoppingOrderStatusHistory]:
    """
    홈쇼핑 주문의 상태 변경 이력 조회
    """
    result = await db.execute(
        select(HomeShoppingOrderStatusHistory)
        .where(HomeShoppingOrderStatusHistory.homeshopping_order_id == homeshopping_order_id)
        .order_by(desc(HomeShoppingOrderStatusHistory.changed_at))
    )
    
    status_histories = result.scalars().all()
    
    # 각 상태 이력에 대해 status 관계를 명시적으로 로드
    for history in status_histories:
        if not history.status:
            status_result = await db.execute(
                select(StatusMaster).where(StatusMaster.status_id == history.status_id)
            )
            history.status = status_result.scalars().first()
    
    # changed_at 기준으로 다시 정렬 (Python 레벨에서)
    status_histories.sort(key=lambda x: x.changed_at, reverse=True)
    
    return status_histories


async def get_hs_order_with_status(
    db: AsyncSession,
    homeshopping_order_id: int
) -> dict:
    """
    홈쇼핑 주문과 현재 상태를 함께 조회
    """
    # 주문 상세 정보 조회
    hs_order_result = await db.execute(
        select(HomeShoppingOrder, Order, HomeshoppingList, HomeshoppingProductInfo)
        .join(Order, HomeShoppingOrder.order_id == Order.order_id)
        .join(HomeshoppingList, HomeShoppingOrder.product_id == HomeshoppingList.product_id)
        .join(HomeshoppingProductInfo, HomeShoppingOrder.product_id == HomeshoppingProductInfo.product_id)
        .where(HomeShoppingOrder.homeshopping_order_id == homeshopping_order_id)
    )
    
    order_data = hs_order_result.first()
    if not order_data:
        return None
    
    hs_order, order, live, product = order_data
    
    # 상태 이력 조회 (가장 최근 상태를 현재 상태로 사용)
    status_history = await get_hs_order_status_history(db, homeshopping_order_id)
    
    # 디버깅을 위한 로그 추가
    logger.info(f"상태 이력 조회 결과: homeshopping_order_id={homeshopping_order_id}, count={len(status_history) if status_history else 0}")
    if status_history:
        for i, history in enumerate(status_history):
            logger.info(f"상태 이력 {i}: history_id={history.history_id}, changed_at={history.changed_at}, status_id={history.status_id}")
            if history.status:
                logger.info(f"  - status: {history.status.status_code} ({history.status.status_name})")
    
    # 가장 최근 상태를 현재 상태로 사용
    if status_history and len(status_history) > 0:
        # 가장 최근 상태 이력 (changed_at 기준 내림차순으로 정렬되어 있음)
        latest_status_history = status_history[0]
        
        if latest_status_history.status:
            current_status_data = {
                "status_id": latest_status_history.status.status_id,
                "status_code": latest_status_history.status.status_code,
                "status_name": latest_status_history.status.status_name
            }
            logger.info(f"최근 상태 이력에서 현재 상태 사용: {current_status_data}")
        else:
            # status 관계가 로드되지 않은 경우 기본 상태 사용
            default_status_result = await db.execute(
                select(StatusMaster).where(StatusMaster.status_code == "ORDER_RECEIVED")
            )
            default_status = default_status_result.scalar_one_or_none()
            
            current_status_data = {
                "status_id": default_status.status_id if default_status else 0,
                "status_code": default_status.status_code if default_status else "ORDER_RECEIVED",
                "status_name": default_status.status_name if default_status else "주문 접수"
            }
            logger.info(f"기본 상태 사용: {current_status_data}")
    else:
        # 상태 이력이 없는 경우 기본 상태 사용
        default_status_result = await db.execute(
            select(StatusMaster).where(StatusMaster.status_code == "ORDER_RECEIVED")
        )
        default_status = default_status_result.scalar_one_or_none()
        
        current_status_data = {
            "status_id": default_status.status_id if default_status else 0,
            "status_code": default_status.status_code if default_status else "ORDER_RECEIVED",
            "status_name": default_status.status_name if default_status else "주문 접수"
        }
        logger.info(f"상태 이력 없음, 기본 상태 사용: {current_status_data}")
    
    # 상태 이력은 이미 위에서 조회했으므로 재사용
    
    # 상태 이력을 API 응답 형식에 맞게 변환
    status_history_data = []
    for history in status_history:
        if history.status:  # status 관계가 로드된 경우
            status_history_data.append({
                "history_id": history.history_id,
                "homeshopping_order_id": history.homeshopping_order_id,
                "status": {
                    "status_id": history.status.status_id,
                    "status_code": history.status.status_code,
                    "status_name": history.status.status_name
                },
                "created_at": history.changed_at.isoformat() if history.changed_at else None
            })
    
    return {
        "order_id": order.order_id,
        "homeshopping_order_id": hs_order.homeshopping_order_id,
        "product_id": hs_order.product_id,
        "product_name": live.product_name if live else f"상품_{hs_order.product_id}",
        "quantity": hs_order.quantity,
        "dc_price": hs_order.dc_price,
        "order_price": hs_order.order_price,
        "order_time": order.order_time.isoformat() if order.order_time else None,
        "current_status": current_status_data,
        "status_history": status_history_data
    }


async def confirm_hs_payment(
    db: AsyncSession,
    homeshopping_order_id: int,
    user_id: int
) -> dict:
    """
    홈쇼핑 주문 결제 확인 (PAYMENT_REQUESTED → PAYMENT_COMPLETED)
    """
    # 1. 주문 조회 및 권한 확인
    hs_order_result = await db.execute(
        select(HomeShoppingOrder, Order)
        .join(Order, HomeShoppingOrder.order_id == Order.order_id)
        .where(HomeShoppingOrder.homeshopping_order_id == homeshopping_order_id)
    )
    
    order_data = hs_order_result.first()
    if not order_data:
        raise ValueError("해당 주문을 찾을 수 없습니다")
    
    hs_order, order = order_data
    
    # 주문자 본인 확인
    if order.user_id != user_id:
        raise ValueError("주문자 본인만 결제 확인할 수 있습니다")
    
    # 2. 현재 상태 확인
    current_status = await get_hs_current_status(db, homeshopping_order_id)
    if not current_status:
        raise ValueError("주문 상태 정보를 찾을 수 없습니다")
    
    if not current_status.status:
        raise ValueError("주문 상태 정보가 올바르지 않습니다")
    
    if current_status.status.status_code != "PAYMENT_REQUESTED":
        raise ValueError("현재 상태가 PAYMENT_REQUESTED가 아닙니다")
    
    # 3. 상태를 PAYMENT_COMPLETED로 변경
    new_status = await get_status_by_code(db, "PAYMENT_COMPLETED")
    if not new_status:
        raise ValueError("PAYMENT_COMPLETED 상태를 찾을 수 없습니다")
    
    # 4. 새로운 상태 이력 생성
    new_status_history = HomeShoppingOrderStatusHistory(
        homeshopping_order_id=homeshopping_order_id,
        status_id=new_status.status_id,
        changed_at=datetime.now(),
        changed_by=user_id
    )
    
    db.add(new_status_history)
    
    # 5. 알림 생성
    await create_hs_notification_for_status_change(
        db, homeshopping_order_id, new_status.status_id, user_id
    )
    
    await db.commit()
    
    return {
        "homeshopping_order_id": homeshopping_order_id,
        "previous_status": current_status.status.status_name,
        "current_status": new_status.status_name,
        "message": "결제가 확인되었습니다"
    }


async def start_hs_auto_update(
    db: AsyncSession,
    homeshopping_order_id: int,
    user_id: int
) -> dict:
    """
    홈쇼핑 주문 자동 상태 업데이트 시작 (테스트용)
    """
    # 1. 주문 조회 및 권한 확인
    hs_order_result = await db.execute(
        select(HomeShoppingOrder, Order)
        .join(Order, HomeShoppingOrder.order_id == Order.order_id)
        .where(HomeShoppingOrder.homeshopping_order_id == homeshopping_order_id)
    )
    
    order_data = hs_order_result.first()
    if not order_data:
        raise ValueError("해당 주문을 찾을 수 없습니다")
    
    hs_order, order = order_data
    
    # 주문자 본인 확인
    if order.user_id != user_id:
        raise ValueError("주문자 본인만 자동 업데이트를 시작할 수 있습니다")
    
    # 2. 현재 상태 확인
    current_status = await get_hs_current_status(db, homeshopping_order_id)
    if not current_status:
        raise ValueError("주문 상태 정보를 찾을 수 없습니다")
    
    if not current_status.status:
        raise ValueError("주문 상태 정보가 올바르지 않습니다")
    
    # 3. 자동 업데이트 로직 (테스트용)
    # 실제로는 백그라운드 태스크나 스케줄러를 사용해야 함
    logger.info(f"자동 상태 업데이트 시작: homeshopping_order_id={homeshopping_order_id}, current_status={current_status.status.status_code}")
    
    return {
        "homeshopping_order_id": homeshopping_order_id,
        "message": "자동 상태 업데이트가 시작되었습니다",
        "auto_update_started": True
    }


# -----------------------------
# 주문 관련 CRUD 함수 (기본 구조)
# -----------------------------

async def calculate_homeshopping_order_price(
    db: AsyncSession,
    product_id: int,
    quantity: int = 1
) -> dict:
    """
    홈쇼핑 주문 금액 계산
    """
    logger.info(f"홈쇼핑 주문 금액 계산 시작: product_id={product_id}, quantity={quantity}")
    
    try:
        # 1. 상품 정보 조회 (할인가 확인)
        product_stmt = select(HomeshoppingProductInfo).where(
            HomeshoppingProductInfo.product_id == product_id
        )
        product_result = await db.execute(product_stmt)
        product = product_result.scalar_one_or_none()
        
        if not product:
            logger.error(f"상품을 찾을 수 없음: product_id={product_id}")
            raise ValueError("상품을 찾을 수 없습니다.")
        
        # 2. 상품명 조회
        live_stmt = select(HomeshoppingList).where(
            HomeshoppingList.product_id == product_id
        )
        live_result = await db.execute(live_stmt)
        live = live_result.scalar_one_or_none()
        
        product_name = live.product_name if live else f"상품_{product_id}"
        
        # 3. 주문 금액 계산
        dc_price = product.dc_price \
            or (product.sale_price * (1 - product.dc_rate / 100)) \
                or 0
        order_price = dc_price * quantity
        
        logger.info(f"홈쇼핑 주문 금액 계산 완료: product_id={product_id}, dc_price={dc_price}, quantity={quantity}, order_price={order_price}")
        
        return {
            "product_id": product_id,
            "product_name": product_name,
            "dc_price": dc_price,
            "quantity": quantity,
            "order_price": order_price
        }
        
    except Exception as e:
        logger.error(f"홈쇼핑 주문 금액 계산 실패: product_id={product_id}, error={str(e)}")
        raise


async def create_homeshopping_order(
    db: AsyncSession,
    user_id: int,
    product_id: int,
    quantity: int = 1  # 기본값을 1로 설정
) -> dict:
    """
    홈쇼핑 주문 생성 (단건 주문)
    """
    logger.info(f"홈쇼핑 주문 생성 시작: user_id={user_id}, product_id={product_id}, quantity={quantity}")
    
    try:
        # 1. 주문 금액 계산 (별도 함수 사용)
        price_info = await calculate_homeshopping_order_price(db, product_id, quantity)
        dc_price = price_info["dc_price"]
        order_price = price_info["order_price"]
        product_name = price_info["product_name"]
        
        # 2. 주문 생성 (ORDERS 테이블)
        order_time = datetime.now()
        new_order = Order(
            user_id=user_id,
            order_time=order_time
        )
        
        db.add(new_order)
        await db.flush()  # order_id 생성
        
        # 3. 홈쇼핑 주문 상세 생성 (HOMESHOPPING_ORDERS 테이블)
        new_homeshopping_order = HomeShoppingOrder(
            order_id=new_order.order_id,
            product_id=product_id,
            dc_price=dc_price,
            quantity=quantity,
            order_price=order_price
        )
        
        db.add(new_homeshopping_order)
        await db.flush()  # homeshopping_order_id 생성
        
        # 4. 주문 상태 이력 생성 (초기 상태: 주문접수)
        # STATUS_MASTER에서 'ORDER_RECEIVED' 상태 ID 조회
        status_stmt = select(StatusMaster).where(
            StatusMaster.status_code == "ORDER_RECEIVED"
        )
        status_result = await db.execute(status_stmt)
        status = status_result.scalar_one_or_none()
        
        if status:
            new_status_history = HomeShoppingOrderStatusHistory(
                homeshopping_order_id=new_homeshopping_order.homeshopping_order_id,
                status_id=status.status_id,
                changed_at=order_time,
                changed_by=user_id
            )
            db.add(new_status_history)
        
        # 5. 홈쇼핑 알림 생성
        new_notification = HomeshoppingNotification(
            user_id=user_id,
            homeshopping_order_id=new_homeshopping_order.homeshopping_order_id,
            status_id=status.status_id if status else 1,  # 기본값
            title="주문 생성",
            message="주문이 성공적으로 접수되었습니다."
        )
        
        db.add(new_notification)
        
        # 6. 모든 변경사항 커밋
        await db.commit()
        
        # 9. 즉시 PAYMENT_REQUESTED 상태로 변경 (백그라운드 작업 제거)
        try:
            logger.info(f"즉시 상태 변경 시작: homeshopping_order_id={new_homeshopping_order.homeshopping_order_id}")
            
            # PAYMENT_REQUESTED 상태 조회
            payment_status_stmt = select(StatusMaster).where(
                StatusMaster.status_code == "PAYMENT_REQUESTED"
            )
            payment_status_result = await db.execute(payment_status_stmt)
            payment_status = payment_status_result.scalar_one_or_none()
            
            if payment_status:
                # 새로운 상태 이력 생성 (1초 후 시간으로 설정하여 순서 보장)
                payment_time = order_time + timedelta(seconds=1)
                payment_status_history = HomeShoppingOrderStatusHistory(
                    homeshopping_order_id=new_homeshopping_order.homeshopping_order_id,
                    status_id=payment_status.status_id,
                    changed_at=payment_time,
                    changed_by=user_id
                )
                db.add(payment_status_history)
                
                # 알림 생성
                payment_notification = HomeshoppingNotification(
                    user_id=user_id,
                    homeshopping_order_id=new_homeshopping_order.homeshopping_order_id,
                    status_id=payment_status.status_id,
                    title="결제 요청",
                    message="결제가 요청되었습니다."
                )
                db.add(payment_notification)
                
                # 상태 변경 커밋
                await db.commit()
                logger.info(f"즉시 상태 변경 완료: homeshopping_order_id={new_homeshopping_order.homeshopping_order_id}, status=PAYMENT_REQUESTED")
            else:
                logger.error("PAYMENT_REQUESTED 상태를 찾을 수 없습니다")
                
        except Exception as e:
            logger.error(f"즉시 상태 변경 실패: homeshopping_order_id={new_homeshopping_order.homeshopping_order_id}, error={str(e)}")
            # 상태 변경 실패해도 주문 생성은 성공으로 처리
        
        logger.info(f"홈쇼핑 주문 생성 완료: user_id={user_id}, order_id={new_order.order_id}, homeshopping_order_id={new_homeshopping_order.homeshopping_order_id}")
        
        return {
            "order_id": new_order.order_id,
            "homeshopping_order_id": new_homeshopping_order.homeshopping_order_id,
            "product_id": product_id,
            "product_name": product_name,
            "quantity": quantity,
            "dc_price": dc_price,
            "order_price": order_price,
            "order_time": order_time,
            "message": "주문이 성공적으로 생성되었습니다."
        }
        
    except Exception as e:
        await db.rollback()
        logger.error(f"홈쇼핑 주문 생성 실패: user_id={user_id}, product_id={product_id}, error={str(e)}")
        raise
