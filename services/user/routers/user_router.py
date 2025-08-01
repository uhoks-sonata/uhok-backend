"""
User API 엔드포인트 (회원가입, 로그인) - 비동기 패턴
"""

from fastapi import APIRouter, Depends, status, Query, Request
from pydantic import EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from common.errors import BadRequestException, ConflictException, NotAuthenticatedException
from services.user.schemas.user_schema import UserCreate, UserLogin, UserOut, EmailDuplicateCheckResponse
from services.user.crud.user_crud import get_user_by_email, create_user, verify_password
from services.user.database import get_db
from common.auth.jwt_handler import create_access_token

router = APIRouter(prefix="/api/user", tags=["user"])

@router.post("/signup", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def signup(user: UserCreate, db: AsyncSession = Depends(get_db)):
    """
    회원가입 API (비동기)
    - 이메일 중복 체크
    - 신규 User row 및 UserSetting row 생성
    """
    exist_user = await get_user_by_email(db, str(user.email))
    if exist_user:
        raise ConflictException("이미 가입된 이메일입니다.")
    new_user = await create_user(db, str(user.email), user.password, user.username)
    return new_user

@router.get("/signup/email/check", response_model=EmailDuplicateCheckResponse)
async def check_email_duplicate(
    email: EmailStr = Query(..., description="중복 확인할 이메일"),
    db: AsyncSession = Depends(get_db)
):
    """
    회원가입 - 이메일 중복 여부 확인 API (비동기)
    """
    is_dup = await get_user_by_email(db, str(email)) is not None
    msg = "이미 존재하는 아이디입니다." if is_dup else "사용 가능한 아이디입니다."
    return EmailDuplicateCheckResponse(email=email, is_duplicate=is_dup, message=msg)

@router.post("/login")
async def login(user: UserLogin, db: AsyncSession = Depends(get_db)):
    """
    로그인 API (비동기)
    - 이메일/비밀번호 검증
    - JWT 액세스 토큰 발급
    """
    db_user = await get_user_by_email(db, str(user.email))
    if not db_user or not verify_password(user.password, db_user.password_hash):
        raise NotAuthenticatedException()
    # JWT payload의 sub에 user_id를 사용 (best practice)
    access_token = create_access_token({"sub": db_user.user_id})
    return {"access_token": access_token, "token_type": "bearer"}
