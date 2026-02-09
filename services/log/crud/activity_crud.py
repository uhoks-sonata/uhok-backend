"""
사용자 활동 로그 CRUD 함수
- 프론트엔드에서 호출하는 사용자 활동 로그 처리
"""

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.log_utils import serialize_datetime
from common.logger import get_logger
from services.log.models.user_log_model import UserLog
from services.log.schemas.activity_schema import UserActivityLog

logger = get_logger("user_activity_log_crud")


async def create_user_activity_log(
    db: AsyncSession,
    user_id: int,
    activity: UserActivityLog,
) -> UserLog:
    """
    사용자 활동 로그 생성
    """

    try:
        event_data = {
            "action": activity.action,
            "timestamp": serialize_datetime(activity.timestamp),
        }

        if activity.path:
            event_data["path"] = activity.path
        if activity.label:
            event_data["label"] = activity.label
        if activity.extra_data:
            event_data.update(serialize_datetime(activity.extra_data))

        event_type = f"user_activity_{activity.action}"

        user_log = UserLog(
            user_id=user_id,
            event_type=event_type,
            event_data=event_data,
        )
        db.add(user_log)
        await db.commit()
        await db.refresh(user_log)
        return user_log

    except Exception as e:
        await db.rollback()
        logger.error(
            f"사용자 활동 로그 생성 실패: user_id={user_id}, action={activity.action}, error={str(e)}"
        )
        raise


async def get_user_activity_logs(
    db: AsyncSession,
    user_id: int,
    action: Optional[str] = None,
    limit: int = 100,
) -> list[UserLog]:
    """
    사용자 활동 로그 조회
    """

    try:
        query = select(UserLog).where(UserLog.user_id == user_id)

        if action:
            query = query.where(UserLog.event_type.like(f"user_activity_{action}%"))

        query = query.order_by(UserLog.created_at.desc()).limit(limit)

        result = await db.execute(query)
        logs = result.scalars().all()
        return logs

    except Exception as e:
        logger.error(f"사용자 활동 로그 조회 실패: user_id={user_id}, action={action}, error={str(e)}")
        raise
