"""
User API 엔드포인트 (회원가입, 로그인) - 비동기 패턴
"""

from fastapi import APIRouter, Depends, status, Query, BackgroundTasks
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from services.user.schemas.user_schema import (
    UserCreate,
    UserOut,
    EmailDuplicateCheckResponse
)
from services.user.crud.user_crud import (
    get_user_by_email,
    create_user,
    verify_password
)

from common.database.mariadb_auth import get_maria_auth_db
from common.errors import ConflictException, NotAuthenticatedException
from common.auth.jwt_handler import create_access_token
from common.dependencies import get_current_user
from common.log_utils import send_user_log

router = APIRouter(prefix="/api/user", tags=["user"])


@router.post("/signup", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def signup(
    user: UserCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_maria_auth_db)
):
    """
    회원가입 API (비동기)
    - 이메일 중복 체크
    - 신규 User row 및 UserSetting row 생성
    """
    exist_user = await get_user_by_email(db, str(user.email))
    if exist_user:
        raise ConflictException("이미 가입된 이메일입니다.")
    new_user = await create_user(db, str(user.email), user.password, user.username)
    
    # 회원가입 로그 기록
    background_tasks.add_task(
        send_user_log, 
        user_id=new_user.user_id, 
        event_type="user_signup", 
        event_data={"email": str(user.email), "username": user.username}
    )
    
    return new_user


@router.get("/signup/email/check", response_model=EmailDuplicateCheckResponse)
async def check_email_duplicate(
    email: EmailStr = Query(..., description="중복 확인할 이메일"),
    db: AsyncSession = Depends(get_maria_auth_db)
):
    """
    회원가입 - 이메일 중복 여부 확인 API (비동기)
    """
    is_dup = await get_user_by_email(db, str(email)) is not None
    msg = "이미 존재하는 아이디입니다." if is_dup else "사용 가능한 아이디입니다."
    return EmailDuplicateCheckResponse(email=email, is_duplicate=is_dup, message=msg)


@router.post("/login")
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_maria_auth_db)
):
    """
    로그인 API (Swagger Authorize 연동)
    - username 필드에 email 입력!
    - JWT 액세스 토큰 발급
    """
    email = form_data.username  # Swagger의 username 필드에 email 입력!
    password = form_data.password

    db_user = await get_user_by_email(db, email)
    if not db_user or not verify_password(password, db_user.password_hash):
        raise NotAuthenticatedException()

    access_token = create_access_token({"sub": str(db_user.user_id)})
    
    # 로그인 로그 기록
    if background_tasks:
        background_tasks.add_task(
            send_user_log, 
            user_id=db_user.user_id, 
            event_type="user_login", 
            event_data={"email": email}
        )
    
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/info", response_model=UserOut, status_code=status.HTTP_200_OK)
async def get_user_info(
    current_user: UserOut = Depends(get_current_user)
):
    """
    로그인한 사용자의 기본 정보를 반환합니다.
    - JWT 토큰 인증 필요 (헤더: Authorization: Bearer <token>)
    - 응답: user_id, username, email
    """
    return current_user
