from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from services.user.database import Base
from datetime import datetime

class User(Base):
    __tablename__ = "USERS"
    user_id = Column("USER_ID", Integer, primary_key=True, autoincrement=True)
    email = Column("EMAIL", String(255), unique=True, nullable=False)
    password_hash = Column("PASSWORD_HASH", String(255), nullable=False)
    username = Column("USERNAME", String(100))
    created_at = Column("CREATED_AT", DateTime, default=datetime.utcnow)
    settings = relationship("UserSetting", back_populates="user", uselist=False)

class UserSetting(Base):
    __tablename__ = "USER_SETTINGS"
    setting_id = Column("SETTING_ID", Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        "USER_ID",
        Integer,
        ForeignKey("USERS.USER_ID", ondelete="RESTRICT", onupdate="SET NULL"),
        nullable=True, unique=True
    )
    receive_notification = Column("RECEIVE_NOTIFICATION", Boolean, default=True)
    user = relationship("User", back_populates="settings")
