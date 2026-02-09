from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer, SMALLINT, String, UniqueConstraint
from sqlalchemy.orm import relationship

from common.database.base_mariadb import MariaBase

class HomeshoppingCart(MariaBase):
    """홈쇼핑 장바구니 테이블"""
    __tablename__ = "HOMESHOPPING_CART"
    
    cart_id = Column("CART_ID", Integer, primary_key=True, autoincrement=True, comment="장바구니 ID")
    user_id = Column("USER_ID", Integer, nullable=False, comment="사용자 ID")
    product_id = Column("PRODUCT_ID", BigInteger, ForeignKey("FCT_HOMESHOPPING_PRODUCT_INFO.PRODUCT_ID"), nullable=False, comment="제품 코드")
    quantity = Column("QUANTITY", Integer, nullable=False, default=1, comment="수량")
    created_at = Column("CREATED_AT", DateTime, nullable=True, comment="추가 시간")
    recipe_id = Column("RECIPE_ID", Integer, ForeignKey("FCT_RECIPE.RECIPE_ID", onupdate="RESTRICT", ondelete="RESTRICT"), nullable=True, comment="레시피 ID")
    
    # 추가 필드: 상품명과 이미지 (런타임에 설정)
    product_name = None
    thumb_img_url = None
    
    __table_args__ = (
        UniqueConstraint("USER_ID", "PRODUCT_ID", name="UK_HOMESHOPPING_CART_USER_PRODUCT"),
    )
    
    # 제품 정보와 N:1 관계 설정
    product_info = relationship(
        "HomeshoppingProductInfo",
        primaryjoin="HomeshoppingCart.product_id==HomeshoppingProductInfo.product_id",
        lazy="select"
    )


class HomeshoppingSearchHistory(MariaBase):
    """홈쇼핑 검색 이력 테이블"""
    __tablename__ = "HOMESHOPPING_SEARCH_HISTORY"
    
    homeshopping_history_id = Column("HOMESHOPPING_HISTORY_ID", Integer, primary_key=True, autoincrement=True, comment="검색 이력 ID (PK)")
    user_id = Column("USER_ID", Integer, nullable=False, comment="사용자 ID (회원 PK 참조)")
    homeshopping_keyword = Column("HOMESHOPPING_KEYWORD", String(100), nullable=False, comment="검색 키워드")
    homeshopping_searched_at = Column("HOMESHOPPING_SEARCHED_AT", DateTime, nullable=False, comment="검색 시간")


class HomeshoppingLikes(MariaBase):
    """홈쇼핑 찜 테이블"""
    __tablename__ = "HOMESHOPPING_LIKES"
    
    homeshopping_like_id = Column("HOMESHOPPING_LIKE_ID", Integer, primary_key=True, autoincrement=True, comment="찜 ID (PK)")
    user_id = Column("USER_ID", Integer, nullable=False, comment="사용자 ID (회원 PK 참조, 논리 FK)")
    live_id = Column("LIVE_ID", Integer, ForeignKey("FCT_HOMESHOPPING_LIST.LIVE_ID", ondelete="RESTRICT"), nullable=False, comment="방송 ID (FK)")
    homeshopping_like_created_at = Column("HOMESHOPPING_LIKE_CREATED_AT", DateTime, nullable=False, comment="찜한 시간")

    # 방송 정보와 N:1 관계 설정
    live_info = relationship(
        "HomeshoppingList",
        primaryjoin="HomeshoppingLikes.live_id==HomeshoppingList.live_id",
        lazy="select"
    )


class HomeshoppingNotification(MariaBase):
    """홈쇼핑 알림 테이블 (방송 찜 + 주문 상태 변경 통합)"""
    __tablename__ = "HOMESHOPPING_NOTIFICATION"
    
    notification_id = Column("NOTIFICATION_ID", BigInteger, primary_key=True, autoincrement=True, comment="알림 고유번호 (PK)")
    user_id = Column("USER_ID", Integer, nullable=False, comment="알림 대상 사용자 ID (논리 FK, 외래키 제약 없음)")
    
    # 알림 타입 구분
    notification_type = Column("NOTIFICATION_TYPE", String(50), nullable=False, default="order_status", comment="알림 타입 (broadcast_start, order_status)")
    
    # 관련 엔티티 정보 (방송 찜 또는 주문)
    related_entity_type = Column("RELATED_ENTITY_TYPE", String(50), nullable=False, default="order", comment="관련 엔티티 타입 (product, order)")
    related_entity_id = Column("RELATED_ENTITY_ID", BigInteger, nullable=False, default=0, comment="관련 엔티티 ID (제품 ID 또는 주문 ID)")
    
    # 방송 찜 알림 관련 필드
    homeshopping_like_id = Column("HOMESHOPPING_LIKE_ID", Integer, ForeignKey("HOMESHOPPING_LIKES.HOMESHOPPING_LIKE_ID", ondelete="CASCADE", onupdate="CASCADE"), nullable=True, comment="관련 찜 ID (FK: HOMESHOPPING_LIKES.HOMESHOPPING_LIKE_ID)")
    
    # 주문 상태 변경 알림 관련 필드
    homeshopping_order_id = Column("HOMESHOPPING_ORDER_ID", Integer, ForeignKey("HOMESHOPPING_ORDERS.HOMESHOPPING_ORDER_ID", ondelete="CASCADE", onupdate="CASCADE"), nullable=True, comment="관련 주문 상세 ID (FK: HOMESHOPPING_ORDERS.HOMESHOPPING_ORDER_ID)")
    status_id = Column("STATUS_ID", Integer, ForeignKey("STATUS_MASTER.STATUS_ID", ondelete="RESTRICT", onupdate="CASCADE"), nullable=True, comment="상태 코드 ID (알림 트리거, FK: STATUS_MASTER.STATUS_ID)")
    
    # 공통 필드
    title = Column("TITLE", String(100), nullable=False, comment="알림 제목")
    message = Column("MESSAGE", String(255), nullable=False, comment="알림 메시지(상세)")
    is_read = Column("IS_READ", SMALLINT, nullable=False, default=0, comment="읽음 여부 (0: 안읽음, 1: 읽음)")
    created_at = Column("CREATED_AT", DateTime, nullable=False, server_default='current_timestamp()', comment='알림 생성 시각')
    read_at = Column("READ_AT", DateTime, nullable=True, comment="읽음 처리 시각")
    
    # 관계 설정
    homeshopping_order = relationship("HomeShoppingOrder", back_populates="notifications", lazy="noload")
    status = relationship("StatusMaster", lazy="noload")
    homeshopping_like = relationship("HomeshoppingLikes", lazy="noload")

