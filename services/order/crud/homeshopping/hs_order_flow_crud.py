"""HomeShopping order creation/payment flow CRUD functions."""

import asyncio
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.logger import get_logger
from services.order.models.order_base_model import Order, StatusMaster
from services.order.models.homeshopping.hs_order_model import (
    HomeShoppingOrder,
    HomeShoppingOrderStatusHistory,
)
from services.homeshopping.models.interaction_model import HomeshoppingNotification
from services.order.crud.order_common import get_status_by_code
from services.order.crud.homeshopping.hs_order_pricing_crud import calculate_homeshopping_order_price
from services.order.crud.homeshopping.hs_order_status_crud import (
    get_hs_current_status,
    create_hs_notification_for_status_change,
    update_hs_order_status,
    auto_update_hs_order_status,
)

logger = get_logger("hs_order_crud")

async def create_homeshopping_order(
    db: AsyncSession,
    user_id: int,
    product_id: int,
    quantity: int = 1  # 기본값을 1로 설정
) -> dict:
    """
    홈쇼핑 주문 생성 (단건 주문)
    
    Args:
        db: 데이터베이스 세션
        user_id: 주문하는 사용자 ID
        product_id: 상품 ID
        quantity: 수량 (기본값: 1)
    
    Returns:
        dict: 주문 생성 결과 (order_id, homeshopping_order_id, product_id, product_name, quantity, dc_price, order_price, order_time, message)
        
    Note:
        - CRUD 계층: 트랜잭션 단위 책임
        - 주문 금액 자동 계산 (calculate_homeshopping_order_price 함수 사용)
        - 주문 접수 상태로 초기화
        - 주문 생성 알림 자동 생성
        - 트랜잭션으로 처리하여 일관성 보장
    """
    # logger.info(f"홈쇼핑 주문 생성 시작: user_id={user_id}, product_id={product_id}, quantity={quantity}")
    
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
        try:
            status_result = await db.execute(status_stmt)
            status = status_result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"주문 상태 조회 SQL 실행 실패: status_code=ORDER_RECEIVED, error={str(e)}")
            raise
        
        if status:
            new_status_history = HomeShoppingOrderStatusHistory(
                homeshopping_order_id=new_homeshopping_order.homeshopping_order_id,
                status_id=status.status_id,
                changed_at=order_time,
                changed_by=user_id
            )
            db.add(new_status_history)
        else:
            logger.warning(f"ORDER_RECEIVED 상태를 찾을 수 없음: user_id={user_id}, product_id={product_id}")
        
        # 5. 홈쇼핑 알림 생성
        new_notification = HomeshoppingNotification(
            user_id=user_id,
            homeshopping_order_id=new_homeshopping_order.homeshopping_order_id,
            status_id=status.status_id if status else 1,  # 기본값
            title="주문 생성",
            message="주문이 성공적으로 접수되었습니다."
        )
        
        db.add(new_notification)
        await db.commit()
        
    # logger.info(f"홈쇼핑 주문 생성 완료: user_id={user_id}, order_id={new_order.order_id}, homeshopping_order_id={new_homeshopping_order.homeshopping_order_id}")
        
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



async def confirm_hs_payment(
    db: AsyncSession,
    homeshopping_order_id: int,
    user_id: int
) -> dict:
    """
    홈쇼핑 주문 결제 확인 (PAYMENT_REQUESTED → PAYMENT_COMPLETED)
    
    Args:
        db: 데이터베이스 세션
        homeshopping_order_id: 홈쇼핑 주문 ID
        user_id: 결제 확인을 요청한 사용자 ID
    
    Returns:
        dict: 결제 확인 결과 (homeshopping_order_id, previous_status, current_status, message)
        
    Note:
        - CRUD 계층: 트랜잭션 단위 책임
        - 주문자 본인만 결제 확인 가능
        - 현재 상태가 PAYMENT_REQUESTED인지 확인
        - PAYMENT_COMPLETED 상태로 변경하고 알림 생성
        - 트랜잭션으로 처리하여 일관성 보장
    """
    # 1. 주문 조회 및 권한 확인
    try:
        hs_order_result = await db.execute(
            select(HomeShoppingOrder, Order)
            .join(Order, HomeShoppingOrder.order_id == Order.order_id)
            .where(HomeShoppingOrder.homeshopping_order_id == homeshopping_order_id)
        )
        
        order_data = hs_order_result.first()
    except Exception as e:
        logger.error(f"홈쇼핑 주문 결제 확인 조회 SQL 실행 실패: homeshopping_order_id={homeshopping_order_id}, error={str(e)}")
        raise
    
    if not order_data:
        logger.warning(f"홈쇼핑 주문을 찾을 수 없음: homeshopping_order_id={homeshopping_order_id}")
        raise ValueError("해당 주문을 찾을 수 없습니다")
    
    hs_order, order = order_data
    
    # 주문자 본인 확인
    if order.user_id != user_id:
        logger.warning(f"주문자 본인이 아님: order_user_id={order.user_id}, request_user_id={user_id}, homeshopping_order_id={homeshopping_order_id}")
        raise ValueError("주문자 본인만 결제 확인할 수 있습니다")
    
    # 2. 현재 상태 확인
    current_status = await get_hs_current_status(db, homeshopping_order_id)
    if not current_status:
        logger.warning(f"주문 상태 정보를 찾을 수 없음: homeshopping_order_id={homeshopping_order_id}")
        raise ValueError("주문 상태 정보를 찾을 수 없습니다")
    
    if not current_status.status:
        logger.warning(f"주문 상태 정보가 올바르지 않음: homeshopping_order_id={homeshopping_order_id}, status_id={current_status.status_id}")
        raise ValueError("주문 상태 정보가 올바르지 않습니다")
    
    if current_status.status.status_code != "PAYMENT_REQUESTED":
        logger.warning(f"현재 상태가 PAYMENT_REQUESTED가 아님: homeshopping_order_id={homeshopping_order_id}, current_status={current_status.status.status_code}")
        raise ValueError("현재 상태가 PAYMENT_REQUESTED가 아닙니다")
    
    # 3. 상태를 PAYMENT_COMPLETED로 변경
    new_status = await get_status_by_code(db, "PAYMENT_COMPLETED")
    if not new_status:
        logger.warning(f"PAYMENT_COMPLETED 상태를 찾을 수 없음: homeshopping_order_id={homeshopping_order_id}")
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
    
    Args:
        db: 데이터베이스 세션
        homeshopping_order_id: 홈쇼핑 주문 ID
        user_id: 자동 업데이트를 요청한 사용자 ID
    
    Returns:
        dict: 자동 업데이트 시작 결과 (homeshopping_order_id, message, auto_update_started, current_status, next_status)
        
    Note:
        - CRUD 계층: 트랜잭션 단위 책임
        - 주문자 본인만 자동 업데이트 시작 가능
        - 현재 상태에 따른 다음 상태 결정 및 업데이트
        - 백그라운드에서 나머지 상태 업데이트 시작
        - 상태 전환 로직: PAYMENT_COMPLETED → PREPARING → SHIPPING → DELIVERED
    """
    try:
        # 1. 주문 조회 및 권한 확인
        try:
            hs_order_result = await db.execute(
                select(HomeShoppingOrder, Order)
                .join(Order, HomeShoppingOrder.order_id == Order.order_id)
                .where(HomeShoppingOrder.homeshopping_order_id == homeshopping_order_id)
            )
            
            order_data = hs_order_result.first()
        except Exception as e:
            logger.error(f"홈쇼핑 주문 자동 업데이트 조회 SQL 실행 실패: homeshopping_order_id={homeshopping_order_id}, error={str(e)}")
            raise
        
        if not order_data:
            logger.warning(f"홈쇼핑 주문을 찾을 수 없음: homeshopping_order_id={homeshopping_order_id}")
            raise ValueError("해당 주문을 찾을 수 없습니다")
        
        hs_order, order = order_data
        
        # 주문자 본인 확인
        if order.user_id != user_id:
            logger.warning(f"주문자 본인이 아님: order_user_id={order.user_id}, request_user_id={user_id}, homeshopping_order_id={homeshopping_order_id}")
            raise ValueError("주문자 본인만 자동 업데이트를 시작할 수 있습니다")
        
        # 2. 현재 상태 확인
        current_status = await get_hs_current_status(db, homeshopping_order_id)
        if not current_status:
            logger.warning(f"주문 상태 정보를 찾을 수 없음: homeshopping_order_id={homeshopping_order_id}")
            raise ValueError("주문 상태 정보를 찾을 수 없습니다")
        
        if not current_status.status:
            logger.warning(f"주문 상태 정보가 올바르지 않음: homeshopping_order_id={homeshopping_order_id}, status_id={current_status.status_id}")
            raise ValueError("주문 상태 정보가 올바르지 않습니다")
        
        # logger.info(f"자동 상태 업데이트 시작: homeshopping_order_id={homeshopping_order_id}, current_status={current_status.status.status_code}")
        
        # 3. 현재 상태에 따른 다음 상태 결정 및 업데이트
        current_status_code = current_status.status.status_code
        next_status_code = None
        
        # 상태 전환 로직
        if current_status_code == "PAYMENT_COMPLETED":
            next_status_code = "PREPARING"
        elif current_status_code == "PREPARING":
            next_status_code = "SHIPPING"
        elif current_status_code == "SHIPPING":
            next_status_code = "DELIVERED"
        elif current_status_code == "DELIVERED":
            # 이미 배송완료 상태이므로 더 이상 업데이트 불가
            return {
                "homeshopping_order_id": homeshopping_order_id,
                "message": "이미 배송완료 상태입니다",
                "auto_update_started": False,
                "current_status": current_status_code,
                "next_status": None
            }
        else:
            # 다른 상태들은 자동 업데이트 대상이 아님
            return {
                "homeshopping_order_id": homeshopping_order_id,
                "message": f"현재 상태({current_status_code})에서는 자동 업데이트를 할 수 없습니다",
                "auto_update_started": False,
                "current_status": current_status_code,
                "next_status": None
            }
        
        # 4. 상태 업데이트 실행
        if next_status_code:
            # logger.info(f"상태 업데이트 실행: {current_status_code} -> {next_status_code}")
            
            # 상태 업데이트 함수 호출
            updated_order = await update_hs_order_status(
                db=db,
                homeshopping_order_id=homeshopping_order_id,
                new_status_code=next_status_code,
                changed_by=user_id
            )
            
            # 상태 업데이트 후 commit하여 DB에 반영
            await db.commit()
            # logger.info(f"상태 업데이트 완료 및 DB 반영: homeshopping_order_id={homeshopping_order_id}, {current_status_code} -> {next_status_code}")
            
            # 5. 백그라운드에서 나머지 상태 업데이트 시작
            try:
                # 현재 세션을 사용하여 백그라운드에서 자동 업데이트 시작
                asyncio.create_task(auto_update_hs_order_status(homeshopping_order_id, db))
                logger.info(f"백그라운드 자동 상태 업데이트 시작: homeshopping_order_id={homeshopping_order_id}")
            except Exception as e:
                logger.warning(f"백그라운드 자동 상태 업데이트 시작 실패: homeshopping_order_id={homeshopping_order_id}, error={str(e)}")
            
            return {
                "homeshopping_order_id": homeshopping_order_id,
                "message": f"상태가 {current_status_code}에서 {next_status_code}로 업데이트되었습니다. 백그라운드에서 자동 업데이트가 시작됩니다.",
                "auto_update_started": True,
                "current_status": current_status_code,
                "next_status": next_status_code
            }
        
        return {
            "homeshopping_order_id": homeshopping_order_id,
            "message": "자동 상태 업데이트가 시작되었습니다",
            "auto_update_started": True,
            "current_status": current_status_code,
            "next_status": next_status_code
        }
        
    except Exception as e:
        logger.error(f"자동 상태 업데이트 실패: homeshopping_order_id={homeshopping_order_id}, error={str(e)}")
        # 트랜잭션 롤백을 위해 예외를 다시 발생시킴
        raise


