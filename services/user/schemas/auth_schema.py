"""User auth-related schemas."""

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    """회원가입 요청용 스키마."""

    email: EmailStr
    password: str = Field(min_length=4)
    username: str


class EmailDuplicateCheckResponse(BaseModel):
    """이메일 중복 확인 응답 스키마."""

    email: EmailStr
    is_duplicate: bool
    message: str


class UserLogin(BaseModel):
    """로그인 요청용 스키마."""

    email: EmailStr
    password: str
