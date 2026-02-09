"""User read CRUD functions."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from services.user.models.account_model import User


async def get_user_by_email(db: AsyncSession, email: str):
    """주어진 이메일(email)에 해당하는 사용자(User) 객체를 반환 (없으면 None)."""
    result = await db.execute(select(User).where(User.email == email))  # type: ignore
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: int):
    """주어진 사용자 ID(user_id)에 해당하는 사용자(User) 객체를 반환 (없으면 None)."""
    result = await db.execute(select(User).where(User.user_id == user_id))  # type: ignore
    return result.scalar_one_or_none()
