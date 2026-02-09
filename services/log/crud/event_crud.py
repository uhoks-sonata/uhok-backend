"""
USER_LOG 사용자 이벤트 로그 CRUD 함수
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.errors import BadRequestException, InternalServerErrorException
from common.log_utils import serialize_datetime
from common.logger import get_logger
from services.log.models.user_log_model import UserLog

logger = get_logger("user_event_log_crud")


async def create_user_log(db: AsyncSession, log_data: dict) -> UserLog:
    """
    사용자 로그 생성(적재)
    - user_id: MariaDB USERS.USER_ID를 그대로 사용
    - 필수값 및 타입 검증
    - created_at은 DB에서 자동 생성(NOW())
    """

    user_id = log_data.get("user_id")
    if user_id is None:
        raise BadRequestException("user_id가 누락되었습니다.")
    if not isinstance(user_id, int) or user_id < 0:
        raise BadRequestException("user_id는 0 이상의 정수여야 합니다.")

    # user_id=0은 익명 사용자를 의미하므로 허용
    if user_id == 0:
        logger.debug("익명 사용자 로그 기록: user_id=0")
    if not log_data.get("event_type"):
        raise BadRequestException("event_type이 누락되었습니다.")

    # created_at이 log_data에 들어가 있으면 제외
    log_data = dict(log_data)
    log_data.pop("created_at", None)

    data = {
        "user_id": log_data["user_id"],
        "event_type": log_data["event_type"],
    }
    if "event_data" in log_data and log_data["event_data"] is not None:
        data["event_data"] = serialize_datetime(log_data["event_data"])

    http_fields = ["http_method", "api_url", "request_time", "response_time", "response_code", "client_ip"]
    for field in http_fields:
        if field in log_data:
            if field in ["request_time", "response_time"] and log_data[field] is not None:
                data[field] = serialize_datetime(log_data[field])
            else:
                data[field] = log_data[field]

    try:
        log = UserLog(**data)
        db.add(log)
        await db.commit()
        await db.refresh(log)
        return log
    except Exception as e:
        logger.error(f"사용자 로그 생성 실패: {e}")
        raise InternalServerErrorException("로그 저장 중 서버 오류가 발생했습니다.")


async def get_user_logs(db: AsyncSession, user_id: int, limit: int = 50):
    """
    특정 유저의 최근 로그 리스트 조회
    - user_id: MariaDB USERS.USER_ID 기준
    - 최신순, 최대 50개까지 반환
    """

    try:
        result = await db.execute(
            select(UserLog)
            .where(UserLog.user_id == user_id)  # type: ignore
            .order_by(UserLog.created_at.desc())
            .limit(limit)
        )
        logs = result.scalars().all()
        return logs
    except Exception as e:
        logger.error(f"사용자 로그 조회 실패: user_id={user_id}, error={str(e)}")
        raise InternalServerErrorException("로그 조회 중 서버 오류가 발생했습니다.")
