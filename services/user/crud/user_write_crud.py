"""User write CRUD functions."""

from sqlalchemy.ext.asyncio import AsyncSession

from services.user.crud.user_password_crud import hash_password
from services.user.models.account_model import User
from services.user.models.setting_model import UserSetting


async def create_user(db: AsyncSession, email: str, password: str, username: str):
    """신규 사용자 회원가입 처리 (User row + 기본 UserSetting row 생성)."""
    hashed_pw = hash_password(password)
    user = User(email=email, password_hash=hashed_pw, username=username)
    db.add(user)
    await db.commit()
    await db.refresh(user)

    setting = UserSetting(user_id=user.user_id)
    db.add(setting)
    await db.commit()
    await db.refresh(user)
    return user
