from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.schema import UniqueConstraint

from common.database.base_mariadb import MariaBase

class KokSearchHistory(MariaBase):
    """
    KOK_SEARCH_HISTORY 테이블의 ORM 모델
    """
    __tablename__ = "KOK_SEARCH_HISTORY"

    kok_history_id = Column("KOK_HISTORY_ID", Integer, primary_key=True, autoincrement=True)  # 검색 이력 ID
    user_id = Column("USER_ID", Integer, nullable=False)  # 사용자 ID (회원 PK 참조)
    kok_keyword = Column("KOK_KEYWORD", String(100), nullable=False)  # 검색 키워드
    kok_searched_at = Column("KOK_SEARCHED_AT", DateTime, nullable=False)  # 검색 시간

class KokLikes(MariaBase):
    """
    KOK_LIKES 테이블의 ORM 모델
    """
    __tablename__ = "KOK_LIKES"

    kok_like_id = Column("KOK_LIKE_ID", Integer, primary_key=True, autoincrement=True)  # 찜 ID
    user_id = Column("USER_ID", Integer, nullable=False)  # 사용자 ID (회원 PK 참조)
    kok_product_id = Column("KOK_PRODUCT_ID", Integer, ForeignKey("FCT_KOK_PRODUCT_INFO.KOK_PRODUCT_ID"), nullable=False)  # 제품 ID
    kok_created_at = Column("KOK_CREATED_AT", DateTime, nullable=False)  # 찜한 시간

    # 제품 정보와 N:1 관계 설정
    product = relationship(
        "KokProductInfo",
        back_populates="likes",
        lazy="select"
    )

class KokCart(MariaBase):
    """
    KOK_CART 테이블의 ORM 모델
    """
    __tablename__ = "KOK_CART"

    kok_cart_id = Column("KOK_CART_ID", Integer, primary_key=True, autoincrement=True)  # 장바구니 ID
    user_id = Column("USER_ID", Integer, nullable=False)  # 사용자 ID (회원 PK 참조)
    kok_product_id = Column("KOK_PRODUCT_ID", Integer, ForeignKey("FCT_KOK_PRODUCT_INFO.KOK_PRODUCT_ID"), nullable=False)  # 제품 ID
    kok_quantity = Column("KOK_QUANTITY", Integer, nullable=False)  # 수량
    kok_created_at = Column("KOK_CREATED_AT", DateTime, nullable=True)  # 추가 시간
    recipe_id = Column("RECIPE_ID", Integer, ForeignKey("FCT_RECIPE.RECIPE_ID", onupdate="RESTRICT", ondelete="RESTRICT"), nullable=True)
    kok_price_id = Column("KOK_PRICE_ID", Integer, ForeignKey("FCT_KOK_PRICE_INFO.KOK_PRICE_ID"), nullable=False)  # 가격 정보 ID
    
    # 추가 필드: 상품명과 이미지 (런타임에 설정)
    product_name = None
    product_image = None

    __table_args__ = (
        UniqueConstraint("USER_ID", "KOK_PRODUCT_ID", name="UK_KOK_CART_USER_PRODUCT"),
    )

    # 제품 정보와 N:1 관계 설정
    product = relationship(
        "KokProductInfo",
        back_populates="cart_items",
        lazy="select"
    )
    
    # 가격 정보와 N:1 관계 설정
    price_info = relationship(
        "KokPriceInfo",
        lazy="select"
    )

class KokNotification(MariaBase):
    """
    KOK_NOTIFICATION 테이블의 ORM 모델
    """
    __tablename__ = "KOK_NOTIFICATION"

    notification_id = Column("NOTIFICATION_ID", Integer, primary_key=True, autoincrement=True, comment='알림 고유번호 (PK)')
    user_id = Column("USER_ID", Integer, nullable=False, comment='알림 대상 사용자 ID (논리 FK)')
    kok_order_id = Column("KOK_ORDER_ID", Integer, ForeignKey("KOK_ORDERS.KOK_ORDER_ID", onupdate="CASCADE", ondelete="CASCADE"), nullable=False, comment='관련 주문 상세 ID')
    status_id = Column("STATUS_ID", Integer, ForeignKey("STATUS_MASTER.STATUS_ID", onupdate="CASCADE", ondelete="RESTRICT"), nullable=False, comment='상태 코드 ID(알림 트리거)')
    title = Column("TITLE", String(100), nullable=False, comment='알림 제목')
    message = Column("MESSAGE", String(255), nullable=False, comment='알림 메시지(상세)')
    created_at = Column("CREATED_AT", DateTime, nullable=False, server_default='current_timestamp()', comment='알림 생성 시각')

    # 관계 설정 (논리적 관계)
    # user = relationship('User', backref='notifications')  # User 모델이 별도 서비스에 있을 경우
    # kok_order = relationship('KokOrder', backref='notifications')  # KokOrder 모델이 별도 서비스에 있을 경우
    # status = relationship('StatusMaster', backref='notifications')  # StatusMaster 모델이 별도 서비스에 있을 경우

