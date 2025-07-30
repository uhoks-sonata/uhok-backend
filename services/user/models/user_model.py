from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, func
from sqlalchemy.orm import relationship
from services.user.database import Base

class User(Base):
    __tablename__ = "users"

    user_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    username = Column(String(100))
    created_at = Column(DateTime, server_default=func.now())

    settings = relationship("UserSetting", back_populates="user", uselist=False)


class UserSetting(Base):
    __tablename__ = "user_settings"

    setting_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False, unique=True)
    receive_alerts = Column(Boolean, default=True)

    user = relationship("User", back_populates="settings")
