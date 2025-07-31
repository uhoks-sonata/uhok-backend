"""
User 관련 DB 접근 함수 (CRUD)
"""
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from services.user.models.user_model import User, UserSetting

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_user_by_email(db: Session, email: str):
    """
        주어진 이메일(email)에 해당하는 사용자(User) 객체를 반환
        - 없으면 None 반환
    """
    return db.query(User).filter(User.email == email).first() # type: ignore

def get_user_by_id(db: Session, user_id: int):
    """
        주어진 사용자 ID(user_id)에 해당하는 사용자(User) 객체를 반환
        - 없으면 None 반환
    """
    return db.query(User).filter(User.user_id == user_id).first() # type: ignore

def create_user(db: Session, email: str, password: str, username: str):
    """
        신규 사용자 회원가입 처리
        - 비밀번호는 bcrypt로 해싱하여 저장
        - User row + 기본 UserSetting row를 함께 생성
        - 생성된 User 객체 반환
    """
    hashed_pw = pwd_context.hash(password)
    user = User(email=email, password_hash=hashed_pw, username=username)
    db.add(user)
    db.commit()
    db.refresh(user)
    # 기본 설정 생성
    setting = UserSetting(user_id=user.user_id)
    db.add(setting)
    db.commit()
    db.refresh(user)
    return user

def verify_password(plain_pw, hashed_pw):
    """
        입력받은 평문 비밀번호와 해시된 비밀번호가 일치하는지 검증
        - 일치 시 True, 아니면 False 반환
    """
    return pwd_context.verify(plain_pw, hashed_pw)
