from datetime import date
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from common.database.mariadb_service import get_maria_service_db
from common.dependencies import get_current_user_optional
from common.http_dependencies import extract_http_info
from common.log_utils import send_user_log
from common.logger import get_logger
from services.homeshopping.crud.schedule_crud import get_homeshopping_schedule
from services.homeshopping.schemas.schedule_schema import HomeshoppingScheduleResponse

logger = get_logger("homeshopping_router", level="DEBUG")
router = APIRouter()

@router.get("/schedule", response_model=HomeshoppingScheduleResponse)
async def get_schedule(
        request: Request,
        live_date: Optional[date] = Query(None, description="조회할 날짜 (YYYY-MM-DD 형식, 미입력시 전체 스케줄)"),
        background_tasks: BackgroundTasks = None,
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    홈쇼핑 편성표 조회 (식품만) - 최적화된 버전
    - live_date가 제공되면 해당 날짜의 스케줄만 조회
    - live_date가 미입력시 전체 스케줄 조회
    - 제한 없이 모든 결과 반환
    """
    logger.debug(f"홈쇼핑 편성표 조회 시작: live_date={live_date}")
    
    current_user = await get_current_user_optional(request)
    user_id = current_user.user_id if current_user else None
    
    if not current_user:
        logger.warning("인증되지 않은 사용자가 편성표 조회 요청")
    
    logger.info(f"홈쇼핑 편성표 조회 요청: user_id={user_id}, live_date={live_date}")
    
    try:
        logger.info(f"=== 라우터에서 get_homeshopping_schedule 호출 시작 ===")
        schedules = await get_homeshopping_schedule(
            db, 
            live_date=live_date
        )
        logger.info(f"=== 라우터에서 get_homeshopping_schedule 호출 완료: 결과={len(schedules)} ===")
        logger.debug(f"편성표 조회 성공: 결과 수={len(schedules)}")
    except Exception as e:
        logger.error(f"편성표 조회 실패: user_id={user_id}, error={str(e)}")
        raise HTTPException(status_code=500, detail="편성표 조회 중 오류가 발생했습니다.")
    
    # 편성표 조회 로그 기록 (인증된 사용자인 경우에만)
    if current_user and background_tasks:
        http_info = extract_http_info(request, response_code=200)
        background_tasks.add_task(
            send_user_log, 
            user_id=current_user.user_id, 
            event_type="homeshopping_schedule_view", 
            event_data={
                "live_date": live_date.isoformat() if live_date else None,
                "total_count": len(schedules)
            },
            **http_info  # HTTP 정보를 키워드 인자로 전달
        )
    
    logger.info(f"홈쇼핑 편성표 조회 완료: user_id={user_id}, 결과 수={len(schedules)}")
    
    return {
        "schedules": schedules
    }
