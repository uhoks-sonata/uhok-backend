"""User account model."""

from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.orm import relationship

from common.database.base_mariadb import MariaBase


class User(MariaBase):
    __tablename__ = "USERS"

    user_id = Column("USER_ID", Integer, primary_key=True, autoincrement=True)
    email = Column("EMAIL", String(255), unique=True, nullable=False)
    password_hash = Column("PASSWORD_HASH", String(255), nullable=False)
    username = Column("USERNAME", String(100))
    created_at = Column("CREATED_AT", DateTime, default=datetime.utcnow)
    settings = relationship("UserSetting", back_populates="user", uselist=False)
