"""
홈쇼핑 관련 테이블들의 ORM 모델 정의 모듈
- 변수는 소문자, DB 컬럼명은 대문자로 명시적 매핑
- DB 데이터 정의서 기반으로 변수명 통일
"""

from sqlalchemy import (
    Column, Integer, String, DateTime, Text, BigInteger, 
    Enum, ForeignKey, SMALLINT, Date, Time, UniqueConstraint
)
from sqlalchemy.orm import relationship

from common.database.base_mariadb import MariaBase


class HomeshoppingInfo(MariaBase):
    """홈쇼핑 정보 테이블"""
    __tablename__ = "HOMESHOPPING_INFO"
    
    homeshopping_id = Column("HOMESHOPPING_ID", SMALLINT, primary_key=True, comment="홈쇼핑 인덱스")
    homeshopping_name = Column("HOMESHOPPING_NAME", String(20), comment="홈쇼핑명")
    homeshopping_channel = Column("HOMESHOPPING_CHANNEL", SMALLINT, comment="홈쇼핑 채널")
    homeshopping_url = Column("HOMESHOPPING_URL", String(255), comment="홈쇼핑 URL")
    
    # 홈쇼핑 라이브 목록과 1:N 관계 설정
    live_lists = relationship(
        "HomeshoppingList",
        back_populates="homeshopping_info",
        lazy="select"
    )


class HomeshoppingList(MariaBase):
    """홈쇼핑 라이브 목록 테이블"""
    __tablename__ = "FCT_HOMESHOPPING_LIST"
    
    live_id = Column("LIVE_ID", Integer, primary_key=True, autoincrement=True, comment="라이브 인덱스")
    homeshopping_id = Column("HOMESHOPPING_ID", SMALLINT, ForeignKey("HOMESHOPPING_INFO.HOMESHOPPING_ID"), comment="홈쇼핑 인덱스")
    live_date = Column("LIVE_DATE", Date, comment="방영일")
    live_start_time = Column("LIVE_START_TIME", Time, comment="방영 시작 시간")
    live_end_time = Column("LIVE_END_TIME", Time, comment="방영 종료 시간")
    promotion_type = Column("PROMOTION_TYPE", Enum('main', 'sub', name='promotion_type_enum'), comment="main/sub")
    product_id = Column("PRODUCT_ID", BigInteger, comment="제품 코드")
    product_name = Column("PRODUCT_NAME", Text, comment="제품명")
    thumb_img_url = Column("THUMB_IMG_URL", Text, comment="썸네일 URL")

    # 홈쇼핑 정보와 N:1 관계 설정
    homeshopping_info = relationship(
        "HomeshoppingInfo",
        back_populates="live_lists",
        lazy="select"
    )

    # 제품 정보와는 product_id로만 연결 (관계 없음)
    # 상세 정보, 이미지, 찜은 FCT_HOMESHOPPING_PRODUCT_INFO와 관계


class HomeshoppingProductInfo(MariaBase):
    """홈쇼핑 제품 정보 테이블"""
    __tablename__ = "FCT_HOMESHOPPING_PRODUCT_INFO"
    
    product_id = Column("PRODUCT_ID", BigInteger, primary_key=True, comment="제품코드")
    store_name = Column("STORE_NAME", String(1000), comment="판매자 정보")
    sale_price = Column("SALE_PRICE", BigInteger, comment="원가")
    dc_rate = Column("DC_RATE", Integer, comment="할인율")
    dc_price = Column("DC_PRICE", BigInteger, comment="할인가")

    # 홈쇼핑 라이브 목록과는 product_id로만 연결 (관계 없음)


class HomeshoppingClassify(MariaBase):
    """홈쇼핑 제품 분류 테이블"""
    __tablename__ = "HOMESHOPPING_CLASSIFY"
    
    product_id = Column("PRODUCT_ID", BigInteger, primary_key=True, comment="홈쇼핑 제품 코드")
    product_name = Column("PRODUCT_NAME", Text, comment="제품명")
    cls_food = Column("CLS_FOOD", SMALLINT, comment="식품 분류")
    cls_ing = Column("CLS_ING", SMALLINT, comment="식재료 분류")

    # 홈쇼핑 라이브 목록과는 product_id로만 연결 (관계 없음)


class HomeshoppingDetailInfo(MariaBase):
    """홈쇼핑 상세 정보 테이블"""
    __tablename__ = "FCT_HOMESHOPPING_DETAIL_INFO"
    
    detail_id = Column("DETAIL_ID", Integer, primary_key=True, autoincrement=True, comment="상세정보 인덱스")
    product_id = Column("PRODUCT_ID", BigInteger, ForeignKey("FCT_HOMESHOPPING_PRODUCT_INFO.PRODUCT_ID"), comment="제품 코드")
    detail_col = Column("DETAIL_COL", String(1000), comment="상세정보 컬럼명")
    detail_val = Column("DETAIL_VAL", Text, comment="상세정보 텍스트")

    # 제품 정보와 N:1 관계 설정
    product_info = relationship(
        "HomeshoppingProductInfo",
        primaryjoin="HomeshoppingDetailInfo.product_id==HomeshoppingProductInfo.product_id",
        lazy="select"
    )


class HomeshoppingImgUrl(MariaBase):
    """홈쇼핑 이미지 URL 테이블"""
    __tablename__ = "FCT_HOMESHOPPING_IMG_URL"
    
    img_id = Column("IMG_ID", Integer, primary_key=True, autoincrement=True, comment="이미지 인덱스")
    product_id = Column("PRODUCT_ID", BigInteger, ForeignKey("FCT_HOMESHOPPING_PRODUCT_INFO.PRODUCT_ID"), comment="제품 코드")
    sort_order = Column("SORT_ORDER", SMALLINT, default=0, comment="이미지 순서")
    img_url = Column("IMG_URL", Text, comment="이미지 URL")
    
    # 제품 정보와 N:1 관계 설정
    product_info = relationship(
        "HomeshoppingProductInfo",
        primaryjoin="HomeshoppingImgUrl.product_id==HomeshoppingProductInfo.product_id",
        lazy="select"
    )


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
    product_id = Column("PRODUCT_ID", BigInteger, ForeignKey("FCT_HOMESHOPPING_PRODUCT_INFO.PRODUCT_ID", ondelete="RESTRICT"), nullable=False, comment="제품 ID (FK)")
    homeshopping_like_created_at = Column("HOMESHOPPING_LIKE_CREATED_AT", DateTime, nullable=False, comment="찜한 시간")

    # 제품 정보와 N:1 관계 설정
    product_info = relationship(
        "HomeshoppingProductInfo",
        primaryjoin="HomeshoppingLikes.product_id==HomeshoppingProductInfo.product_id",
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



