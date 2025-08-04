"""
주문 통합(ORDERS), 콕 주문(KOK_ORDERS), 홈쇼핑 주문(HOMESHOPPING_ORDERS) ORM 모델 정의
"""
from sqlalchemy import Column, Integer, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class Order(Base):
    """
    ORDERS 테이블 (주문 공통 정보)
    """
    __tablename__ = "ORDERS"

    order_id = Column("ORDER_ID", Integer, primary_key=True, autoincrement=True)
    user_id = Column("USER_ID", Integer, ForeignKey("USERS.USER_ID"), nullable=False)
    order_time = Column("ORDER_TIME", DateTime, nullable=False)
    cancel_time = Column("CANCEL_TIME", DateTime, nullable=True)

    kok_order = relationship("KokOrder", uselist=False, back_populates="order")
    homeshopping_order = relationship("HomeShoppingOrder", uselist=False, back_populates="order")

class KokOrder(Base):
    """
    KOK_ORDERS 테이블 (콕 주문 상세)
    """
    __tablename__ = "KOK_ORDERS"

    kok_order_id = Column("KOK_ORDER_ID", Integer, primary_key=True, autoincrement=True)
    price_id = Column("PRICE_ID", Integer, ForeignKey("PRICE.PRICE_ID"), nullable=False)
    order_id = Column("ORDER_ID", Integer, ForeignKey("ORDERS.ORDER_ID"), nullable=False, unique=True)

    order = relationship("Order", back_populates="kok_order")

class HomeShoppingOrder(Base):
    """
    HOMESHOPPING_ORDERS 테이블 (HomeShopping 주문 상세)
    """
    __tablename__ = "HOMESHOPPING_ORDERS"

    homeshopping_order_id = Column("HOMESHOPPING_ORDER_ID", Integer, primary_key=True, autoincrement=True)
    live_id = Column("LIVE_ID", Integer, ForeignKey("LIVE.LIVE_ID"), nullable=False)
    order_id = Column("ORDER_ID", Integer, ForeignKey("ORDERS.ORDER_ID"), nullable=False, unique=True)

    order = relationship("Order", back_populates="homeshopping_order")
