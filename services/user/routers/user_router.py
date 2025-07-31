"""
User API 엔드포인트 (회원가입, 로그인)
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from common.errors import BadRequestException, ConflictException, NotAuthenticatedException
from services.user.schemas.user_schema import UserCreate, UserLogin, UserOut
from services.user.crud.user_crud import get_user_by_email, create_user, verify_password
from services.user.database import get_db
from common.auth.jwt_handler import create_access_token

router = APIRouter(prefix="/api/user", tags=["user"])

@router.post("/signup", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def signup(user: UserCreate, db: Session = Depends(get_db)):
    """
        회원가입 API
        - 이메일 중복 체크
        - 비밀번호, 비밀번호 확인 일치 검사
        - 신규 User row 및 UserSetting row 생성
    """
    if user.password != user.password_confirm:
        raise BadRequestException("비밀번호와 비밀번호 확인이 일치하지 않습니다.")
    if get_user_by_email(db, str(user.email)):
        raise ConflictException("이미 가입된 이메일입니다.")
    new_user = create_user(db, str(user.email), user.password, user.username)
    return new_user

@router.post("/login")
def login(user: UserLogin, db: Session = Depends(get_db)):
    """
        로그인 API
        - 이메일/비밀번호 검증
        - JWT 액세스 토큰 발급
    """
    db_user = get_user_by_email(db, str(user.email))
    if not db_user or not verify_password(user.password, db_user.password_hash):
        raise NotAuthenticatedException()
    # JWT payload의 sub에 user_id를 사용 (best practice)
    access_token = create_access_token({"sub": db_user.user_id})
    return {"access_token": access_token, "token_type": "bearer"}
