from fastapi import APIRouter, Depends, Query
from pydantic import EmailStr, ValidationError
from sqlalchemy.orm import Session
from services.user.database import get_db
from services.user.schemas import user_schema
from services.user.crud import user_crud
from common.auth.jwt_handler import create_access_token
from common.dependencies import get_current_user
from common.errors import BadRequestException

router = APIRouter(prefix="/api/user", tags=["User"])

@router.post("/signup", response_model=user_schema.UserRead)
def signup(user: user_schema.UserCreate, db: Session = Depends(get_db)):
    return user_crud.create_user(db, user)

@router.get("/signup/email/check")
def check_email_duplicate(email: str = Query(..., description="중복 확인할 이메일"), db: Session = Depends(get_db)):
    try:
        validated_email = EmailStr(email)
    except ValidationError:
        raise BadRequestException("유효한 이메일 형식이 아닙니다.")

    is_duplicate = user_crud.is_email_duplicated(db, validated_email)
    return {"email": validated_email, "is_duplicate": is_duplicate}

@router.post("/login", response_model=user_schema.TokenResponse)
def login(user: user_schema.UserLogin, db: Session = Depends(get_db)):
    db_user = user_crud.get_user_by_email(db, user.email)
    if not db_user or not user_crud.verify_password(user.password, db_user.password_hash):
        raise BadRequestException("이메일 또는 비밀번호가 올바르지 않습니다.")
    token = create_access_token(data={"sub": db_user.user_id})
    return {"access_token": token, "token_type": "bearer"}

@router.get("/settings", response_model=user_schema.UserSettingRead)
def get_user_settings(user = Depends(get_current_user), db: Session = Depends(get_db)):
    return user_crud.get_user_settings(db, user.user_id)

@router.put("/settings/alerts")
def update_alerts(receive_alerts: bool, user = Depends(get_current_user), db: Session = Depends(get_db)):
    return user_crud.update_alert_setting(db, user.user_id, receive_alerts)
