"""User setting model."""

from sqlalchemy import Boolean, Column, ForeignKey, Integer
from sqlalchemy.orm import relationship

from common.database.base_mariadb import MariaBase


class UserSetting(MariaBase):
    __tablename__ = "USER_SETTINGS"

    setting_id = Column("SETTING_ID", Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        "USER_ID",
        Integer,
        ForeignKey("USERS.USER_ID", ondelete="RESTRICT", onupdate="SET NULL"),
        nullable=True,
        unique=True,
    )
    receive_notification = Column("RECEIVE_NOTIFICATION", Boolean, default=True)
    user = relationship("User", back_populates="settings")
