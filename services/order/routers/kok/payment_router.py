"""Kok order payment/automation/notification API routes."""

from fastapi import APIRouter, Depends, Query, HTTPException, BackgroundTasks, status, Request
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from common.database.mariadb_service import get_maria_service_db
from common.dependencies import get_current_user
from common.log_utils import send_user_log
from common.http_dependencies import extract_http_info
from common.logger import get_logger
from services.order.models.order_base_model import Order, StatusMaster
from services.order.models.kok.kok_order_model import KokOrder, KokOrderStatusHistory
from services.order.schemas.kok.notification_schema import (
    KokNotificationSchema,
    KokNotificationListResponse,
)
from services.order.crud.kok.kok_order_notification_crud import get_kok_order_notifications_history
from services.order.crud.kok.kok_order_status_crud import (
    update_kok_order_status,
    start_auto_kok_order_status_update,
)

logger = get_logger("kok_order_router")
router = APIRouter()

@router.post("/{kok_order_id}/payment/confirm")
async def confirm_payment(
    request: Request,
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
    logger.debug(f"콕 결제 확인 시작: user_id={user.user_id}, kok_order_id={kok_order_id}")
    logger.info(f"콕 결제 확인 요청: user_id={user.user_id}, kok_order_id={kok_order_id}")
    
    # 권한 확인
    kok_order_result = await db.execute(
        select(KokOrder).where(KokOrder.kok_order_id == kok_order_id)
    )
    kok_order = kok_order_result.scalars().first()
    if not kok_order:
        logger.warning(f"콕 주문을 찾을 수 없음: kok_order_id={kok_order_id}, user_id={user.user_id}")
        raise HTTPException(status_code=404, detail="해당 콕 주문을 찾을 수 없습니다.")

    order_result = await db.execute(select(Order).where(Order.order_id == kok_order.order_id))
    order = order_result.scalars().first()
    if not order or order.user_id != user.user_id:
        logger.warning(f"콕 주문 접근 권한 없음: kok_order_id={kok_order_id}, 요청 user_id={user.user_id}, 주문자 user_id={order.user_id if order else None}")
        raise HTTPException(status_code=403, detail="해당 주문에 대한 권한이 없습니다.")

    logger.debug(f"콕 주문 권한 확인 성공: kok_order_id={kok_order_id}, user_id={user.user_id}")

    try:
        await update_kok_order_status(db, kok_order_id, "PAYMENT_COMPLETED", user.user_id)
        logger.debug(f"콕 결제 확인 성공: kok_order_id={kok_order_id}")

        if background_tasks:
            http_info = extract_http_info(request, response_code=200)
            background_tasks.add_task(
                send_user_log,
                user_id=user.user_id,
                event_type="kok_payment_confirm",
                event_data={"kok_order_id": kok_order_id},
                **http_info  # HTTP 정보를 키워드 인자로 전달
            )

        logger.info(f"콕 결제 확인 완료: user_id={user.user_id}, kok_order_id={kok_order_id}")
        return {"message": "결제가 완료되어 상태가 변경되었습니다.", "kok_order_id": kok_order_id}
    except Exception as e:
        logger.error(f"결제 확인 실패: kok_order_id={kok_order_id}, error={str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


# 결제완료 콜백(주문 단위): 해당 order_id의 모든 KokOrder를 PAYMENT_COMPLETED로 변경
# - 여러 상품을 한 번에 결제한 경우 한 번의 콜백으로 전체 업데이트할 때 사용합니다.
@router.post("/order-unit/{order_id}/payment/confirm")
async def confirm_payment_by_order(
    request: Request,
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
    logger.debug(f"콕 주문 단위 결제 확인 시작: user_id={user.user_id}, order_id={order_id}")
    logger.info(f"콕 주문 단위 결제 확인 요청: user_id={user.user_id}, order_id={order_id}")
    
    # 권한 확인
    order_result = await db.execute(select(Order).where(Order.order_id == order_id))
    order = order_result.scalars().first()
    if not order:
        logger.warning(f"주문을 찾을 수 없음: order_id={order_id}, user_id={user.user_id}")
        raise HTTPException(status_code=404, detail="해당 주문을 찾을 수 없습니다.")
    if order.user_id != user.user_id:
        logger.warning(f"주문 접근 권한 없음: order_id={order_id}, 요청 user_id={user.user_id}, 주문자 user_id={order.user_id}")
        raise HTTPException(status_code=403, detail="해당 주문에 대한 권한이 없습니다.")

    kok_result = await db.execute(select(KokOrder).where(KokOrder.order_id == order_id))
    kok_orders = kok_result.scalars().all()
    if not kok_orders:
        logger.warning(f"콕 주문 항목이 없음: order_id={order_id}, user_id={user.user_id}")
        raise HTTPException(status_code=404, detail="해당 주문의 콕 주문 항목이 없습니다.")

    logger.debug(f"콕 주문 항목 조회 성공: order_id={order_id}, kok_order_count={len(kok_orders)}")

    try:
        for ko in kok_orders:
            await update_kok_order_status(db, ko.kok_order_id, "PAYMENT_COMPLETED", user.user_id)
        logger.debug(f"콕 주문 단위 결제 확인 성공: order_id={order_id}, kok_order_count={len(kok_orders)}")

        if background_tasks:
            http_info = extract_http_info(request, response_code=200)
            background_tasks.add_task(
                send_user_log,
                user_id=user.user_id,
                event_type="kok_payment_confirm_order",
                event_data={"order_id": order_id, "kok_order_count": len(kok_orders)},
                **http_info  # HTTP 정보를 키워드 인자로 전달
            )

        logger.info(f"콕 주문 단위 결제 확인 완료: user_id={user.user_id}, order_id={order_id}, kok_order_count={len(kok_orders)}")
        return {"message": "결제가 완료되어 모든 KokOrder 상태가 변경되었습니다.", "order_id": order_id}
    except Exception as e:
        logger.error(f"주문 단위 결제 확인 실패: order_id={order_id}, error={str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{kok_order_id}/auto-update", status_code=status.HTTP_200_OK)
async def start_auto_status_update_api(
    kok_order_id: int,
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_maria_service_db)
):
    """
    특정 주문의 자동 상태 업데이트 시작 (테스트용)
    - 결제 완료 상태인 경우에만 자동 업데이트 시작
    """
    logger.debug(f"콕 자동 상태 업데이트 시작 요청: kok_order_id={kok_order_id}")
    logger.info(f"콕 자동 상태 업데이트 시작 요청: kok_order_id={kok_order_id}")
    
    try:
        # 주문 존재 확인
        kok_order_result = await db.execute(
            select(KokOrder).where(KokOrder.kok_order_id == kok_order_id)
        )
        kok_order = kok_order_result.scalars().first()
        if not kok_order:
            logger.warning(f"콕 주문을 찾을 수 없음: kok_order_id={kok_order_id}")
            raise HTTPException(status_code=404, detail="해당 콕 주문을 찾을 수 없습니다.")
        
        logger.debug(f"콕 주문 조회 성공: kok_order_id={kok_order_id}")
        
        # 디버깅: 직접 상태 이력 조회
        
        # 1단계: 상태 이력만 조회 (같은 시간일 때 history_id로도 정렬)
        history_result = await db.execute(
            select(KokOrderStatusHistory)
            .where(KokOrderStatusHistory.kok_order_id == kok_order_id)
            .order_by(desc(KokOrderStatusHistory.changed_at), desc(KokOrderStatusHistory.history_id))
            .limit(1)
        )
        
        current_history = history_result.scalars().first()
        if not current_history:
            logger.warning(f"상태 이력이 없음: kok_order_id={kok_order_id}")
            raise HTTPException(
                status_code=400, 
                detail="주문이 생성되었지만 아직 상태 이력이 없습니다."
            )
        
        logger.debug(f"상태 이력 조회 성공: history_id={current_history.history_id}, status_id={current_history.status_id}, changed_at={current_history.changed_at}")
        
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
        logger.info(f"현재 상태 확인: kok_order_id={kok_order_id}, current_status={current_status.status_code}, changed_at={current_history.changed_at}")
        
        # 결제 완료 상태가 아니면 에러 반환
        if current_status.status_code != "PAYMENT_COMPLETED":
            logger.warning(f"결제 완료 상태가 아님: kok_order_id={kok_order_id}, current_status={current_status.status_code}")
            logger.warning(f"상태 변경 시간: {current_history.changed_at}")
            
            # 최근 상태 이력들을 모두 조회해서 디버깅
            all_history_result = await db.execute(
                select(KokOrderStatusHistory, StatusMaster)
                .join(StatusMaster, KokOrderStatusHistory.status_id == StatusMaster.status_id)
                .where(KokOrderStatusHistory.kok_order_id == kok_order_id)
                .order_by(desc(KokOrderStatusHistory.changed_at))
                .limit(5)
            )
            all_histories = all_history_result.all()
            logger.warning(f"최근 상태 이력들: {[(h[0].changed_at, h[1].status_code) for h in all_histories]}")
            
            raise HTTPException(
                status_code=400, 
                detail=f"결제 완료 상태가 아닙니다. 현재 상태: {current_status.status_name} ({current_status.status_code})"
            )
        
        # 자동 상태 업데이트 시작
        if background_tasks:
            logger.debug(f"자동 상태 업데이트 백그라운드 작업 시작: kok_order_id={kok_order_id}")
            background_tasks.add_task(
                start_auto_kok_order_status_update,
                kok_order_id=kok_order_id
            )
        
        logger.info(f"콕 자동 상태 업데이트 완료: kok_order_id={kok_order_id}, current_status={current_status.status_code}")
        return {"message": f"주문 {kok_order_id}의 자동 상태 업데이트가 시작되었습니다. (현재 상태: {current_status.status_name})"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"자동 상태 업데이트 시작 실패: kok_order_id={kok_order_id}, error={str(e)}")
        raise HTTPException(status_code=500, detail=f"서버 오류가 발생했습니다: {str(e)}")

@router.get("/notifications/history", response_model=KokNotificationListResponse)
async def get_kok_order_notifications_history_api(
    request: Request,
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
    logger.debug(f"콕 주문 알림 조회 시작: user_id={user.user_id}, limit={limit}, offset={offset}")
    logger.info(f"콕 주문 알림 조회 요청: user_id={user.user_id}, limit={limit}, offset={offset}")
    
    notifications, total_count = await get_kok_order_notifications_history(
        db, user.user_id, limit, offset
    )
    
    logger.debug(f"콕 주문 알림 조회 성공: user_id={user.user_id}, notification_count={len(notifications)}, total_count={total_count}")
    
    # 콕 주문 현황 알림 조회 로그 기록
    if background_tasks:
        http_info = extract_http_info(request, response_code=200)
        background_tasks.add_task(
            send_user_log,
            user_id=user.user_id,
            event_type="kok_order_notifications_history_view",
            event_data={
                "limit": limit,
                "offset": offset,
                "notification_count": len(notifications)
            },
            **http_info  # HTTP 정보를 키워드 인자로 전달
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
    
    logger.info(f"콕 주문 알림 조회 완료: user_id={user.user_id}, notification_count={len(notification_schemas)}, total_count={total_count}")
    return KokNotificationListResponse(
        notifications=notification_schemas,
        total_count=total_count
    )
