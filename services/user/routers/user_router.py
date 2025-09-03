"""
User API 엔드포인트 (회원가입, 로그인) - 비동기 패턴
"""

from fastapi import APIRouter, Depends, status, Query, BackgroundTasks, Request
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from common.dependencies import get_current_user
from common.auth.jwt_handler import create_access_token, get_token_expiration, extract_user_id_from_token
from common.database.mariadb_auth import get_maria_auth_db
from common.errors import ConflictException, NotAuthenticatedException, InvalidTokenException
from common.log_utils import send_user_log
from common.http_dependencies import extract_http_info
from common.logger import get_logger

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


router = APIRouter(prefix="/api/user", tags=["User"])
logger = get_logger("user_router")

@router.post("/signup", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def signup(
    user: UserCreate,
    background_tasks: BackgroundTasks,
    request: Request,
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
            logger.warning(f"중복 이메일로 회원가입 시도: {user.email}")
            raise ConflictException("이미 가입된 이메일입니다.")
        
        new_user = await create_user(db, str(user.email), user.password, user.username)
        logger.info(f"새 사용자 등록 성공: user_id={new_user.user_id}, email={user.email}")
        
        # 회원가입 로그 기록
        if background_tasks:
            http_info = extract_http_info(request, response_code=201)
            background_tasks.add_task(
                send_user_log,
                user_id=new_user.user_id,
                event_type="user_signup",
                event_data={
                    "email": user.email,
                    "username": user.username
                },
                **http_info  # HTTP 정보를 키워드 인자로 전달
            )
        
        return new_user
    except Exception as e:
        logger.error(f"회원가입 실패, email={user.email}: {str(e)}")
        raise


@router.get("/signup/email/check", response_model=EmailDuplicateCheckResponse)
async def check_email_duplicate(
    request: Request,
    email: EmailStr = Query(..., description="중복 확인할 이메일"),
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_maria_auth_db)
):
    """
    회원가입 - 이메일 중복 여부 확인 API (비동기)
    """
    try:
        is_dup = await get_user_by_email(db, str(email)) is not None
        msg = "이미 존재하는 아이디입니다." if is_dup else "사용 가능한 아이디입니다."
        logger.debug(f"이메일 중복 확인: {email} - 중복여부={is_dup}")
        
        # 이메일 중복 확인 로그 기록 (익명 사용자)
        if background_tasks:
            http_info = extract_http_info(request, response_code=200)
            background_tasks.add_task(
                send_user_log,
                user_id=0,  # 익명 사용자
                event_type="user_email_duplicate_check",
                event_data={
                    "email": email,
                    "is_duplicate": is_dup
                },
                **http_info  # HTTP 정보를 키워드 인자로 전달
            )
        
        return EmailDuplicateCheckResponse(email=email, is_duplicate=is_dup, message=msg)
    except Exception as e:
        logger.error(f"이메일 중복 확인 실패, email={email}: {str(e)}")
        raise


@router.post("/login")
async def login(
    request: Request,
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
        
        logger.info(f"로그인 요청 시작: email={email}")
        logger.debug(f"로그인 요청 데이터: username={form_data.username}, password_length={len(password) if password else 0}")
        
        # 이메일 유효성 검사
        if not email:
            logger.warning("로그인 실패: 이메일이 비어있음")
            raise NotAuthenticatedException("이메일을 입력해주세요.")
        
        if not password:
            logger.warning("로그인 실패: 비밀번호가 비어있음")
            raise NotAuthenticatedException("비밀번호를 입력해주세요.")

        db_user = await get_user_by_email(db, email)
        if not db_user:
            logger.warning(f"로그인 실패: 존재하지 않는 이메일, email={email}")
            raise NotAuthenticatedException("이메일 또는 비밀번호가 올바르지 않습니다.")
        
        if not verify_password(password, db_user.password_hash):
            logger.warning(f"로그인 실패: 비밀번호 불일치, email={email}")
            raise NotAuthenticatedException("이메일 또는 비밀번호가 올바르지 않습니다.")

        access_token = create_access_token({"sub": str(db_user.user_id)})
        logger.info(f"사용자 로그인 성공: user_id={db_user.user_id}, email={email}")
        
        # 로그인 로그 기록
        if background_tasks:
            http_info = extract_http_info(request, response_code=200)
            background_tasks.add_task(
                send_user_log,
                user_id=db_user.user_id,
                event_type="user_login",
                event_data={
                    "email": email,
                    "username": db_user.username
                },
                **http_info  # HTTP 정보를 키워드 인자로 전달
            )
        
        return {"access_token": access_token, "token_type": "bearer"}
    except NotAuthenticatedException:
        # 이미 로깅된 경우 재로깅하지 않음
        raise
    except Exception as e:
        logger.error(f"로그인 중 예상치 못한 오류, email={email}: {str(e)}")
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
    try:
        logger.info(f"로그아웃 요청 시작: user_id={current_user.user_id}, email={current_user.email}")
        
        # Authorization 헤더에서 토큰 추출
        authorization = request.headers.get("authorization")
        logger.debug(f"Authorization 헤더 확인: {authorization[:20] if authorization else 'None'}...")
        
        if not authorization or not authorization.startswith("Bearer "):
            logger.warning(f"유효하지 않은 Authorization 헤더: {authorization}")
            raise InvalidTokenException("유효한 Authorization 헤더가 필요합니다.")
        
        token = authorization.replace("Bearer ", "")
        logger.debug(f"토큰 추출 완료: {token[:20]}...")
        
        # 토큰에서 사용자 ID와 만료 시간 추출
        user_id = extract_user_id_from_token(token)
        expires_at = get_token_expiration(token)
        
        logger.debug(f"토큰 정보 추출: user_id={user_id}, expires_at={expires_at}")
        
        if not user_id or not expires_at:
            logger.error(f"토큰 정보 추출 실패: user_id={user_id}, expires_at={expires_at}")
            raise InvalidTokenException("유효하지 않은 토큰입니다.")
        
        # 토큰을 블랙리스트에 추가
        logger.info(f"토큰을 블랙리스트에 추가 중: user_id={user_id}")
        await add_token_to_blacklist(
            db=db,
            token=token,
            expires_at=expires_at,
            user_id=user_id,
            metadata="user_logout"
        )
        logger.info(f"토큰 블랙리스트 추가 성공: user_id={user_id}")
        
        # 로그아웃 로그 기록
        if background_tasks:
            http_info = extract_http_info(request, response_code=200)
            background_tasks.add_task(
                send_user_log,
                user_id=user_id,
                event_type="user_logout",
                event_data={
                    "email": current_user.email,
                    "username": current_user.username
                },
                **http_info  # HTTP 정보를 키워드 인자로 전달
            )
        
        return {"message": "로그아웃이 완료되었습니다."}
        
    except InvalidTokenException as e:
        logger.error(f"로그아웃 실패 (토큰 오류): user_id={current_user.user_id}, error={str(e)}")
        raise
    except Exception as e:
        logger.error(f"로그아웃 중 예상치 못한 오류: user_id={current_user.user_id}, error={str(e)}")
        raise

    
@router.get("/info", response_model=UserOut, status_code=status.HTTP_200_OK)
async def get_user_info(
    request: Request,
    current_user: UserOut = Depends(get_current_user),
    background_tasks: BackgroundTasks = None
):
    """
    로그인한 사용자의 기본 정보를 반환합니다.
    - JWT 토큰 인증 필요 (헤더: Authorization: Bearer <token>)
    - 응답: user_id, username, email
    """
    # 사용자 정보 조회 로그 기록
    if background_tasks:
        http_info = extract_http_info(request, response_code=200)
        background_tasks.add_task(
            send_user_log,
            user_id=current_user.user_id,
            event_type="user_info_view",
            event_data={
                "email": current_user.email,
                "username": current_user.username
            },
            **http_info  # HTTP 정보를 키워드 인자로 전달
        )
    
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
