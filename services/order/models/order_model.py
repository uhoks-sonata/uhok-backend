"""
주문 통합(ORDERS), 콕 주문(KOK_ORDERS), 홈쇼핑 주문(HOMESHOPPING_ORDERS) ORM 모델 정의
"""
from sqlalchemy import Column, Integer, DateTime, ForeignKey, String, BigInteger
from sqlalchemy.orm import relationship
from datetime import datetime

from services.kok.models.kok_model import KokProductInfo  # 반드시 임포트

from common.database.base_mariadb import MariaBase

class StatusMaster(MariaBase):
    """
    STATUS_MASTER 테이블 (상태 코드 마스터)
    """
    __tablename__ = "STATUS_MASTER"

    status_id = Column("STATUS_ID", Integer, primary_key=True, autoincrement=True)
    status_code = Column("STATUS_CODE", String(30), nullable=False, unique=True)
    status_name = Column("STATUS_NAME", String(100), nullable=False)

class Order(MariaBase):
    """
    ORDERS 테이블 (주문 공통 정보)
    """
    __tablename__ = "ORDERS"

    order_id = Column("ORDER_ID", Integer, primary_key=True, autoincrement=True)
    user_id = Column("USER_ID", Integer, nullable=False)
    order_time = Column("ORDER_TIME", DateTime, nullable=False)
    cancel_time = Column("CANCEL_TIME", DateTime, nullable=True)

    kok_order = relationship("KokOrder", uselist=False, back_populates="order")
    homeshopping_order = relationship("HomeShoppingOrder", uselist=False, back_populates="order")

class KokOrder(MariaBase):
    """
    KOK_ORDERS 테이블 (콕 주문 상세)
    """
    __tablename__ = "KOK_ORDERS"

    kok_order_id = Column("KOK_ORDER_ID", Integer, primary_key=True, autoincrement=True)
    order_id = Column("ORDER_ID", Integer, ForeignKey("ORDERS.ORDER_ID"), nullable=False)
    kok_price_id = Column("KOK_PRICE_ID", Integer, ForeignKey("FCT_KOK_PRICE_INFO.KOK_PRICE_ID"), nullable=False)
    kok_product_id = Column("KOK_PRODUCT_ID", Integer, ForeignKey("FCT_KOK_PRODUCT_INFO.KOK_PRODUCT_ID"), nullable=False)
    quantity = Column("QUANTITY", Integer, nullable=False)
    order_price = Column("ORDER_PRICE", Integer, nullable=True)

    order = relationship("Order", back_populates="kok_order")
    status_history = relationship("KokOrderStatusHistory", back_populates="kok_order")

class KokOrderStatusHistory(MariaBase):
    """
    KOK_ORDER_STATUS_HISTORY 테이블 (콕 주문 상태 변경 이력)
    """
    __tablename__ = "KOK_ORDER_STATUS_HISTORY"

    history_id = Column("HISTORY_ID", BigInteger, primary_key=True, autoincrement=True)
    kok_order_id = Column("KOK_ORDER_ID", Integer, ForeignKey("KOK_ORDERS.KOK_ORDER_ID"), nullable=False)
    status_id = Column("STATUS_ID", Integer, ForeignKey("STATUS_MASTER.STATUS_ID"), nullable=False)
    changed_at = Column("CHANGED_AT", DateTime, nullable=False, default=datetime.now)
    changed_by = Column("CHANGED_BY", Integer, nullable=True)

    kok_order = relationship("KokOrder", back_populates="status_history")
    status = relationship("StatusMaster")

class HomeShoppingOrder(MariaBase):
    """
    HOMESHOPPING_ORDERS 테이블 (HomeShopping 주문 상세)
    """
    __tablename__ = "HOMESHOPPING_ORDERS"

    homeshopping_order_id = Column("HOMESHOPPING_ORDER_ID", Integer, primary_key=True, autoincrement=True)
    live_id = Column("LIVE_ID", Integer, ForeignKey("LIVE.LIVE_ID"), nullable=False)
    order_id = Column("ORDER_ID", Integer, ForeignKey("ORDERS.ORDER_ID"), nullable=False, unique=True)

    order = relationship("Order", back_populates="homeshopping_order")
