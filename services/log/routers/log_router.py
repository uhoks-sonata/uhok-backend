"""
로그 적재/조회 API 라우터
- 사용자 로그 기록 및 조회 기능 제공
"""
from fastapi import APIRouter, Depends, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from services.log.schemas.log_schema import UserLogCreate, UserLogRead
from services.log.crud.log_crud import create_user_log, get_user_logs
from common.database.postgres_log import get_postgres_log_db
from common.errors import BadRequestException, InternalServerErrorException
from sqlalchemy.exc import SQLAlchemyError
from typing import List
from common.log_utils import send_user_log

# 로그 관련 API 라우터
# - prefix="/log" : 이 라우터에 포함된 모든 경로 앞에 "/log"가 자동으로 붙는다
#   예) @router.post("/") → POST /log/
# - tags=["log"] : Swagger 문서에서 log 그룹으로 노출
router = APIRouter(
    prefix="/log",   # 이 라우터의 모든 엔드포인트 URL 앞에 "/log"를 자동으로 추가
    tags=["log"]     # API 문서(Swagger)에서 'log' 그룹으로 분류
)


@router.post("/", response_model=UserLogRead, status_code=status.HTTP_201_CREATED)
async def write_log(
    log: UserLogCreate,
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_postgres_log_db)
):
    """
    사용자 로그 적재(비동기)
    - user_id는 MariaDB USERS.USER_ID와 동일하게 받아서 저장
    - event_type, event_data(옵션) 포함
    - 필수 필드 검증 및 DB 예외 처리
    """
    try:
        log_obj = await create_user_log(db, log.model_dump())
        
        # 로그 적재 성공 시 추가 로그 기록
        if background_tasks:
            background_tasks.add_task(
                send_user_log, 
                user_id=log.user_id, 
                event_type="log_write_success", 
                event_data={
                    "log_id": log_obj.id,
                    "event_type": log.event_type,
                    "event_data": log.event_data
                }
            )
        
        return log_obj
    except BadRequestException as e:
        # 파라미터 오류(400)
        raise e
    except InternalServerErrorException as e:
        # 서버 내부 로직 오류(500)
        raise e
    except SQLAlchemyError:
        # DB 예외(500)
        raise InternalServerErrorException("DB 오류로 로그 저장에 실패했습니다.")
    except Exception:
        # 알 수 없는 예외(500)
        raise InternalServerErrorException()

@router.get("/user/{user_id}", response_model=List[UserLogRead])
async def read_user_logs(
    user_id: int,
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_postgres_log_db)
):
    """
    특정 사용자의 최근 로그 조회
    - user_id: MariaDB USERS.USER_ID 기준
    """
    try:
        logs = await get_user_logs(db, user_id)
        
        # 로그 조회 로그 기록
        if background_tasks:
            background_tasks.add_task(
                send_user_log, 
                user_id=user_id, 
                event_type="log_read", 
                event_data={
                    "target_user_id": user_id,
                    "log_count": len(logs)
                }
            )
        
        return logs
    except Exception:
        raise InternalServerErrorException("로그 조회 중 오류가 발생했습니다.")
