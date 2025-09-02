"""
로그 적재/조회 API 라우터
- 사용자 로그 기록 및 조회 기능 제공
- HTTP 요청 정보 수집 (메서드, URL, IP, 응답시간 등)
"""
from fastapi import APIRouter, Depends, status, BackgroundTasks, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
from typing import List
from datetime import datetime
import time

from common.database.postgres_log import get_postgres_log_db
from common.errors import BadRequestException, InternalServerErrorException
from common.log_utils import send_user_log
from common.logger import get_logger

from services.log.schemas.user_event_log_schema import UserEventLogCreate, UserEventLogRead
from services.log.crud.user_event_log_crud import create_user_log, get_user_logs

logger = get_logger("user_event_log_router")
router = APIRouter(prefix="/api/log/user/event", tags=["UserEventLog"])


def get_client_ip(request: Request) -> str:
    """
    클라이언트 IP 주소 추출
    - X-Forwarded-For 헤더 우선 확인 (프록시 환경)
    - X-Real-IP 헤더 확인
    - 직접 연결 IP 확인
    """
    # 프록시를 통한 요청인 경우
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # X-Forwarded-For는 쉼표로 구분된 IP 목록일 수 있음
        return forwarded_for.split(",")[0].strip()
    
    # X-Real-IP 헤더 확인
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    
    # 직접 연결 IP
    return request.client.host if request.client else "unknown"

def extract_http_info(request: Request, start_time: float) -> dict:
    """
    HTTP 요청 정보 추출
    """
    return {
        "http_method": request.method,
        "api_url": str(request.url),
        "request_time": datetime.fromtimestamp(start_time),
        "response_time": datetime.now(),
        "client_ip": get_client_ip(request)
    }

@router.get("/health")
async def health_check():
    """
    로그 서비스 헬스체크
    """
    return {
        "status": "healthy",
        "service": "log",
        "message": "로그 서비스가 정상적으로 작동 중입니다."
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
            "GET /user/{user_id}": "사용자별 로그 조회"
        }
    }

@router.post("", response_model=UserEventLogRead, status_code=status.HTTP_201_CREATED)
async def write_log(
        request: Request,
        log: UserEventLogCreate,
        background_tasks: BackgroundTasks = None,
        db: AsyncSession = Depends(get_postgres_log_db)
):
    """
    사용자 로그 적재(비동기)
    - POST /api/log/user/event (슬래시 없음)
    - HTTP 요청 정보 자동 수집
    """
    start_time = time.time()
    response_code = status.HTTP_201_CREATED
    
    try:
        # HTTP 정보 추출
        http_info = extract_http_info(request, start_time)
        
        # 로그 데이터에 HTTP 정보 추가
        log_data = log.model_dump()
        log_data.update(http_info)
        
        # logger.info(f"사용자 이벤트 로그 기록 시작: user_id={log.user_id}, event_type={log.event_type}")
        log_obj = await create_user_log(db, log_data)

        # log_write_success 이벤트일 때는 또 기록하지 않도록 방지!
        if background_tasks and log.event_type != "log_write_success":
            background_tasks.add_task(
                send_user_log,
                user_id=log.user_id,
                event_type="log_write_success",
                event_data={
                    "log_id": log_obj.log_id,
                    "event_type": log.event_type,
                    "event_data": log.event_data,
                    "http_method": http_info["http_method"],
                    "api_url": http_info["api_url"],
                    "response_code": response_code
                }
            )
        # logger.info(f"사용자 이벤트 로그 기록 성공: user_id={log.user_id}, event_type={log.event_type}, log_id={log_obj.log_id}")
        return log_obj
    except BadRequestException as e:
        response_code = status.HTTP_400_BAD_REQUEST
        logger.warning(f"사용자 이벤트 로그 기록 실패 (잘못된 요청): user_id={log.user_id}, error={str(e)}")
        raise e
    except InternalServerErrorException as e:
        response_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        logger.error(f"사용자 이벤트 로그 기록 실패 (내부 서버 오류): user_id={log.user_id}, error={str(e)}")
        raise e
    except SQLAlchemyError:
        response_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        logger.error(f"사용자 이벤트 로그 기록 실패 (DB 오류): user_id={log.user_id}")
        raise InternalServerErrorException("DB 오류로 로그 저장에 실패했습니다.")
    except Exception:
        response_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        logger.error(f"사용자 이벤트 로그 기록 실패 (예상치 못한 오류): user_id={log.user_id}")
        raise InternalServerErrorException()

@router.get("/{user_id}", response_model=List[UserEventLogRead])
async def read_user_logs(
        request: Request,
        user_id: int,
        background_tasks: BackgroundTasks = None,
        db: AsyncSession = Depends(get_postgres_log_db)
):
    """
    특정 사용자의 최근 로그 조회
    - HTTP 요청 정보 자동 수집
    """
    start_time = time.time()
    response_code = status.HTTP_200_OK
    
    try:
        # HTTP 정보 추출
        http_info = extract_http_info(request, start_time)
        
        # logger.info(f"사용자 이벤트 로그 조회 시작: user_id={user_id}")
        logs = await get_user_logs(db, user_id)

        if background_tasks:
            background_tasks.add_task(
                send_user_log,
                user_id=user_id,
                event_type="log_read",
                event_data={
                    "target_user_id": user_id,
                    "log_count": len(logs),
                    "http_method": http_info["http_method"],
                    "api_url": http_info["api_url"],
                    "response_code": response_code
                }
            )
        # logger.info(f"사용자 이벤트 로그 조회 성공: user_id={user_id}, count={len(logs)}")
        return logs
    except Exception:
        response_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        logger.error(f"사용자 이벤트 로그 조회 실패: user_id={user_id}")
        raise InternalServerErrorException("로그 조회 중 오류가 발생했습니다.")
