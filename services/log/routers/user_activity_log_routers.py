"""
사용자 활동 로그 전용 API 라우터
- 프론트엔드에서 호출하는 사용자 활동 로그 처리
"""
from fastapi import APIRouter, Depends, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from common.dependencies import get_current_user
from common.database.postgres_log import get_postgres_log_db
from common.logger import get_logger

from services.user.schemas.user_schema import UserOut
from services.log.schemas.user_activity_schema import UserActivityLog, UserActivityLogResponse
from services.log.crud.user_activity_log_crud import create_user_activity_log

logger = get_logger("user_activity_log_router")
router = APIRouter(prefix="/api/log/user/activity", tags=["UserActivityLog"])


@router.post("", response_model=UserActivityLogResponse, status_code=status.HTTP_201_CREATED)
async def log_user_activity(
    activity: UserActivityLog,
    current_user: UserOut = Depends(get_current_user),
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_postgres_log_db)
):
    """
    사용자 활동 로그 기록 API
    - 인증된 사용자의 활동을 로그 서비스에 직접 기록
    - 프론트엔드에서 호출하는 활동 로그 처리
    
    지원하는 경로:
    - POST /api/log/user/activity (슬래시 없음)
    
    요청 예시:
    {
      "action": "navigation_click",
      "path": "/mypage",
      "label": "마이페이지",
      "timestamp": "2025-01-27T10:30:00.000Z"
    }
    """
    try:
        # logger.info(f"사용자 활동 로그 기록 시작: user_id={current_user.user_id}, action={activity.action}")
        
        # 사용자 정보 자동 설정 (요청에서 전달된 경우 덮어씀)
        if not activity.user_id:
            activity.user_id = current_user.user_id
        if not activity.user_email:
            activity.user_email = current_user.email
        if not activity.user_username:
            activity.user_username = current_user.username
        
        # 타임스탬프가 없으면 현재 시간으로 설정
        if not activity.timestamp:
            activity.timestamp = datetime.utcnow().isoformat() + "Z"
        
        # 사용자 활동 로그 생성
        log_obj = await create_user_activity_log(
            db=db,
            user_id=current_user.user_id,
            activity=activity
        )
        
        # logger.info(f"사용자 활동 로그 기록 성공: user_id={current_user.user_id}, action={activity.action}, log_id={log_obj.log_id}")
        
        return UserActivityLogResponse(
            message="활동 로그가 성공적으로 기록되었습니다.",
            user_id=current_user.user_id,
            action=activity.action,
            path=activity.path,
            label=activity.label,
            timestamp=activity.timestamp,
            logged=True,
            log_id=log_obj.log_id
        )
        
    except Exception as e:
        logger.error(f"사용자 활동 로그 기록 실패: user_id={current_user.user_id}, action={activity.action}, error={str(e)}")
        # 프론트엔드에서 실패를 무시하므로 에러를 발생시키지 않음
        return UserActivityLogResponse(
            message="활동 로그 기록에 실패했습니다.",
            user_id=current_user.user_id,
            action=activity.action,
            path=activity.path,
            label=activity.label,
            timestamp=activity.timestamp,
            logged=False,
            error=str(e)
        )
