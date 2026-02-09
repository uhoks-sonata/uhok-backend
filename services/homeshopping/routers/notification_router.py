from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from common.database.mariadb_service import get_maria_service_db
from common.dependencies import get_current_user
from common.http_dependencies import extract_http_info
from common.log_utils import send_user_log
from common.logger import get_logger
from services.homeshopping.crud.notification_crud import (
    get_notifications_with_filter,
    mark_notification_as_read,
)
from services.homeshopping.schemas.notification_schema import HomeshoppingNotificationListResponse
from services.user.schemas.profile_schema import UserOut

logger = get_logger("homeshopping_router", level="DEBUG")
router = APIRouter()

@router.get("/notifications/orders", response_model=HomeshoppingNotificationListResponse)
async def get_order_notifications_api(
        request: Request,
        limit: int = Query(20, ge=1, le=100, description="조회할 주문 알림 개수"),
        offset: int = Query(0, ge=0, description="시작 위치"),
        current_user: UserOut = Depends(get_current_user),
        background_tasks: BackgroundTasks = None,
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    홈쇼핑 주문 상태 변경 알림만 조회
    """
    logger.debug(f"홈쇼핑 주문 알림 조회 시작: user_id={current_user.user_id}, limit={limit}, offset={offset}")
    logger.info(f"홈쇼핑 주문 알림 조회 요청: user_id={current_user.user_id}, limit={limit}, offset={offset}")
    
    try:
        notifications, total_count = await get_notifications_with_filter(
            db, 
            current_user.user_id, 
            notification_type="order_status",
            limit=limit, 
            offset=offset
        )
        logger.debug(f"주문 알림 조회 성공: user_id={current_user.user_id}, 결과 수={len(notifications)}, 전체={total_count}")
        
        # 주문 알림 조회 로그 기록
        if background_tasks:
            http_info = extract_http_info(request, response_code=200)
            background_tasks.add_task(
                send_user_log, 
                user_id=current_user.user_id, 
                event_type="homeshopping_order_notifications_view", 
                event_data={
                    "limit": limit,
                    "offset": offset,
                    "notification_count": len(notifications),
                    "total_count": total_count
                },
                **http_info  # HTTP 정보를 키워드 인자로 전달
            )
        
        logger.info(f"홈쇼핑 주문 알림 조회 완료: user_id={current_user.user_id}, 결과 수={len(notifications)}, 전체 개수={total_count}")
        
        has_more = (offset + limit) < total_count
        return {
            "notifications": notifications,
            "total_count": total_count,
            "has_more": has_more
        }
        
    except Exception as e:
        logger.error(f"홈쇼핑 주문 알림 조회 실패: user_id={current_user.user_id}, error={str(e)}")
        raise HTTPException(status_code=500, detail="주문 알림 조회 중 오류가 발생했습니다.")


@router.get("/notifications/broadcasts", response_model=HomeshoppingNotificationListResponse)
async def get_broadcast_notifications_api(
        request: Request,
        limit: int = Query(20, ge=1, le=100, description="조회할 방송 알림 개수"),
        offset: int = Query(0, ge=0, description="시작 위치"),
        current_user: UserOut = Depends(get_current_user),
        background_tasks: BackgroundTasks = None,
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    홈쇼핑 방송 시작 알림만 조회
    """
    logger.debug(f"홈쇼핑 방송 알림 조회 시작: user_id={current_user.user_id}, limit={limit}, offset={offset}")
    logger.info(f"홈쇼핑 방송 알림 조회 요청: user_id={current_user.user_id}, limit={limit}, offset={offset}")
    
    try:
        notifications, total_count = await get_notifications_with_filter(
            db, 
            current_user.user_id, 
            notification_type="broadcast_start",
            limit=limit, 
            offset=offset
        )
        logger.debug(f"방송 알림 조회 성공: user_id={current_user.user_id}, 결과 수={len(notifications)}, 전체={total_count}")
        
        # 방송 알림 조회 로그 기록
        if background_tasks:
            http_info = extract_http_info(request, response_code=200)
            background_tasks.add_task(
                send_user_log, 
                user_id=current_user.user_id, 
                event_type="homeshopping_broadcast_notifications_view", 
                event_data={
                    "limit": limit,
                    "offset": offset,
                    "notification_count": len(notifications),
                    "total_count": total_count
                },
                **http_info  # HTTP 정보를 키워드 인자로 전달
            )
        
        logger.info(f"홈쇼핑 방송 알림 조회 완료: user_id={current_user.user_id}, 결과 수={len(notifications)}, 전체 개수={total_count}")
        
        has_more = (offset + limit) < total_count
        return {
            "notifications": notifications,
            "total_count": total_count,
            "has_more": has_more
        }
        
    except Exception as e:
        logger.error(f"홈쇼핑 방송 알림 조회 실패: user_id={current_user.user_id}, error={str(e)}")
        raise HTTPException(status_code=500, detail="방송 알림 조회 중 오류가 발생했습니다.")


@router.get("/notifications/all", response_model=HomeshoppingNotificationListResponse)
async def get_all_notifications_api(
        request: Request,
        limit: int = Query(20, ge=1, le=100, description="조회할 알림 개수"),
        offset: int = Query(0, ge=0, description="시작 위치"),
        current_user: UserOut = Depends(get_current_user),
        background_tasks: BackgroundTasks = None,
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    홈쇼핑 모든 알림 통합 조회 (주문 + 방송)
    """
    logger.debug(f"홈쇼핑 모든 알림 통합 조회 시작: user_id={current_user.user_id}, limit={limit}, offset={offset}")
    logger.info(f"홈쇼핑 모든 알림 통합 조회 요청: user_id={current_user.user_id}, limit={limit}, offset={offset}")
    
    try:
        notifications, total_count = await get_notifications_with_filter(
            db, 
            current_user.user_id, 
            limit=limit, 
            offset=offset
        )
        logger.debug(f"모든 알림 통합 조회 성공: user_id={current_user.user_id}, 결과 수={len(notifications)}, 전체={total_count}")
        
        # 모든 알림 통합 조회 로그 기록
        if background_tasks:
            http_info = extract_http_info(request, response_code=200)
            background_tasks.add_task(
                send_user_log, 
                user_id=current_user.user_id, 
                event_type="homeshopping_all_notifications_view", 
                event_data={
                    "limit": limit,
                    "offset": offset,
                    "notification_count": len(notifications),
                    "total_count": total_count
                },
                **http_info  # HTTP 정보를 키워드 인자로 전달
            )
        
        logger.info(f"홈쇼핑 모든 알림 통합 조회 완료: user_id={current_user.user_id}, 결과 수={len(notifications)}, 전체 개수={total_count}")
        
        has_more = (offset + limit) < total_count
        return {
            "notifications": notifications,
            "total_count": total_count,
            "has_more": has_more
        }
        
    except Exception as e:
        logger.error(f"홈쇼핑 모든 알림 통합 조회 실패: user_id={current_user.user_id}, error={str(e)}")
        raise HTTPException(status_code=500, detail="모든 알림 통합 조회 중 오류가 발생했습니다.")


@router.put("/notifications/{notification_id}/read")
async def mark_notification_read_api(
        request: Request,
        notification_id: int,
        current_user: UserOut = Depends(get_current_user),
        background_tasks: BackgroundTasks = None,
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    홈쇼핑 알림 읽음 처리
    """
    logger.debug(f"홈쇼핑 알림 읽음 처리 시작: user_id={current_user.user_id}, notification_id={notification_id}")
    logger.info(f"홈쇼핑 알림 읽음 처리 요청: user_id={current_user.user_id}, notification_id={notification_id}")
    
    try:
        success = await mark_notification_as_read(db, current_user.user_id, notification_id)
        
        if not success:
            logger.warning(f"알림을 찾을 수 없음: notification_id={notification_id}")
            raise HTTPException(status_code=404, detail="알림을 찾을 수 없습니다.")
        
        await db.commit()
        logger.debug(f"알림 읽음 처리 성공: notification_id={notification_id}")
        
        # 알림 읽음 처리 로그 기록
        if background_tasks:
            http_info = extract_http_info(request, response_code=200)
            background_tasks.add_task(
                send_user_log, 
                user_id=current_user.user_id, 
                event_type="homeshopping_notification_read", 
                event_data={"notification_id": notification_id},
                **http_info  # HTTP 정보를 키워드 인자로 전달
            )
        
        logger.info(f"홈쇼핑 알림 읽음 처리 완료: notification_id={notification_id}")
        return {"message": "알림이 읽음으로 표시되었습니다."}
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"홈쇼핑 알림 읽음 처리 실패: notification_id={notification_id}, error={str(e)}")
        raise HTTPException(status_code=500, detail="알림 읽음 처리 중 오류가 발생했습니다.")
