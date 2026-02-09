"""Order base/status ORM models."""

from sqlalchemy import Column, Integer, DateTime, String
from sqlalchemy.orm import relationship

from common.database.base_mariadb import MariaBase


class StatusMaster(MariaBase):
    """STATUS_MASTER 테이블 (상태 코드 마스터)"""

    __tablename__ = "STATUS_MASTER"

    status_id = Column("STATUS_ID", Integer, primary_key=True, autoincrement=True)
    status_code = Column("STATUS_CODE", String(30), nullable=False, unique=True)
    status_name = Column("STATUS_NAME", String(100), nullable=False)


class Order(MariaBase):
    """ORDERS 테이블 (주문 공통 정보)"""

    __tablename__ = "ORDERS"

    order_id = Column("ORDER_ID", Integer, primary_key=True, autoincrement=True)
    user_id = Column("USER_ID", Integer, nullable=False)
    order_time = Column("ORDER_TIME", DateTime, nullable=False)
    cancel_time = Column("CANCEL_TIME", DateTime, nullable=True)

    kok_orders = relationship("KokOrder", uselist=True, back_populates="order", lazy="noload")
    homeshopping_orders = relationship("HomeShoppingOrder", uselist=True, back_populates="order", lazy="noload")
