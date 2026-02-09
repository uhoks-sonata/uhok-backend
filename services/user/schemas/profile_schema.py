"""User profile-related schemas."""

from datetime import datetime

from pydantic import BaseModel, EmailStr


class UserOut(BaseModel):
    """회원정보 응답 스키마."""

    user_id: int
    email: EmailStr
    username: str
    created_at: datetime

    class Config:
        from_attributes = True


class UserSettingOut(BaseModel):
    """사용자 설정 응답 스키마."""

    receive_notification: bool
