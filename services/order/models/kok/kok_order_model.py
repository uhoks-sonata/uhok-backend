"""Kok order ORM models."""

from datetime import datetime

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer
from sqlalchemy.orm import relationship

from common.database.base_mariadb import MariaBase


class KokOrder(MariaBase):
    """KOK_ORDERS 테이블 (콕 주문 상세)"""

    __tablename__ = "KOK_ORDERS"

    kok_order_id = Column("KOK_ORDER_ID", Integer, primary_key=True, autoincrement=True)
    order_id = Column("ORDER_ID", Integer, ForeignKey("ORDERS.ORDER_ID"), nullable=False)
    kok_price_id = Column("KOK_PRICE_ID", Integer, ForeignKey("FCT_KOK_PRICE_INFO.KOK_PRICE_ID"), nullable=False)
    kok_product_id = Column("KOK_PRODUCT_ID", Integer, ForeignKey("FCT_KOK_PRODUCT_INFO.KOK_PRODUCT_ID"), nullable=False)
    quantity = Column("QUANTITY", Integer, nullable=False)
    order_price = Column("ORDER_PRICE", Integer, nullable=True)
    recipe_id = Column("RECIPE_ID", Integer, ForeignKey("FCT_RECIPE.RECIPE_ID", onupdate="RESTRICT", ondelete="RESTRICT"), nullable=True)

    order = relationship("Order", back_populates="kok_orders", lazy="noload")
    status_history = relationship("KokOrderStatusHistory", back_populates="kok_order", lazy="noload")


class KokOrderStatusHistory(MariaBase):
    """KOK_ORDER_STATUS_HISTORY 테이블 (콕 주문 상태 변경 이력)"""

    __tablename__ = "KOK_ORDER_STATUS_HISTORY"

    history_id = Column("HISTORY_ID", BigInteger, primary_key=True, autoincrement=True)
    kok_order_id = Column("KOK_ORDER_ID", Integer, ForeignKey("KOK_ORDERS.KOK_ORDER_ID"), nullable=False)
    status_id = Column("STATUS_ID", Integer, ForeignKey("STATUS_MASTER.STATUS_ID"), nullable=False)
    changed_at = Column("CHANGED_AT", DateTime, nullable=False, default=datetime.now)
    changed_by = Column("CHANGED_BY", Integer, nullable=True)

    kok_order = relationship("KokOrder", back_populates="status_history", lazy="noload")
    status = relationship("StatusMaster", lazy="noload")
