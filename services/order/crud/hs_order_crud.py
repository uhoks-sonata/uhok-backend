"""
홈쇼핑 주문 관련 CRUD 함수들
CRUD 계층: 모든 DB 트랜잭션 처리 담당
"""
import asyncio
from datetime import datetime
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from common.database.mariadb_service import get_maria_service_db
from common.logger import get_logger

from services.order.models.order_model import (
    Order, 
    HomeShoppingOrder, 
    HomeShoppingOrderStatusHistory, 
    StatusMaster
)
from services.homeshopping.models.homeshopping_model import (
    HomeshoppingList, 
    HomeshoppingProductInfo, 
    HomeshoppingNotification
)   
from services.order.crud.order_common import (
    get_status_by_code,
    NOTIFICATION_TITLES, NOTIFICATION_MESSAGES
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


async def get_hs_current_status(
    db: AsyncSession, 
    homeshopping_order_id: int
) -> HomeShoppingOrderStatusHistory:
    """
    홈쇼핑 주문의 현재 상태(가장 최근 상태 이력) 조회 (최적화: JOIN으로 N+1 문제 해결)
    
    Args:
        db: 데이터베이스 세션
        homeshopping_order_id: 홈쇼핑 주문 ID
    
    Returns:
        HomeShoppingOrderStatusHistory: 가장 최근 상태 이력 객체
        
    Note:
        - CRUD 계층: DB 조회만 담당, 트랜잭션 변경 없음
        - JOIN을 사용하여 상태 정보를 한 번에 조회하여 N+1 문제 해결
        - 상태 이력이 없는 경우 기본 상태(ORDER_RECEIVED)로 상태 이력 생성
    """
    from sqlalchemy import text
    
    # 최적화된 쿼리: JOIN을 사용하여 상태 정보를 한 번에 조회
    sql_query = """
    SELECT 
        hosh.history_id,
        hosh.homeshopping_order_id,
        hosh.status_id,
        hosh.changed_at,
        hosh.changed_by,
        sm.status_code,
        sm.status_name
    FROM HOMESHOPPING_ORDER_STATUS_HISTORY hosh
    INNER JOIN STATUS_MASTER sm ON hosh.status_id = sm.status_id
    WHERE hosh.homeshopping_order_id = :homeshopping_order_id
    ORDER BY hosh.changed_at DESC
    LIMIT 1
    """
    
    try:
        result = await db.execute(text(sql_query), {"homeshopping_order_id": homeshopping_order_id})
        status_data = result.fetchone()
    except Exception as e:
        logger.error(f"홈쇼핑 주문 현재 상태 조회 SQL 실행 실패: homeshopping_order_id={homeshopping_order_id}, error={str(e)}")
        raise
    
    # 상태 이력이 있는 경우
    if status_data:
        # HomeShoppingOrderStatusHistory 객체 생성
        status_history = HomeShoppingOrderStatusHistory()
        status_history.history_id = status_data.history_id
        status_history.homeshopping_order_id = status_data.homeshopping_order_id
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
    
    # 상태 이력이 없는 경우 기본 상태 반환
    try:
        default_status_result = await db.execute(
            select(StatusMaster).where(StatusMaster.status_code == "ORDER_RECEIVED")
        )
        default_status = default_status_result.scalars().first()
    except Exception as e:
        logger.error(f"기본 상태 조회 SQL 실행 실패: status_code=ORDER_RECEIVED, error={str(e)}")
        raise
    
    if default_status:
        # 기본 상태로 상태 이력 생성
        status_history = HomeShoppingOrderStatusHistory(
            homeshopping_order_id=homeshopping_order_id,
            status_id=default_status.status_id,
            changed_at=datetime.now(),
            changed_by=None
        )
        
        # 기본 상태 정보를 status 관계에 설정
        status_history.status = default_status
        return status_history
    else:
        logger.warning(f"기본 상태(ORDER_RECEIVED)를 찾을 수 없음: homeshopping_order_id={homeshopping_order_id}")
        # 빈 상태 이력 반환
        return HomeShoppingOrderStatusHistory(
            homeshopping_order_id=homeshopping_order_id,
            status_id=0,
            changed_at=datetime.now(),
            changed_by=None
        )


async def create_hs_notification_for_status_change(
    db: AsyncSession, 
    homeshopping_order_id: int, 
    status_id: int, 
    user_id: int
):
    """
    홈쇼핑 주문 상태 변경 시 알림 생성
    
    Args:
        db: 데이터베이스 세션
        homeshopping_order_id: 홈쇼핑 주문 ID
        status_id: 상태 ID
        user_id: 사용자 ID
    
    Returns:
        None
        
    Note:
        - CRUD 계층: DB 상태 변경 담당, 트랜잭션 단위 책임
        - 주문 상태 변경 시 자동으로 알림 생성
        - NOTIFICATION_TITLES와 NOTIFICATION_MESSAGES에서 상태별 메시지 조회
        - HomeshoppingNotification 테이블에 알림 정보 저장
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
    notification = HomeshoppingNotification(
        user_id=user_id,
        homeshopping_order_id=homeshopping_order_id,
        status_id=status_id,
        title=title,
        message=message
    )
    
    db.add(notification)
    await db.commit()
    # logger.info(f"홈쇼핑 주문 알림 생성 완료: homeshopping_order_id={homeshopping_order_id}, status_id={status_id}")


async def update_hs_order_status(
        db: AsyncSession,
        homeshopping_order_id: int,
        new_status_code: str,
        changed_by: int = None
) -> HomeShoppingOrder:
    """
    홈쇼핑 주문 상태 업데이트 (INSERT만 사용) + 알림 생성
    
    Args:
        db: 데이터베이스 세션
        homeshopping_order_id: 홈쇼핑 주문 ID
        new_status_code: 새로운 상태 코드
        changed_by: 상태 변경을 수행한 사용자 ID (기본값: None)
    
    Returns:
        HomeShoppingOrder: 업데이트된 홈쇼핑 주문 객체
        
    Note:
        - CRUD 계층: 트랜잭션 단위 책임
        - 기존 상태를 UPDATE하지 않고 새로운 상태 이력을 INSERT
        - 상태 변경 시 자동으로 알림 생성
        - 트랜잭션으로 처리하여 일관성 보장
    """
    # 1. 새로운 상태 조회
    new_status = await get_status_by_code(db, new_status_code)
    if not new_status:
        raise ValueError(f"상태 코드 '{new_status_code}'를 찾을 수 없습니다")

    # 2. 주문 조회
    try:
        result = await db.execute(
            select(HomeShoppingOrder).where(HomeShoppingOrder.homeshopping_order_id == homeshopping_order_id)
        )
        hs_order = result.scalars().first()
    except Exception as e:
        logger.error(f"홈쇼핑 주문 조회 SQL 실행 실패: homeshopping_order_id={homeshopping_order_id}, error={str(e)}")
        raise
    
    if not hs_order:
        logger.warning(f"홈쇼핑 주문을 찾을 수 없음: homeshopping_order_id={homeshopping_order_id}")
        raise Exception("해당 주문을 찾을 수 없습니다")

    # 3. 주문자 ID 조회
    try:
        order_result = await db.execute(
            select(Order).where(Order.order_id == hs_order.order_id)
        )
        order = order_result.scalars().first()
    except Exception as e:
        logger.error(f"주문 정보 조회 SQL 실행 실패: order_id={hs_order.order_id}, error={str(e)}")
        raise
    
    if not order:
        logger.warning(f"주문 정보를 찾을 수 없음: order_id={hs_order.order_id}")
        raise Exception("주문 정보를 찾을 수 없습니다")

    # 4. 상태 변경 이력 생성 (UPDATE 없이 INSERT만)
    status_history = HomeShoppingOrderStatusHistory(
        homeshopping_order_id=homeshopping_order_id,
        status_id=new_status.status_id,
        changed_at=datetime.now(),
        changed_by=changed_by or order.user_id
    )
    
    db.add(status_history)
    
    # 5. 알림 생성 (트랜잭션 내에서 처리)
    await create_hs_notification_for_status_change(
        db=db,
        homeshopping_order_id=homeshopping_order_id,
        status_id=new_status.status_id,
        user_id=order.user_id
    )
    
    await db.commit()
    # logger.info(f"홈쇼핑 주문 상태 변경 완료: homeshopping_order_id={homeshopping_order_id}, status={new_status_code}")
    
    return hs_order


async def get_hs_order_status_history(
    db: AsyncSession,
    homeshopping_order_id: int
) -> list[HomeShoppingOrderStatusHistory]:
    """
    홈쇼핑 주문의 상태 변경 이력 조회 (최적화: JOIN으로 N+1 문제 해결)
    
    Args:
        db: 데이터베이스 세션
        homeshopping_order_id: 홈쇼핑 주문 ID
    
    Returns:
        list[HomeShoppingOrderStatusHistory]: 상태 변경 이력 목록
        
    Note:
        - CRUD 계층: DB 조회만 담당, 트랜잭션 변경 없음
        - JOIN을 사용하여 상태 정보를 한 번에 조회하여 N+1 문제 해결
        - changed_at 기준으로 내림차순 정렬
    """
    from sqlalchemy import text
    
    # 최적화된 쿼리: JOIN을 사용하여 상태 정보를 한 번에 조회
    sql_query = """
    SELECT 
        hosh.history_id,
        hosh.homeshopping_order_id,
        hosh.status_id,
        hosh.changed_at,
        hosh.changed_by,
        sm.status_code,
        sm.status_name
    FROM HOMESHOPPING_ORDER_STATUS_HISTORY hosh
    INNER JOIN STATUS_MASTER sm ON hosh.status_id = sm.status_id
    WHERE hosh.homeshopping_order_id = :homeshopping_order_id
    ORDER BY hosh.changed_at DESC
    """
    
    try:
        result = await db.execute(text(sql_query), {"homeshopping_order_id": homeshopping_order_id})
        status_histories_data = result.fetchall()
    except Exception as e:
        logger.error(f"홈쇼핑 주문 상태 이력 조회 SQL 실행 실패: homeshopping_order_id={homeshopping_order_id}, error={str(e)}")
        raise
    
    # 결과를 HomeShoppingOrderStatusHistory 객체로 변환
    status_histories = []
    for row in status_histories_data:
        # HomeShoppingOrderStatusHistory 객체 생성
        history = HomeShoppingOrderStatusHistory()
        history.history_id = row.history_id
        history.homeshopping_order_id = row.homeshopping_order_id
        history.status_id = row.status_id
        history.changed_at = row.changed_at
        history.changed_by = row.changed_by
        
        # StatusMaster 객체 생성 및 설정
        status = StatusMaster()
        status.status_id = row.status_id
        status.status_code = row.status_code
        status.status_name = row.status_name
        history.status = status
        
        status_histories.append(history)
    
    return status_histories


async def get_hs_order_with_status(
    db: AsyncSession,
    homeshopping_order_id: int
) -> dict:
    """
    홈쇼핑 주문과 현재 상태를 함께 조회 (최적화: 윈도우 함수 사용)
    
    Args:
        db: 데이터베이스 세션
        homeshopping_order_id: 홈쇼핑 주문 ID
    
    Returns:
        dict: 주문 정보와 현재 상태 정보
        
    Note:
        - CRUD 계층: DB 조회만 담당, 트랜잭션 변경 없음
        - 윈도우 함수를 사용하여 최신 상품 정보와 상태 정보를 한 번에 조회
        - N+1 문제 해결 및 쿼리 성능 최적화
    """
    from sqlalchemy import text
    
    # 최적화된 쿼리: 윈도우 함수를 사용하여 모든 정보를 한 번에 조회
    sql_query = """
    WITH latest_product_info AS (
        SELECT 
            hl.product_id,
            hl.product_name,
            ROW_NUMBER() OVER (
                PARTITION BY hl.product_id 
                ORDER BY hl.live_date DESC, hl.live_start_time DESC
            ) as rn
        FROM FCT_HOMESHOPPING_LIST hl
    ),
    latest_status_info AS (
        SELECT 
            hosh.homeshopping_order_id,
            hosh.status_id,
            hosh.changed_at,
            hosh.changed_by,
            sm.status_code,
            sm.status_name,
            ROW_NUMBER() OVER (
                PARTITION BY hosh.homeshopping_order_id 
                ORDER BY hosh.changed_at DESC
            ) as rn
        FROM HOMESHOPPING_ORDER_STATUS_HISTORY hosh
        INNER JOIN STATUS_MASTER sm ON hosh.status_id = sm.status_id
    )
    SELECT 
        ho.homeshopping_order_id,
        ho.order_id,
        ho.product_id,
        ho.quantity,
        ho.dc_price,
        ho.order_price,
        o.user_id,
        o.order_time,
        COALESCE(lpi.product_name, CONCAT('상품_', ho.product_id)) as product_name,
        COALESCE(ls.status_id, 1) as current_status_id,
        COALESCE(ls.status_code, 'ORDER_RECEIVED') as current_status_code,
        COALESCE(ls.status_name, '주문 접수') as current_status_name
    FROM HOMESHOPPING_ORDERS ho
    INNER JOIN ORDERS o ON ho.order_id = o.order_id
    LEFT JOIN latest_product_info lpi ON ho.product_id = lpi.product_id AND lpi.rn = 1
    LEFT JOIN latest_status_info ls ON ho.homeshopping_order_id = ls.homeshopping_order_id AND ls.rn = 1
    WHERE ho.homeshopping_order_id = :homeshopping_order_id
    """
    
    try:
        result = await db.execute(text(sql_query), {"homeshopping_order_id": homeshopping_order_id})
        order_data = result.fetchone()
    except Exception as e:
        logger.error(f"홈쇼핑 주문 상세 조회 SQL 실행 실패: homeshopping_order_id={homeshopping_order_id}, error={str(e)}")
        return None
    
    if not order_data:
        logger.warning(f"홈쇼핑 주문 상세 정보를 찾을 수 없음: homeshopping_order_id={homeshopping_order_id}")
        return None
    
    # 상태 이력 조회 (최적화된 쿼리)
    status_history_sql = """
    SELECT 
        hosh.history_id,
        hosh.homeshopping_order_id,
        hosh.status_id,
        hosh.changed_at,
        hosh.changed_by,
        sm.status_code,
        sm.status_name
    FROM HOMESHOPPING_ORDER_STATUS_HISTORY hosh
    INNER JOIN STATUS_MASTER sm ON hosh.status_id = sm.status_id
    WHERE hosh.homeshopping_order_id = :homeshopping_order_id
    ORDER BY hosh.changed_at DESC
    """
    
    try:
        status_result = await db.execute(text(status_history_sql), {"homeshopping_order_id": homeshopping_order_id})
        status_histories = status_result.fetchall()
    except Exception as e:
        logger.warning(f"상태 이력 조회 실패: homeshopping_order_id={homeshopping_order_id}, error={str(e)}")
        status_histories = []
    
    # 현재 상태 정보 구성
    current_status_data = {
        "status_id": order_data.current_status_id,
        "status_code": order_data.current_status_code,
        "status_name": order_data.current_status_name
    }
    
    # 상태 이력을 API 응답 형식에 맞게 변환
    status_history_data = []
    for history in status_histories:
        status_history_data.append({
            "history_id": history.history_id,
            "homeshopping_order_id": history.homeshopping_order_id,
            "status": {
                "status_id": history.status_id,
                "status_code": history.status_code,
                "status_name": history.status_name
            },
            "created_at": history.changed_at.isoformat() if history.changed_at else None
        })
    
    return {
        "order_id": order_data.order_id,
        "homeshopping_order_id": order_data.homeshopping_order_id,
        "product_id": order_data.product_id,
        "product_name": order_data.product_name,
        "quantity": order_data.quantity,
        "dc_price": order_data.dc_price,
        "order_price": order_data.order_price,
        "order_time": order_data.order_time.isoformat() if order_data.order_time else None,
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


async def auto_update_hs_order_status(homeshopping_order_id: int, db: AsyncSession):
    """
    홈쇼핑 주문 후 자동으로 상태를 업데이트하는 함수
    
    Args:
        homeshopping_order_id: 홈쇼핑 주문 ID
        db: 데이터베이스 세션
    
    Returns:
        None
        
    Note:
        - PAYMENT_COMPLETED -> PREPARING -> SHIPPING -> DELIVERED 순서로 자동 업데이트
        - 각 단계마다 5초 대기
        - 첫 단계(PAYMENT_COMPLETED)는 이미 설정되어 있을 수 있으므로 건너뜀
        - 시스템 자동 업데이트 (changed_by=1)
        - 각 단계마다 commit하여 DB에 반영
    """
    status_sequence = [
        "PAYMENT_COMPLETED",
        "PREPARING", 
        "SHIPPING",
        "DELIVERED"
    ]
    
    logger.info(f"홈쇼핑 주문 자동 상태 업데이트 시작: order_id={homeshopping_order_id}")
    
    for i, status_code in enumerate(status_sequence):
        try:
            # 첫 단계는 이미 설정되었을 수 있으므로 건너뜀
            if i == 0:
                logger.info(f"홈쇼핑 주문 {homeshopping_order_id} 상태가 '{status_code}'로 이미 설정되어 있습니다.")
                continue
                
            # 2초 대기
            logger.info(f"홈쇼핑 주문 {homeshopping_order_id} 상태 업데이트 대기 중... (2초 후 '{status_code}'로 변경)")
            await asyncio.sleep(2)
            
            # 상태 업데이트
            logger.info(f"홈쇼핑 주문 {homeshopping_order_id} 상태를 '{status_code}'로 업데이트 중...")
            await update_hs_order_status(
                db=db,
                homeshopping_order_id=homeshopping_order_id,
                new_status_code=status_code,
                changed_by=1  # 시스템 자동 업데이트
            )
            
            # 상태 업데이트 후 commit하여 DB에 반영
            await db.commit()
            
            # logger.info(f"홈쇼핑 주문 {homeshopping_order_id} 상태가 '{status_code}'로 업데이트되었습니다.")
            
        except Exception as e:
            logger.error(f"홈쇼핑 주문 {homeshopping_order_id} 상태 업데이트 실패: {str(e)}")
            break
    
    logger.info(f"홈쇼핑 주문 자동 상태 업데이트 완료: order_id={homeshopping_order_id}")


async def start_auto_hs_order_status_update(homeshopping_order_id: int):
    """
    홈쇼핑 주문 자동 상태 업데이트를 백그라운드에서 시작하는 함수
    
    Args:
        homeshopping_order_id: 홈쇼핑 주문 ID
    
    Returns:
        None
        
    Note:
        - CRUD 계층: 백그라운드 작업 시작 담당
        - 새로운 DB 세션을 생성하여 자동 상태 업데이트 실행
        - 백그라운드 작업 실패는 전체 프로세스를 중단하지 않음
        - 첫 번째 세션만 사용하여 리소스 효율성 확보
    """
    try:
        logger.info(f"홈쇼핑 주문 자동 상태 업데이트 백그라운드 작업 시작: order_id={homeshopping_order_id}")
        
        # 새로운 DB 세션 생성
        async for db in get_maria_service_db():
            await auto_update_hs_order_status(homeshopping_order_id, db)
            break  # 첫 번째 세션만 사용
            
    except Exception as e:
        logger.error(f"❌ 홈쇼핑 주문 자동 상태 업데이트 백그라운드 작업 실패: homeshopping_order_id={homeshopping_order_id}, error={str(e)}")
        # 백그라운드 작업 실패는 전체 프로세스를 중단하지 않음


# -----------------------------
# 주문 관련 CRUD 함수 (기본 구조)
# -----------------------------

async def calculate_homeshopping_order_price(
    db: AsyncSession,
    product_id: int,
    quantity: int = 1
) -> dict:
    """
    홈쇼핑 주문 금액 계산 (최적화: 윈도우 함수로 최신 상품 정보 조회)
    
    Args:
        db: 데이터베이스 세션
        product_id: 상품 ID
        quantity: 수량 (기본값: 1)
    
    Returns:
        dict: 가격 정보 (product_id, product_name, dc_price, quantity, order_price)
        
    Note:
        - CRUD 계층: DB 조회만 담당, 트랜잭션 변경 없음
        - 윈도우 함수를 사용하여 최신 상품 정보를 한 번에 조회
        - 할인가(dc_price) 우선 사용, 없으면 할인율 적용하여 계산
        - 최종 주문 금액 = 할인가 × 수량
    """
    from sqlalchemy import text
    
    # 최적화된 쿼리: 윈도우 함수를 사용하여 최신 상품 정보를 한 번에 조회
    sql_query = """
    WITH latest_product_info AS (
        SELECT 
            hl.product_id,
            hl.product_name,
            ROW_NUMBER() OVER (
                PARTITION BY hl.product_id 
                ORDER BY hl.live_date DESC, hl.live_start_time DESC
            ) as rn
        FROM FCT_HOMESHOPPING_LIST hl
        WHERE hl.product_id = :product_id
    )
    SELECT 
        hpi.product_id,
        hpi.sale_price,
        hpi.dc_price,
        hpi.dc_rate,
        COALESCE(lpi.product_name, CONCAT('상품_', hpi.product_id)) as product_name
    FROM FCT_HOMESHOPPING_PRODUCT_INFO hpi
    LEFT JOIN latest_product_info lpi ON hpi.product_id = lpi.product_id AND lpi.rn = 1
    WHERE hpi.product_id = :product_id
    """
    
    try:
        result = await db.execute(text(sql_query), {"product_id": product_id})
        product_data = result.fetchone()
    except Exception as e:
        logger.error(f"홈쇼핑 상품 정보 조회 SQL 실행 실패: product_id={product_id}, error={str(e)}")
        raise
    
    if not product_data:
        logger.warning(f"홈쇼핑 상품을 찾을 수 없음: product_id={product_id}")
        raise ValueError("상품을 찾을 수 없습니다.")
    
    # 주문 금액 계산
    dc_price = product_data.dc_price or (product_data.sale_price * (1 - (product_data.dc_rate or 0) / 100)) or 0
    order_price = dc_price * quantity
    
    return {
        "product_id": product_id,
        "product_name": product_data.product_name,
        "dc_price": dc_price,
        "quantity": quantity,
        "order_price": order_price
    }
