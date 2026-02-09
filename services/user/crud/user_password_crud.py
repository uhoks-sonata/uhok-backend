"""User password hashing and verification helpers."""

from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain_pw: str) -> str:
    """Hash plain text password with bcrypt."""
    return pwd_context.hash(plain_pw)


def verify_password(plain_pw, hashed_pw):
    """입력받은 평문 비밀번호와 해시된 비밀번호가 일치하는지 검증."""
    return pwd_context.verify(plain_pw, hashed_pw)
