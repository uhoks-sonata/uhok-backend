"""
User API 엔드포인트 (회원가입, 로그인) - 비동기 패턴
"""

from fastapi import APIRouter, Depends, status, Query, BackgroundTasks, Request
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

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
from services.user.crud.jwt_blacklist_crud import add_token_to_blacklist

from common.database.mariadb_auth import get_maria_auth_db
from common.errors import ConflictException, NotAuthenticatedException, InvalidTokenException
from common.auth.jwt_handler import create_access_token, get_token_expiration, extract_user_id_from_token
from common.dependencies import get_current_user
from common.log_utils import send_user_log
from common.logger import get_logger

router = APIRouter(prefix="/api/user", tags=["user"])
logger = get_logger("user_router")


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
    try:
        exist_user = await get_user_by_email(db, str(user.email))
        if exist_user:
            logger.warning(f"Signup attempt with duplicate email: {user.email}")
            raise ConflictException("이미 가입된 이메일입니다.")
        
        new_user = await create_user(db, str(user.email), user.password, user.username)
        logger.info(f"New user registered successfully: user_id={new_user.user_id}, email={user.email}")
        
        # 회원가입 로그 기록
        background_tasks.add_task(
            send_user_log, 
            user_id=new_user.user_id, 
            event_type="user_signup", 
            event_data={"email": str(user.email), "username": user.username}
        )
        
        return new_user
    except Exception as e:
        logger.error(f"Signup failed for email {user.email}: {str(e)}")
        raise


@router.get("/signup/email/check", response_model=EmailDuplicateCheckResponse)
async def check_email_duplicate(
    email: EmailStr = Query(..., description="중복 확인할 이메일"),
    db: AsyncSession = Depends(get_maria_auth_db)
):
    """
    회원가입 - 이메일 중복 여부 확인 API (비동기)
    """
    try:
        is_dup = await get_user_by_email(db, str(email)) is not None
        msg = "이미 존재하는 아이디입니다." if is_dup else "사용 가능한 아이디입니다."
        logger.debug(f"Email duplicate check: {email} - is_duplicate={is_dup}")
        return EmailDuplicateCheckResponse(email=email, is_duplicate=is_dup, message=msg)
    except Exception as e:
        logger.error(f"Email duplicate check failed for {email}: {str(e)}")
        raise


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
    try:
        email = form_data.username  # Swagger의 username 필드에 email 입력!
        password = form_data.password

        db_user = await get_user_by_email(db, email)
        if not db_user or not verify_password(password, db_user.password_hash):
            logger.warning(f"Login failed for email: {email}")
            raise NotAuthenticatedException()

        access_token = create_access_token({"sub": str(db_user.user_id)})
        logger.info(f"User logged in successfully: user_id={db_user.user_id}, email={email}")
        
        # 로그인 로그 기록
        if background_tasks:
            background_tasks.add_task(
                send_user_log, 
                user_id=db_user.user_id, 
                event_type="user_login", 
                event_data={"email": email}
            )
        
        return {"access_token": access_token, "token_type": "bearer"}
    except Exception as e:
        logger.error(f"Login failed for email {email}: {str(e)}")
        raise


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(
    request: Request,
    current_user: UserOut = Depends(get_current_user),
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_maria_auth_db)
):
    """
    로그아웃 API
    - JWT 토큰을 블랙리스트에 추가하여 재사용을 방지
    - get_current_user 의존성을 통해 토큰 검증
    """
    # Authorization 헤더에서 토큰 추출
    authorization = request.headers.get("authorization")
    if not authorization or not authorization.startswith("Bearer "):
        raise InvalidTokenException("유효한 Authorization 헤더가 필요합니다.")
    
    token = authorization.replace("Bearer ", "")
    
    # 토큰에서 만료 시간 추출
    expires_at = get_token_expiration(token)
    if not expires_at:
        raise InvalidTokenException("유효하지 않은 토큰입니다.")
    
    # 토큰을 블랙리스트에 추가
    await add_token_to_blacklist(
        db=db,
        token=token,
        expires_at=expires_at,
        user_id=current_user.user_id,
        metadata="user_logout"
    )
    
    # 로그아웃 로그 기록
    if background_tasks:
        background_tasks.add_task(
            send_user_log, 
            user_id=current_user.user_id, 
            event_type="user_logout", 
            event_data={"logout_method": "api_call"}
        )
    
    return {"message": "로그아웃이 완료되었습니다."}

    
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


# @router.post("/logout/all", status_code=status.HTTP_200_OK)
# async def logout_all_devices(
#     current_user: UserOut = Depends(get_current_user),
#     background_tasks: BackgroundTasks = None,
#     db: AsyncSession = Depends(get_maria_auth_db)
# ):
#     """
#     모든 디바이스에서 로그아웃 API
#     - 현재 사용자의 모든 활성 토큰을 블랙리스트에 추가
#     - 주의: 이 기능은 구현이 복잡하므로 향후 확장 예정
#     """
#     # 현재는 단순한 메시지만 반환
#     # 향후 사용자별 토큰 관리 시스템 구현 시 확장 가능
#     
#     # 로그아웃 로그 기록
#     if background_tasks:
#         background_tasks.add_task(
#             send_user_log, 
#             user_id=current_user.user_id, 
#             event_type="user_logout_all_devices", 
#             event_data={"logout_method": "api_call"}
#         )
#     
#     return {"message": "모든 디바이스에서 로그아웃 요청이 완료되었습니다. (기능 개발 중)"}


# @router.get("/admin/blacklist/stats", status_code=status.HTTP_200_OK)
# async def get_blacklist_stats(
#     current_user: UserOut = Depends(get_current_user),
#     db: AsyncSession = Depends(get_maria_auth_db)
# ):
#     """
#     블랙리스트 통계 정보 조회 API (관리자용)
#     - 현재 사용자가 관리자인지 확인 필요 (향후 권한 시스템 구현 시 확장)
#     """
#     from services.user.crud.jwt_blacklist_crud import get_blacklist_stats
#     
#     stats = await get_blacklist_stats(db)
#     return stats


# @router.post("/admin/blacklist/cleanup", status_code=status.HTTP_200_OK)
# async def cleanup_expired_tokens(
#     current_user: UserOut = Depends(get_current_user),
#     db: AsyncSession = Depends(get_maria_auth_db)
# ):
#     """
#     만료된 토큰들을 블랙리스트에서 정리하는 API (관리자용)
#     - 현재 사용자가 관리자인지 확인 필요 (향후 권한 시스템 구현 시 확장)
#     """
#     from services.user.crud.jwt_blacklist_crud import cleanup_expired_tokens
#     
#     cleaned_count = await cleanup_expired_tokens(db)
#     return {"message": f"{cleaned_count}개의 만료된 토큰이 정리되었습니다."}
