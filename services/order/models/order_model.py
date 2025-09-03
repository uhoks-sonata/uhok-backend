"""
주문 통합(ORDERS), 콕 주문(KOK_ORDERS), 홈쇼핑 주문(HOMESHOPPING_ORDERS) ORM 모델 정의
"""
from sqlalchemy import Column, Integer, DateTime, ForeignKey, String, BigInteger
from sqlalchemy.orm import relationship
from datetime import datetime
from common.database.base_mariadb import MariaBase

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
    user_id = Column("USER_ID", Integer, nullable=False)  # 논리적 FK: AUTH_DB.USERS.USER_ID
    order_time = Column("ORDER_TIME", DateTime, nullable=False)
    cancel_time = Column("CANCEL_TIME", DateTime, nullable=True)

    kok_orders = relationship("KokOrder", uselist=True, back_populates="order", lazy="noload")
    homeshopping_orders = relationship("HomeShoppingOrder", uselist=True, back_populates="order", lazy="noload")

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
    recipe_id = Column("RECIPE_ID", Integer, ForeignKey("FCT_RECIPE.RECIPE_ID", onupdate="RESTRICT", ondelete="RESTRICT"), nullable=True)

    order = relationship("Order", back_populates="kok_orders", lazy="noload")
    status_history = relationship("KokOrderStatusHistory", back_populates="kok_order", lazy="noload")

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

    kok_order = relationship("KokOrder", back_populates="status_history", lazy="noload")
    status = relationship("StatusMaster", lazy="noload")

class HomeShoppingOrder(MariaBase):
    """
    HOMESHOPPING_ORDERS 테이블 (홈쇼핑 주문 상세)
    """
    __tablename__ = "HOMESHOPPING_ORDERS"

    homeshopping_order_id = Column("HOMESHOPPING_ORDER_ID", Integer, primary_key=True, autoincrement=True, comment="홈쇼핑 주문 상세 고유번호(PK)")
    order_id = Column("ORDER_ID", Integer, ForeignKey("ORDERS.ORDER_ID", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False, comment="상위 주문 고유번호(FK: ORDERS.ORDER_ID)")
    product_id = Column("PRODUCT_ID", BigInteger, ForeignKey("FCT_HOMESHOPPING_PRODUCT_INFO.PRODUCT_ID", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False, comment="제품 ID (FK: FCT_HOMESHOPPING_PRODUCT_INFO.PRODUCT_ID)")
    dc_price = Column("DC_PRICE", BigInteger, nullable=False, comment="할인가(당시 기준 금액 스냅샷)")
    quantity = Column("QUANTITY", Integer, nullable=False, comment="주문 수량")
    order_price = Column("ORDER_PRICE", BigInteger, nullable=True, comment="주문 금액(합계 또는 개별 기준, 비즈니스 룰에 따름)")
    
    # 추가 필드: 상품명 (런타임에 설정)
    product_name = None
    product_image = None

    order = relationship("Order", back_populates="homeshopping_orders", lazy="noload")
    status_history = relationship("HomeShoppingOrderStatusHistory", back_populates="homeshopping_order", lazy="noload")
    notifications = relationship("HomeshoppingNotification", back_populates="homeshopping_order", lazy="noload")


class HomeShoppingOrderStatusHistory(MariaBase):
    """
    HOMESHOPPING_ORDER_STATUS_HISTORY 테이블 (홈쇼핑 주문 상태 변경 이력)
    """
    __tablename__ = "HOMESHOPPING_ORDER_STATUS_HISTORY"

    history_id = Column("HISTORY_ID", BigInteger, primary_key=True, autoincrement=True, comment="상태 변경 이력 고유번호(PK)")
    homeshopping_order_id = Column("HOMESHOPPING_ORDER_ID", Integer, ForeignKey("HOMESHOPPING_ORDERS.HOMESHOPPING_ORDER_ID", ondelete="CASCADE", onupdate="CASCADE"), nullable=False, comment="홈쇼핑 주문 상세 고유번호 (FK: HOMESHOPPING_ORDERS.HOMESHOPPING_ORDER_ID)")
    status_id = Column("STATUS_ID", Integer, ForeignKey("STATUS_MASTER.STATUS_ID", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False, comment="상태 ID (FK: STATUS_MASTER.STATUS_ID)")
    changed_at = Column("CHANGED_AT", DateTime, nullable=False, default=datetime.now, comment="상태 변경 일시")
    changed_by = Column("CHANGED_BY", Integer, nullable=True, comment="상태 변경자(관리자/사용자 ID, 옵션/논리 FK)")

    homeshopping_order = relationship("HomeShoppingOrder", back_populates="status_history", lazy="noload")
    status = relationship("StatusMaster", lazy="noload")
