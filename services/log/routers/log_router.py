"""
로그 적재 API (FastAPI 라우터)
- user_id는 반드시 MariaDB USERS.USER_ID를 받아와서 적재
- FastAPI + SQLAlchemy 비동기 처리
- 컬럼/테이블명 대문자, ORM 변수 소문자
- 추후 Kafka나 외부 이벤트 큐로 확장하기 쉽도록 설계
"""
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from services.log.schemas.log_schema import UserLogCreate, UserLogRead
from services.log.crud.log_crud import create_user_log
from common.database.postgres_log import get_postgres_log_db

router = APIRouter(prefix="/log", tags=["Log"])

@router.post("/", response_model=UserLogRead, status_code=status.HTTP_201_CREATED)
async def write_log(
    log: UserLogCreate,
    db: AsyncSession = Depends(get_postgres_log_db)
):
    """
    사용자 로그 적재(비동기)
    - user_id는 MariaDB USERS.USER_ID와 동일하게 받아서 저장
    """
    log_obj = await create_user_log(db, log.model_dump())
    return log_obj
