"""
사용자 활동 로그 전용 API 라우터
- 프론트엔드에서 호출하는 사용자 활동 로그 처리
"""
from fastapi import APIRouter, Depends, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any

from services.log.schemas.user_activity_schema import UserActivityLog
from services.log.crud.user_activity_crud import create_user_activity_log
from common.database.postgres_log import get_postgres_log_db
from common.dependencies import get_current_user
from services.user.schemas.user_schema import UserOut
from common.logger import get_logger

router = APIRouter(
    prefix="/user-activity",
    tags=["user-activity"]
)

logger = get_logger("user_activity_router")


@router.post("/", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
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
    """
    try:
        logger.info(f"사용자 활동 로그 기록: user_id={current_user.user_id}, action={activity.action}")
        
        # 사용자 활동 로그 생성
        log_obj = await create_user_activity_log(
            db=db,
            user_id=current_user.user_id,
            activity=activity
        )
        
        return {
            "message": "활동 로그가 기록되었습니다.",
            "user_id": current_user.user_id,
            "action": activity.action,
            "timestamp": activity.timestamp,
            "logged": True,
            "log_id": log_obj.log_id
        }
    except Exception as e:
        logger.error(f"사용자 활동 로그 기록 실패: user_id={current_user.user_id}, error={str(e)}")
        # 프론트엔드에서 실패를 무시하므로 에러를 발생시키지 않음
        return {
            "message": "활동 로그 기록에 실패했습니다.",
            "user_id": current_user.user_id,
            "action": activity.action,
            "logged": False,
            "error": str(e)
        }
