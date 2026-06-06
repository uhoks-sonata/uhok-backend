"""Kok order status/update CRUD functions."""

import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.database.mariadb_service import get_maria_service_db
from common.logger import get_logger
from services.order.models.order_base_model import Order, StatusMaster
from services.order.models.kok.kok_order_model import KokOrder, KokOrderStatusHistory
from services.kok.models.interaction_model import KokNotification
from services.order.crud.order_common import (
    get_status_by_code,
    NOTIFICATION_TITLES,
    NOTIFICATION_MESSAGES,
)

logger = get_logger("kok_order_crud")

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
    ORDER BY kosh.changed_at DESC, kosh.history_id DESC
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
                ORDER BY kosh.changed_at DESC, kosh.history_id DESC
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
    ORDER BY kosh.changed_at DESC, kosh.history_id DESC
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
        logger.info(f"콕 주문 자동 상태 업데이트 백그라운드 작업 시작: order_id={kok_order_id}")
        
        # 새로운 DB 세션 생성
        async for db in get_maria_service_db():
            await auto_update_order_status(kok_order_id, db)
            break  # 첫 번째 세션만 사용
            
    except Exception as e:
        logger.error(f"콕 주문 자동 상태 업데이트 백그라운드 작업 실패: kok_order_id={kok_order_id}, error={str(e)}")
        # 백그라운드 작업 실패는 전체 프로세스를 중단하지 않음


