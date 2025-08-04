"""
ORDERS 테이블의 SQLAlchemy ORM 모델 정의 (DB 컬럼명은 대문자, 변수는 소문자)
"""
from sqlalchemy import Column, Integer, DateTime, ForeignKey
from common.database.base_mariadb import MariaBase

class Order(MariaBase):
    """
    ORDERS 테이블 ORM 모델 (주문 내역)
    """
    __tablename__ = "ORDERS"

    order_id = Column("ORDER_ID", Integer, primary_key=True, autoincrement=True, comment="주문 고유 인덱스")
    user_id = Column("USER_ID", Integer, ForeignKey("USERS.USER_ID"), nullable=False, comment="주문한 사용자 인덱스")
    price_id = Column("PRICE_ID", Integer, ForeignKey("PRICE.PRICE_ID"), nullable=False, comment="가격/상품 정보 인덱스")
    order_time = Column("ORDER_TIME", DateTime, nullable=False, comment="주문(구매) 시각")
    cancel_time = Column("CANCEL_TIME", DateTime, nullable=True, comment="주문 취소 시각")
