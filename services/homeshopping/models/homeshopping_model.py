"""
홈쇼핑 관련 테이블들의 ORM 모델 정의 모듈
- 변수는 소문자, DB 컬럼명은 대문자로 명시적 매핑
- DB 데이터 정의서 기반으로 변수명 통일
"""

from sqlalchemy import (
    Column, Integer, String, DateTime, Text, BigInteger, 
    Enum, ForeignKey, SMALLINT, Date, Time
)
from sqlalchemy.orm import relationship

from common.database.base_mariadb import MariaBase


class HomeshoppingInfo(MariaBase):
    """홈쇼핑 정보 테이블"""
    __tablename__ = "HOMESHOPPING_INFO"
    
    homeshopping_id = Column("HOMESHOPPING_ID", SMALLINT, primary_key=True, autoincrement=True, comment="홈쇼핑 인덱스")
    homeshopping_channel_name = Column("HOMESHOPPING_CHANNEL_NAME", String(20), comment="채널명")
    homeshopping_channel_number = Column("HOMSHOPPING_CHANNEL_NUMBER", SMALLINT, comment="채널번호")

    # 홈쇼핑 라이브 목록과 1:N 관계 설정
    live_lists = relationship(
        "HomeshoppingList",
        back_populates="homeshopping_info",
        primaryjoin="HomeshoppingInfo.homeshopping_id==HomeshoppingList.homeshopping_id",
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

    # 제품 정보와 1:1 관계 설정 (FK 제약 조건)
    product_info = relationship(
        "HomeshoppingProductInfo",
        back_populates="live_list",
        uselist=False,
        lazy="select"
    )

    # 상세 정보와 1:N 관계 설정
    detail_infos = relationship(
        "HomeshoppingDetailInfo",
        back_populates="live_list",
        primaryjoin="HomeshoppingList.product_id==HomeshoppingDetailInfo.product_id",
        lazy="select"
    )

    # 이미지와 1:N 관계 설정
    images = relationship(
        "HomeshoppingImgUrl",
        back_populates="live_list",
        primaryjoin="HomeshoppingList.product_id==HomeshoppingImgUrl.product_id",
        lazy="select"
    )

    # 찜과 1:N 관계 설정
    likes = relationship(
        "HomeshoppingLikes",
        back_populates="live_list",
        primaryjoin="HomeshoppingList.product_id==HomeshoppingLikes.product_id",
        lazy="select"
    )


class HomeshoppingProductInfo(MariaBase):
    """홈쇼핑 제품 정보 테이블"""
    __tablename__ = "FCT_HOMESHOPPING_PRODUCT_INFO"
    
    product_id = Column("PRODUCT_ID", BigInteger, primary_key=True, comment="제품코드")
    store_name = Column("STORE_NAME", String(1000), comment="판매자 정보")
    sale_price = Column("SALE_PRICE", BigInteger, comment="원가")
    dc_rate = Column("DC_RATE", Integer, comment="할인율")
    dc_price = Column("DC_PRICE", BigInteger, comment="할인가")

    # 홈쇼핑 라이브 목록과 1:1 관계 설정
    live_list = relationship(
        "HomeshoppingList",
        back_populates="product_info",
        uselist=False,
        lazy="select"
    )


class HomeshoppingDetailInfo(MariaBase):
    """홈쇼핑 상세 정보 테이블"""
    __tablename__ = "FCT_HOMESHOPPING_DETAIL_INFO"
    
    detail_id = Column("DETAIL_ID", Integer, primary_key=True, autoincrement=True, comment="상세정보 인덱스")
    product_id = Column("PRODUCT_ID", BigInteger, ForeignKey("FCT_HOMESHOPPING_PRODUCT_INFO.PRODUCT_ID"), comment="제품 코드")
    detail_col = Column("DETAIL_COL", String(1000), comment="상세정보 컬럼명")
    detail_val = Column("DETAIL_VAL", Text, comment="상세정보 텍스트")

    # 홈쇼핑 라이브 목록과 N:1 관계 설정
    live_list = relationship(
        "HomeshoppingList",
        back_populates="detail_infos",
        lazy="select"
    )


class HomeshoppingImgUrl(MariaBase):
    """홈쇼핑 이미지 URL 테이블"""
    __tablename__ = "FCT_HOMESHOPPING_IMG_URL"
    
    img_id = Column("IMG_ID", Integer, primary_key=True, autoincrement=True, comment="이미지 인덱스")
    product_id = Column("PRODUCT_ID", BigInteger, ForeignKey("FCT_HOMESHOPPING_PRODUCT_INFO.PRODUCT_ID"), comment="제품코드")
    sort_order = Column("SORT_ORDER", SMALLINT, comment="이미지 순서")
    img_url = Column("IMG_URL", Text, comment="이미지 URL")

    # 홈쇼핑 라이브 목록과 N:1 관계 설정
    live_list = relationship(
        "HomeshoppingList",
        back_populates="images",
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
    user_id = Column("USER_ID", Integer, nullable=False, comment="사용자 ID (회원 PK 참조)")
    product_id = Column("PRODUCT_ID", BigInteger, ForeignKey("FCT_HOMESHOPPING_PRODUCT_INFO.PRODUCT_ID", ondelete="RESTRICT"), nullable=False, comment="제품 ID (FK)")
    homeshopping_like_created_at = Column("HOMESHOPPING_LIKE_CREATED_AT", DateTime, nullable=False, comment="찜한 시간")

    # 홈쇼핑 라이브 목록과 N:1 관계 설정
    live_list = relationship(
        "HomeshoppingList",
        back_populates="likes",
        lazy="select"
    )


class HomeshoppingNotification(MariaBase):
    """홈쇼핑 알림 테이블"""
    __tablename__ = "HOMESHOPPING_NOTIFICATION"
    
    notification_id = Column("NOTIFICATION_ID", BigInteger, primary_key=True, autoincrement=True, comment="알림 고유번호 (PK)")
    user_id = Column("USER_ID", Integer, nullable=False, comment="알림 대상 사용자 ID (논리 FK, 외래키 제약 없음)")
    homeshopping_order_id = Column("HOMESHOPPING_ORDER_ID", Integer, nullable=False, comment="관련 주문 상세 ID")
    status_id = Column("STATUS_ID", Integer, nullable=False, comment="상태 코드 ID(알림 트리거)")
    title = Column("TITLE", String(100), nullable=False, comment="알림 제목")
    message = Column("MESSAGE", String(255), nullable=False, comment="알림 메시지(상세)")
    created_at = Column("CREATED_AT", DateTime, nullable=False, server_default='current_timestamp()', comment='알림 생성 시각')
