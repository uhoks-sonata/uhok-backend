"""
통합 주문 조회/상세/통계 API 라우터 (콕, HomeShopping 모두 지원)
"""
from fastapi import APIRouter, Depends, Query, HTTPException, BackgroundTasks, status
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta
from typing import List

from services.order.schemas.order_schema import (
    OrderRead, 
    OrderCountResponse, 
    KokOrderStatusUpdate, 
    KokOrderStatusResponse,
    KokOrderWithStatusResponse,
    KokNotificationSchema,
    KokNotificationListResponse
)
from services.order.models.order_model import Order
from services.order.crud.order_crud import (
    get_order_by_id, 
    update_kok_order_status, 
    get_kok_order_with_current_status, 
    get_kok_order_status_history,
    start_auto_status_update,
    get_kok_order_notifications_history
)
from common.database.mariadb_service import get_maria_service_db
from common.dependencies import get_current_user
from common.log_utils import send_user_log


router = APIRouter(prefix="/api/orders", tags=["Orders"])

@router.get("/", response_model=List[OrderRead])
async def list_orders(
    limit: int = Query(10, description="조회 개수"),
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_maria_service_db),
    user=Depends(get_current_user)
):
    """
    내 주문 리스트 (공통+서비스별 상세 포함)
    """
    from services.order.models.order_model import Order, KokOrder
    # from services.order.models.order_model import HomeShoppingOrder

    # 주문 기본 정보 조회
    result = await db.execute(
        select(Order)
        .where(Order.user_id == user.user_id)
        .order_by(Order.order_time.desc())
        .limit(limit)
    )
    orders = result.scalars().all()
    
    # 각 주문에 대한 상세 정보 조회
    order_list = []
    for order in orders:
        # 콕 주문 정보 조회
        kok_result = await db.execute(
            select(KokOrder).where(KokOrder.order_id == order.order_id)
        )
        kok_order = kok_result.scalars().first()
        
        # OrderRead 형태로 변환
        order_data = {
            "order_id": order.order_id,
            "user_id": order.user_id,
            "order_time": order.order_time,
            "cancel_time": order.cancel_time,
            "kok_order": kok_order,
            "homeshopping_order": None
        }
        order_list.append(order_data)
    
    # 주문 목록 조회 로그 기록
    if background_tasks:
        background_tasks.add_task(
            send_user_log, 
            user_id=user.user_id, 
            event_type="order_list_view", 
            event_data={"limit": limit, "order_count": len(order_list)}
        )
    
    return order_list


@router.get("/count", response_model=OrderCountResponse)
async def order_count(
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_maria_service_db),
    user=Depends(get_current_user)
):
    """
    로그인 사용자의 전체 주문 개수 조회
    """
    result = await db.execute(
        select(func.count()).select_from(Order).where(Order.user_id == user.user_id) # type: ignore
    )
    count = result.scalar()
    
    # 주문 개수 조회 로그 기록
    if background_tasks:
        background_tasks.add_task(
            send_user_log, 
            user_id=user.user_id, 
            event_type="order_count_view", 
            event_data={"order_count": count}
        )
    
    return OrderCountResponse(order_count=count)

@router.get("/recent", response_model=List[OrderRead])
async def recent_orders(
    days: int = Query(7, description="최근 조회 일수 (default=7)"),
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_maria_service_db),
    user=Depends(get_current_user)
):
    """
    최근 N일간 주문 내역 리스트 조회
    """
    from services.order.models.order_model import Order, KokOrder
    # from services.order.models.order_model import HomeShoppingOrder
    since = datetime.now() - timedelta(days=days)
    
    # 주문 기본 정보 조회
    result = await db.execute(
        select(Order)
        .where(Order.user_id == user.user_id)
        .where(Order.order_time >= since)
        .order_by(desc(Order.order_time))
    )
    orders = result.scalars().all()
    
    # 각 주문에 대한 상세 정보 조회
    order_list = []
    for order in orders:
        # 콕 주문 정보 조회
        kok_result = await db.execute(
            select(KokOrder).where(KokOrder.order_id == order.order_id)
        )
        kok_order = kok_result.scalars().first()
        
        # OrderRead 형태로 변환
        order_data = {
            "order_id": order.order_id,
            "user_id": order.user_id,
            "order_time": order.order_time,
            "cancel_time": order.cancel_time,
            "kok_order": kok_order,
            "homeshopping_order": None
        }
        order_list.append(order_data)
    
    # 최근 주문 조회 로그 기록
    if background_tasks:
        background_tasks.add_task(
            send_user_log, 
            user_id=user.user_id, 
            event_type="recent_orders_view", 
            event_data={"days": days, "order_count": len(order_list)}
        )
    
    return order_list


@router.get("/{order_id}", response_model=OrderRead)
async def read_order(
        order_id: int,
        background_tasks: BackgroundTasks = None,
        db: AsyncSession = Depends(get_maria_service_db),
        user=Depends(get_current_user)
):
    """
    단일 주문 조회 (공통+콕+HomeShopping 상세 포함)
    """
    order_data = await get_order_by_id(db, order_id)
    if not order_data or order_data["user_id"] != user.user_id:
        raise HTTPException(status_code=404, detail="주문 내역이 없습니다.")

    # 주문 상세 조회 로그 기록
    if background_tasks:
        background_tasks.add_task(
            send_user_log,
            user_id=user.user_id,
            event_type="order_detail_view",
            event_data={"order_id": order_id}
        )

    return order_data

# ================================
# 콕 주문 상태 관리 API
# ================================

@router.patch("/kok/{kok_order_id}/status", response_model=KokOrderStatusResponse)
async def update_kok_order_status_api(
    kok_order_id: int,
    status_update: KokOrderStatusUpdate,
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_maria_service_db),
    user=Depends(get_current_user)
):
    """
    콕 주문 상태 업데이트 (INSERT만 사용)
    """
    try:
        # 사용자 권한 확인 - order 정보 명시적으로 로드
        kok_order_result = await db.execute(
            select(KokOrder).where(KokOrder.kok_order_id == kok_order_id)
        )
        kok_order = kok_order_result.scalars().first()
        if not kok_order:
            raise HTTPException(status_code=404, detail="주문을 찾을 수 없습니다.")
        
        order_result = await db.execute(
            select(Order).where(Order.order_id == kok_order.order_id)
        )
        order = order_result.scalars().first()
        if not order or order.user_id != user.user_id:
            raise HTTPException(status_code=403, detail="해당 주문에 대한 권한이 없습니다.")
        
        # 상태 업데이트 (INSERT만 사용)
        updated_order = await update_kok_order_status(
            db, 
            kok_order_id, 
            status_update.new_status_code, 
            status_update.changed_by or user.user_id
        )
        
        # 업데이트된 주문과 상태 정보 조회
        order_with_status = await get_kok_order_with_current_status(db, kok_order_id)
        if not order_with_status:
            raise HTTPException(status_code=404, detail="주문을 찾을 수 없습니다.")
        
        kok_order, current_status, current_status_history = order_with_status
        
        # 상태 변경 이력 조회
        status_history = await get_kok_order_status_history(db, kok_order_id)
        
        # 상태 변경 로그 기록
        if background_tasks:
            background_tasks.add_task(
                send_user_log,
                user_id=user.user_id,
                event_type="kok_order_status_update",
                event_data={
                    "kok_order_id": kok_order_id,
                    "new_status": status_update.new_status_code,
                    "changed_by": status_update.changed_by or user.user_id
                }
            )
        
        return KokOrderStatusResponse(
            kok_order_id=kok_order_id,
            current_status=current_status,
            status_history=status_history
        )
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/kok/{kok_order_id}/status", response_model=KokOrderStatusResponse)
async def get_kok_order_status(
    kok_order_id: int,
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_maria_service_db),
    user=Depends(get_current_user)
):
    """
    콕 주문 현재 상태 및 변경 이력 조회 (가장 최근 이력 사용)
    """
    # 주문과 현재 상태 조회
    order_with_status = await get_kok_order_with_current_status(db, kok_order_id)
    if not order_with_status:
        raise HTTPException(status_code=404, detail="주문을 찾을 수 없습니다.")
    
    kok_order, current_status, current_status_history = order_with_status
    
    # 사용자 권한 확인 (주문자만 조회 가능) - order 정보 명시적으로 로드
    order_result = await db.execute(
        select(Order).where(Order.order_id == kok_order.order_id)
    )
    order = order_result.scalars().first()
    if not order or order.user_id != user.user_id:
        raise HTTPException(status_code=403, detail="해당 주문에 대한 권한이 없습니다.")
    
    # 상태 변경 이력 조회
    status_history = await get_kok_order_status_history(db, kok_order_id)
    
    # 상태 조회 로그 기록
    if background_tasks:
        background_tasks.add_task(
            send_user_log,
            user_id=user.user_id,
            event_type="kok_order_status_view",
            event_data={"kok_order_id": kok_order_id}
        )
    
    return KokOrderStatusResponse(
        kok_order_id=kok_order_id,
        current_status=current_status,
        status_history=status_history
    )

@router.get("/kok/{kok_order_id}/with-status", response_model=KokOrderWithStatusResponse)
async def get_kok_order_with_status(
    kok_order_id: int,
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_maria_service_db),
    user=Depends(get_current_user)
):
    """
    콕 주문과 현재 상태를 함께 조회
    """
    # 주문과 현재 상태 조회
    order_with_status = await get_kok_order_with_current_status(db, kok_order_id)
    if not order_with_status:
        raise HTTPException(status_code=404, detail="주문을 찾을 수 없습니다.")
    
    kok_order, current_status, _ = order_with_status
    
    # 사용자 권한 확인 - order 정보 명시적으로 로드
    order_result = await db.execute(
        select(Order).where(Order.order_id == kok_order.order_id)
    )
    order = order_result.scalars().first()
    if not order or order.user_id != user.user_id:
        raise HTTPException(status_code=403, detail="해당 주문에 대한 권한이 없습니다.")
    
    # 주문과 상태 함께 조회 로그 기록
    if background_tasks:
        background_tasks.add_task(
            send_user_log,
            user_id=user.user_id,
            event_type="kok_order_with_status_view",
            event_data={"kok_order_id": kok_order_id}
        )
    
    return KokOrderWithStatusResponse(
        kok_order=kok_order,
        current_status=current_status
    )

@router.post("/kok/{kok_order_id}/auto-update", status_code=status.HTTP_200_OK)
async def start_auto_status_update_api(
    kok_order_id: int,
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_maria_service_db),
    user=Depends(get_current_user)
):
    """
    특정 주문의 자동 상태 업데이트 시작 (테스트용)
    """
    # 사용자 권한 확인
    kok_order_result = await db.execute(
        select(KokOrder).where(KokOrder.kok_order_id == kok_order_id)
    )
    kok_order = kok_order_result.scalars().first()
    if not kok_order:
        raise HTTPException(status_code=404, detail="주문을 찾을 수 없습니다.")
    
    order_result = await db.execute(
        select(Order).where(Order.order_id == kok_order.order_id)
    )
    order = order_result.scalars().first()
    if not order or order.user_id != user.user_id:
        raise HTTPException(status_code=403, detail="해당 주문에 대한 권한이 없습니다.")
    
    # 자동 상태 업데이트 시작
    if background_tasks:
        background_tasks.add_task(
            start_auto_status_update,
            kok_order_id=kok_order_id,
            db_session_generator=get_maria_service_db()
        )
    
    return {"message": f"주문 {kok_order_id}의 자동 상태 업데이트가 시작되었습니다."}

# ================================
# 알림 관리 API
# ================================

# @router.patch("/kok/notifications/{notification_id}/read")
# async def mark_notification_as_read_api(
#     notification_id: int,
#     user: User = Depends(get_current_user),
#     db: AsyncSession = Depends(get_maria_service_db)
# ):
#     """
#     알림 읽음 처리
#     """
#     from services.order.crud.order_crud import mark_notification_as_read
#     
#     success = await mark_notification_as_read(db, notification_id, user.user_id)
#     
#     if not success:
#         raise HTTPException(status_code=404, detail="알림을 찾을 수 없습니다")
#     
#     return {"message": "알림이 읽음 처리되었습니다"}

@router.get("/kok/notifications/history", response_model=KokNotificationListResponse)
async def get_kok_order_notifications_history_api(
    limit: int = Query(20, description="조회 개수"),
    offset: int = Query(0, description="시작 위치"),
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_maria_service_db),
    user=Depends(get_current_user)
):
    """
    콕 상품 주문 내역 현황 알림 조회
    주문완료, 배송출발, 배송완료 알림만 조회
    """
    notifications, total_count = await get_kok_order_notifications_history(
        db, user.user_id, limit, offset
    )
    
    # 콕 주문 현황 알림 조회 로그 기록
    if background_tasks:
        background_tasks.add_task(
            send_user_log,
            user_id=user.user_id,
            event_type="kok_order_notifications_history_view",
            event_data={
                "limit": limit,
                "offset": offset,
                "notification_count": len(notifications)
            }
        )
    
    return KokNotificationListResponse(
        notifications=notifications,
        total_count=total_count
    )
