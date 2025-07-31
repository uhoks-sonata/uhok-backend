"""
User 관련 Pydantic 스키마
"""
from pydantic import BaseModel, EmailStr, Field

class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=4)
    password_confirm: str = Field(min_length=4)
    username: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserOut(BaseModel):
    user_id: int
    email: EmailStr
    username: str
    created_at: str

    class Config:
        orm_mode = True

class UserSettingOut(BaseModel):
    receive_alerts: bool
