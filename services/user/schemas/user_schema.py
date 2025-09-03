"""
User 관련 Pydantic 스키마 정의 모듈
"""
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime

class UserCreate(BaseModel):
    """
    회원가입 요청용 스키마
    - email: 이메일 주소 (중복 불가)
    - password: 비밀번호 (최소 4자)
    - password_confirm: 비밀번호 확인 (최소 4자)
    - username: 닉네임
    """
    email: EmailStr                # 사용자 이메일 (형식 검증)
    password: str = Field(min_length=4)          # 비밀번호 (최소 4자)
    # password_confirm: str = Field(min_length=4)  # 비밀번호 확인 (최소 4자)
    username: str                  # 닉네임

class EmailDuplicateCheckResponse(BaseModel):
    """
    이메일 중복 확인 응답 스키마
    - email: 입력한 이메일
    - is_duplicate: True(중복), False(사용 가능)
    - message: 안내 메시지
    """
    email: EmailStr         # 요청받은 이메일 주소
    is_duplicate: bool      # 중복 여부 (True=중복, False=사용가능)
    message: str            # 안내 메시지 ("이미 존재" or "사용 가능")

class UserLogin(BaseModel):
    """
    로그인 요청용 스키마
    - email: 이메일 주소
    - password: 비밀번호
    """
    email: EmailStr         # 로그인용 이메일
    password: str           # 비밀번호

class UserOut(BaseModel):
    """
    회원정보 응답 스키마
    - user_id: 사용자 고유 ID
    - email: 이메일 주소
    - username: 닉네임
    - created_at: 가입 시각
    """
    user_id: int            # 사용자 고유 ID (DB PK)
    email: EmailStr         # 이메일 주소
    username: str           # 닉네임
    created_at: datetime         # 가입 시각

    class Config:
        # orm_mode = True       # ORM 객체 -> 스키마 자동 변환 지원
        from_attributes = True  # Pydantic V2부터 from_attributes 사용

class UserSettingOut(BaseModel):
    """
    사용자 설정 응답 스키마
    - receive_notification: 홈쇼핑 방송 알림 수신 여부
    """
    receive_notification: bool    # 알림 수신 여부 (True/False)
