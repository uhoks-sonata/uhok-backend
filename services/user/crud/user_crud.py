from sqlalchemy.orm import Session
from services.user import models
from services.user.schemas import user_schema
from passlib.context import CryptContext
from common.errors import ConflictException, NotFoundException

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_user_by_email(db: Session, email: str):
    return db.query(models.User).filter(models.User.email == email).first()

def get_user_by_id(db: Session, user_id: int):
    return db.query(models.User).filter(models.User.user_id == user_id).first()

def create_user(db: Session, user: user_schema.UserCreate):
    if get_user_by_email(db, user.email):
        raise ConflictException("이미 등록된 이메일입니다.")

    hashed_pw = pwd_context.hash(user.password)
    db_user = models.User(
        email=user.email,
        password_hash=hashed_pw,
        username=user.username,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    setting = models.UserSetting(user_id=db_user.user_id)
    db.add(setting)
    db.commit()

    return db_user

def is_email_duplicated(db: Session, email: str) -> bool:
    return db.query(models.User).filter(models.User.email == email).first() is not None

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_user_settings(db: Session, user_id: int):
    setting = db.query(models.UserSetting).filter_by(user_id=user_id).first()
    if not setting:
        raise NotFoundException("사용자 설정")
    return setting

def update_alert_setting(db: Session, user_id: int, receive_alerts: bool):
    setting = get_user_settings(db, user_id)
    setting.receive_alerts = receive_alerts
    db.commit()
    db.refresh(setting)
    return setting
