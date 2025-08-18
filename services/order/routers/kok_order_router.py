from fastapi import APIRouter, Depends, Query, HTTPException, BackgroundTasks, status
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from common.database.mariadb_service import get_maria_service_db
from common.dependencies import get_current_user
from common.log_utils import send_user_log
from common.logger import get_logger

from services.order.models.order_model import Order, KokOrder, KokOrderStatusHistory, StatusMaster

from services.user.schemas.user_schema import UserOut
from services.order.schemas.kok_order_schema import (
    KokCartOrderRequest,
    KokCartOrderResponse,
    KokOrderStatusUpdate,
    KokOrderStatusResponse,
    KokOrderWithStatusResponse,
    KokNotificationSchema,
    KokNotificationListResponse
)

from services.order.crud.kok_order_crud import (
    create_orders_from_selected_carts,
    update_kok_order_status,
    get_kok_order_with_current_status,
    get_kok_order_status_history,
    start_auto_kok_order_status_update,
    get_kok_order_notifications_history
)

router = APIRouter(prefix="/api/orders/kok", tags=["Kok Orders"])
logger = get_logger("kok_order_router")


# ================================
# 주문 관련 API
# ================================

# 단일 상품 주문 API는 사용하지 않습니다. (멀티 카트 주문 API 사용)

@router.post("/carts/order", response_model=KokCartOrderResponse, status_code=status.HTTP_201_CREATED)
async def order_from_selected_carts(
    request: KokCartOrderRequest,
    current_user: UserOut = Depends(get_current_user),
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_maria_service_db),
):
    logger.info(f"장바구니 주문 시작: user_id={current_user.user_id}, selected_items_count={len(request.selected_items)}")
    
    if not request.selected_items:
        logger.warning(f"선택된 항목이 없음: user_id={current_user.user_id}")
        raise HTTPException(status_code=400, detail="선택된 항목이 없습니다.")

    result = await create_orders_from_selected_carts(
        db, current_user.user_id, [i.model_dump() for i in request.selected_items]
    )

    logger.info(f"장바구니 주문 완료: user_id={current_user.user_id}, order_id={result['order_id']}, order_count={result['order_count']}")

    if background_tasks:
        background_tasks.add_task(
            send_user_log,
            user_id=current_user.user_id,
            event_type="cart_order_create",
            event_data=result,
        )

    return KokCartOrderResponse(
        order_id=result["order_id"],
        order_count=result["order_count"],
        message=result["message"],
    )


# ================================
# 콕 주문 상태 관리 API
# ================================

@router.patch("/{kok_order_id}/status", response_model=KokOrderStatusResponse)
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
        logger.error(f"주문 상태 업데이트 실패: kok_order_id={kok_order_id}, error={str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{kok_order_id}/status", response_model=KokOrderStatusResponse)
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


@router.get("/{kok_order_id}/with-status", response_model=KokOrderWithStatusResponse)
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


# 결제 확인(테스트/웹훅용): PAYMENT_REQUESTED -> PAYMENT_COMPLETED
# - 결제 모듈/PG사 콜백과 연동할 때 주문 단건 기준으로 호출하는 API입니다.
@router.post("/{kok_order_id}/payment/confirm")
async def confirm_payment(
    kok_order_id: int,
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_maria_service_db),
    user=Depends(get_current_user)
):
    """
    결제확인(단건)
    - 현재 상태가 PAYMENT_REQUESTED인 해당 `kok_order_id`의 주문을 PAYMENT_COMPLETED로 변경
    - 권한: 주문자 본인만 가능
    - 부가효과: 상태 변경 이력/알림 기록
    """
    # 권한 확인
    kok_order_result = await db.execute(
        select(KokOrder).where(KokOrder.kok_order_id == kok_order_id)
    )
    kok_order = kok_order_result.scalars().first()
    if not kok_order:
        raise HTTPException(status_code=404, detail="주문을 찾을 수 없습니다.")

    order_result = await db.execute(select(Order).where(Order.order_id == kok_order.order_id))
    order = order_result.scalars().first()
    if not order or order.user_id != user.user_id:
        raise HTTPException(status_code=403, detail="해당 주문에 대한 권한이 없습니다.")

    try:
        await update_kok_order_status(db, kok_order_id, "PAYMENT_COMPLETED", user.user_id)

        if background_tasks:
            background_tasks.add_task(
                send_user_log,
                user_id=user.user_id,
                event_type="payment_confirm",
                event_data={"kok_order_id": kok_order_id},
            )

        return {"message": "결제가 완료되어 상태가 변경되었습니다.", "kok_order_id": kok_order_id}
    except Exception as e:
        logger.error(f"결제 확인 실패: kok_order_id={kok_order_id}, error={str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


# 결제완료 콜백(주문 단위): 해당 order_id의 모든 KokOrder를 PAYMENT_COMPLETED로 변경
# - 여러 상품을 한 번에 결제한 경우 한 번의 콜백으로 전체 업데이트할 때 사용합니다.
@router.post("/order-unit/{order_id}/payment/confirm")
async def confirm_payment_by_order(
    order_id: int,
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_maria_service_db),
    user=Depends(get_current_user),
):
    """
    결제확인(주문 단위)
    - 주어진 `order_id`에 속한 모든 KokOrder를 PAYMENT_COMPLETED로 변경
    - 권한: 주문자 본인만 가능
    - 부가효과: 각 주문 항목에 대한 상태 변경 이력/알림 기록
    """
    # 권한 확인
    order_result = await db.execute(select(Order).where(Order.order_id == order_id))
    order = order_result.scalars().first()
    if not order or order.user_id != user.user_id:
        raise HTTPException(status_code=403, detail="해당 주문에 대한 권한이 없습니다.")

    kok_result = await db.execute(select(KokOrder).where(KokOrder.order_id == order_id))
    kok_orders = kok_result.scalars().all()
    if not kok_orders:
        raise HTTPException(status_code=404, detail="해당 주문의 KokOrder가 없습니다.")

    try:
        for ko in kok_orders:
            await update_kok_order_status(db, ko.kok_order_id, "PAYMENT_COMPLETED", user.user_id)

        if background_tasks:
            background_tasks.add_task(
                send_user_log,
                user_id=user.user_id,
                event_type="payment_confirm_order",
                event_data={"order_id": order_id, "kok_order_count": len(kok_orders)},
            )

        return {"message": "결제가 완료되어 모든 KokOrder 상태가 변경되었습니다.", "order_id": order_id}
    except Exception as e:
        logger.error(f"주문 단위 결제 확인 실패: order_id={order_id}, error={str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{kok_order_id}/auto-update", status_code=status.HTTP_200_OK)
async def start_auto_status_update_api(
    kok_order_id: int,
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_maria_service_db),
    user=Depends(get_current_user)
):
    """
    특정 주문의 자동 상태 업데이트 시작 (테스트용)
    - 결제 완료 상태인 경우에만 자동 업데이트 시작
    """
    try:
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
        
        # 디버깅: 직접 상태 이력 조회
        
        # 1단계: 상태 이력만 조회
        history_result = await db.execute(
            select(KokOrderStatusHistory)
            .where(KokOrderStatusHistory.kok_order_id == kok_order_id)
            .order_by(desc(KokOrderStatusHistory.changed_at))
            .limit(1)
        )
        
        current_history = history_result.scalars().first()
        if not current_history:
            raise HTTPException(
                status_code=400, 
                detail="주문이 생성되었지만 아직 상태 이력이 없습니다."
            )
        
        logger.info(f"상태 이력 조회 성공: history_id={current_history.history_id}, status_id={current_history.status_id}")
        
        # 2단계: 상태 정보 조회
        status_result = await db.execute(
            select(StatusMaster).where(StatusMaster.status_id == current_history.status_id)
        )
        
        current_status = status_result.scalars().first()
        if not current_status:
            logger.error(f"상태 ID {current_history.status_id}에 해당하는 상태 정보를 찾을 수 없습니다.")
            raise HTTPException(
                status_code=400, 
                detail=f"상태 ID {current_history.status_id}에 해당하는 상태 정보를 찾을 수 없습니다."
            )
        
        logger.info(f"상태 정보 조회 성공: status_id={current_status.status_id}, status_code={current_status.status_code}, status_name={current_status.status_name}")
        
        # 결제 완료 상태가 아니면 에러 반환
        if current_status.status_code != "PAYMENT_COMPLETED":
            raise HTTPException(
                status_code=400, 
                detail=f"결제 완료 상태가 아닙니다. 현재 상태: {current_status.status_name} ({current_status.status_code})"
            )
        
        # 자동 상태 업데이트 시작
        if background_tasks:
            background_tasks.add_task(
                start_auto_kok_order_status_update,
                kok_order_id=kok_order_id,
                db_session_generator=get_maria_service_db()
            )
        
        return {"message": f"주문 {kok_order_id}의 자동 상태 업데이트가 시작되었습니다. (현재 상태: {current_status.status_name})"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"자동 상태 업데이트 시작 실패: kok_order_id={kok_order_id}, error={str(e)}")
        raise HTTPException(status_code=500, detail=f"서버 오류가 발생했습니다: {str(e)}")

# -------------------------
# 알림 관련 APi
# -------------------------

@router.get("/notifications/history", response_model=KokNotificationListResponse)
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
    
    # 딕셔너리 리스트를 Pydantic 모델로 변환
    notification_schemas = []
    for notification_dict in notifications:
        notification_schema = KokNotificationSchema(
            notification_id=notification_dict["notification_id"],
            user_id=notification_dict["user_id"],
            kok_order_id=notification_dict["kok_order_id"],
            status_id=notification_dict["status_id"],
            title=notification_dict["title"],
            message=notification_dict["message"],
            created_at=notification_dict["created_at"],
            order_status=notification_dict["order_status"],
            order_status_name=notification_dict["order_status_name"],
            product_name=notification_dict["product_name"]
        )
        notification_schemas.append(notification_schema)
    
    return KokNotificationListResponse(
        notifications=notification_schemas,
        total_count=total_count
    )
