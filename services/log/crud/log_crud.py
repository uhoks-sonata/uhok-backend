"""
PostgreSQL USER_LOG 테이블 CRUD 함수
"""
from sqlalchemy.ext.asyncio import AsyncSession
from services.log.models.log_model import UserLog

async def create_user_log(db: AsyncSession, log_data: dict) -> UserLog:
    """
    사용자 로그 생성(적재)
    - user_id: MariaDB USERS.USER_ID를 그대로 사용
    """
    log = UserLog(**log_data)
    db.add(log)
    await db.commit()
    await db.refresh(log)
    return log
