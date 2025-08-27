"""
사용자 활동 로그 CRUD 함수
- 프론트엔드에서 호출하는 사용자 활동 로그 처리
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional

from services.log.models.log_model import UserLog
from services.log.schemas.user_activity_schema import UserActivityLog

from common.logger import get_logger
logger = get_logger("user_behavior_log_crud")


async def create_user_activity_log(
    db: AsyncSession,
    user_id: int,
    activity: UserActivityLog
) -> UserLog:
    """
    사용자 활동 로그 생성
    
    Args:
        db: 데이터베이스 세션
        user_id: 사용자 ID
        activity: 사용자 활동 데이터
    
    Returns:
        생성된 UserLog 객체
    """
    try:
        # 이벤트 데이터 구성
        event_data = {
            "action": activity.action,
            "timestamp": activity.timestamp
        }
        
        # 추가 데이터가 있으면 포함
        if activity.path:
            event_data["path"] = activity.path
        if activity.label:
            event_data["label"] = activity.label
        if activity.extra_data:
            event_data.update(activity.extra_data)
        
        # 이벤트 타입 생성
        event_type = f"user_activity_{activity.action}"
        
        # UserLog 모델에 맞는 데이터 생성
        log_data = {
            "user_id": user_id,
            "event_type": event_type,
            "event_data": event_data
        }
        
        # UserLog 객체 생성
        user_log = UserLog(**log_data)
        db.add(user_log)
        await db.commit()
        await db.refresh(user_log)
        
        logger.info(f"사용자 활동 로그 생성 성공: user_id={user_id}, action={activity.action}, log_id={user_log.log_id}")
        return user_log
        
    except Exception as e:
        await db.rollback()
        logger.error(f"사용자 활동 로그 생성 실패: user_id={user_id}, action={activity.action}, error={str(e)}")
        raise


async def get_user_activity_logs(
    db: AsyncSession,
    user_id: int,
    action: Optional[str] = None,
    limit: int = 100
) -> list[UserLog]:
    """
    사용자 활동 로그 조회
    
    Args:
        db: 데이터베이스 세션
        user_id: 사용자 ID
        action: 특정 활동 유형 (선택사항)
        limit: 조회할 로그 개수
    
    Returns:
        사용자 활동 로그 목록
    """
    try:
        query = select(UserLog).where(UserLog.user_id == user_id)
        
        if action:
            query = query.where(UserLog.event_type.like(f"user_activity_{action}%"))
        
        query = query.order_by(UserLog.created_at.desc()).limit(limit)
        
        result = await db.execute(query)
        logs = result.scalars().all()
        
        logger.info(f"사용자 활동 로그 조회 성공: user_id={user_id}, action={action}, count={len(logs)}")
        return logs
        
    except Exception as e:
        logger.error(f"사용자 활동 로그 조회 실패: user_id={user_id}, action={action}, error={str(e)}")
        raise
