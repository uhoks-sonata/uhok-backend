"""HomeShopping order ORM models."""

from datetime import datetime

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer
from sqlalchemy.orm import relationship

from common.database.base_mariadb import MariaBase


class HomeShoppingOrder(MariaBase):
    """HOMESHOPPING_ORDERS 테이블 (홈쇼핑 주문 상세)"""

    __tablename__ = "HOMESHOPPING_ORDERS"

    homeshopping_order_id = Column("HOMESHOPPING_ORDER_ID", Integer, primary_key=True, autoincrement=True, comment="홈쇼핑 주문 상세 고유번호(PK)")
    order_id = Column("ORDER_ID", Integer, ForeignKey("ORDERS.ORDER_ID", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False, comment="상위 주문 고유번호(FK: ORDERS.ORDER_ID)")
    product_id = Column("PRODUCT_ID", BigInteger, ForeignKey("FCT_HOMESHOPPING_PRODUCT_INFO.PRODUCT_ID", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False, comment="제품 ID (FK: FCT_HOMESHOPPING_PRODUCT_INFO.PRODUCT_ID)")
    dc_price = Column("DC_PRICE", BigInteger, nullable=False, comment="할인가(당시 기준 금액 스냅샷)")
    quantity = Column("QUANTITY", Integer, nullable=False, comment="주문 수량")
    order_price = Column("ORDER_PRICE", BigInteger, nullable=True, comment="주문 금액(합계 또는 개별 기준, 비즈니스 룰에 따름)")

    product_name = None
    product_image = None

    order = relationship("Order", back_populates="homeshopping_orders", lazy="noload")
    status_history = relationship("HomeShoppingOrderStatusHistory", back_populates="homeshopping_order", lazy="noload")
    notifications = relationship("HomeshoppingNotification", back_populates="homeshopping_order", lazy="noload")


class HomeShoppingOrderStatusHistory(MariaBase):
    """HOMESHOPPING_ORDER_STATUS_HISTORY 테이블 (홈쇼핑 주문 상태 변경 이력)"""

    __tablename__ = "HOMESHOPPING_ORDER_STATUS_HISTORY"

    history_id = Column("HISTORY_ID", BigInteger, primary_key=True, autoincrement=True, comment="상태 변경 이력 고유번호(PK)")
    homeshopping_order_id = Column("HOMESHOPPING_ORDER_ID", Integer, ForeignKey("HOMESHOPPING_ORDERS.HOMESHOPPING_ORDER_ID", ondelete="CASCADE", onupdate="CASCADE"), nullable=False, comment="홈쇼핑 주문 상세 고유번호 (FK: HOMESHOPPING_ORDERS.HOMESHOPPING_ORDER_ID)")
    status_id = Column("STATUS_ID", Integer, ForeignKey("STATUS_MASTER.STATUS_ID", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False, comment="상태 ID (FK: STATUS_MASTER.STATUS_ID)")
    changed_at = Column("CHANGED_AT", DateTime, nullable=False, default=datetime.now, comment="상태 변경 일시")
    changed_by = Column("CHANGED_BY", Integer, nullable=True, comment="상태 변경자(관리자/사용자 ID, 옵션/논리 FK)")

    homeshopping_order = relationship("HomeShoppingOrder", back_populates="status_history", lazy="noload")
    status = relationship("StatusMaster", lazy="noload")
