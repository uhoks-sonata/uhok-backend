"""
사용자 활동 로그 전용 API 라우터
- 프론트엔드에서 호출하는 사용자 활동 로그 처리
"""

from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from common.database.postgres_log import get_postgres_log_db
from common.dependencies import get_current_user
from common.logger import get_logger
from services.log.crud.activity_crud import create_user_activity_log
from services.log.schemas.activity_schema import UserActivityLog, UserActivityLogResponse
from services.user.schemas.profile_schema import UserOut

logger = get_logger("user_activity_log_router")
router = APIRouter(prefix="/api/log/user/activity", tags=["UserActivityLog"])


@router.post("", response_model=UserActivityLogResponse, status_code=status.HTTP_201_CREATED)
async def log_user_activity(
    activity: UserActivityLog,
    current_user: UserOut = Depends(get_current_user),
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_postgres_log_db),
):
    """
    사용자 활동 로그 기록 API
    - 인증된 사용자의 활동을 로그 서비스에 직접 기록
    - 프론트엔드에서 호출하는 활동 로그 처리
    """

    try:
        if not activity.user_id:
            activity.user_id = current_user.user_id
        if not activity.user_email:
            activity.user_email = current_user.email
        if not activity.user_username:
            activity.user_username = current_user.username

        if not activity.timestamp:
            activity.timestamp = datetime.utcnow().isoformat() + "Z"

        log_obj = await create_user_activity_log(
            db=db,
            user_id=current_user.user_id,
            activity=activity,
        )

        return UserActivityLogResponse(
            message="활동 로그가 성공적으로 기록되었습니다.",
            user_id=current_user.user_id,
            action=activity.action,
            path=activity.path,
            label=activity.label,
            timestamp=activity.timestamp,
            logged=True,
            log_id=log_obj.log_id,
        )

    except Exception as e:
        logger.error(
            f"사용자 활동 로그 기록 실패: user_id={current_user.user_id}, action={activity.action}, error={str(e)}"
        )
        return UserActivityLogResponse(
            message="활동 로그 기록에 실패했습니다.",
            user_id=current_user.user_id,
            action=activity.action,
            path=activity.path,
            label=activity.label,
            timestamp=activity.timestamp,
            logged=False,
            error=str(e),
        )
