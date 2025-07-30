# schemas/user_schema.py
from pydantic import BaseModel, EmailStr, model_validator
from typing import Optional
from common.errors import BadRequestException

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    password_confirm: str
    username: Optional[str] = None

    @model_validator(mode="after")
    def validate_password_match(self):
        if self.password != self.password_confirm:
            raise BadRequestException("비밀번호와 비밀번호 확인이 일치하지 않습니다.")
        return self

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserRead(BaseModel):
    user_id: int
    email: EmailStr
    username: Optional[str]

    class Config:
        from_attributes = True

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class UserSettingRead(BaseModel):
    receive_alerts: bool

    class Config:
        from_attributes = True
