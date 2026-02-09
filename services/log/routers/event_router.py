"""
로그 적재/조회 API 라우터
- 사용자 이벤트 로그 기록 및 조회 기능 제공
"""

from typing import List

from fastapi import APIRouter, BackgroundTasks, Depends, Request, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from common.database.postgres_log import get_postgres_log_db
from common.errors import BadRequestException, InternalServerErrorException
from common.log_utils import send_user_log
from common.logger import get_logger
from services.log.crud.event_crud import create_user_log, get_user_logs
from services.log.schemas.event_schema import UserEventLogCreate, UserEventLogRead

logger = get_logger("user_event_log_router")
router = APIRouter(prefix="/api/log/user/event", tags=["UserEventLog"])


@router.get("/health")
async def health_check():
    """
    로그 서비스 헬스체크
    """

    return {
        "status": "healthy",
        "service": "log",
        "message": "로그 서비스가 정상적으로 작동 중입니다.",
    }


@router.get("")
async def log_root():
    """
    로그 서비스 루트 엔드포인트
    - GET /api/log/user/event (슬래시 없음)
    """

    return {
        "status": "available",
        "service": "log",
        "message": "로그 서비스가 사용 가능합니다.",
        "endpoints": {
            "GET /health": "서비스 상태 확인",
            "POST /": "로그 기록",
            "GET /user/{user_id}": "사용자별 로그 조회",
        },
    }


@router.post("", response_model=UserEventLogRead, status_code=status.HTTP_201_CREATED)
async def write_log(
    log: UserEventLogCreate,
    request: Request,
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_postgres_log_db),
):
    """
    사용자 로그 적재(비동기)
    - POST /api/log/user/event (슬래시 없음)
    """

    try:
        log_data = log.model_dump()
        log_obj = await create_user_log(db, log_data)

        if background_tasks and log.event_type != "log_write_success":
            background_tasks.add_task(
                send_user_log,
                user_id=log.user_id,
                event_type="log_write_success",
                event_data={
                    "log_id": log_obj.log_id,
                    "event_type": log.event_type,
                    "event_data": log.event_data,
                },
            )
        return log_obj
    except BadRequestException as e:
        logger.warning(f"사용자 이벤트 로그 기록 실패 (잘못된 요청): user_id={log.user_id}, error={str(e)}")
        raise e
    except InternalServerErrorException as e:
        logger.error(f"사용자 이벤트 로그 기록 실패 (내부 서버 오류): user_id={log.user_id}, error={str(e)}")
        raise e
    except SQLAlchemyError:
        logger.error(f"사용자 이벤트 로그 기록 실패 (DB 오류): user_id={log.user_id}")
        raise InternalServerErrorException("DB 오류로 로그 저장에 실패했습니다.")
    except Exception:
        logger.error(f"사용자 이벤트 로그 기록 실패 (예상치 못한 오류): user_id={log.user_id}")
        raise InternalServerErrorException()


@router.get("/{user_id}", response_model=List[UserEventLogRead])
async def read_user_logs(
    user_id: int,
    request: Request,
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_postgres_log_db),
):
    """
    특정 사용자의 최근 로그 조회
    """

    try:
        logs = await get_user_logs(db, user_id)
        return logs
    except Exception:
        logger.error(f"사용자 이벤트 로그 조회 실패: user_id={user_id}")
        raise InternalServerErrorException("로그 조회 중 오류가 발생했습니다.")
