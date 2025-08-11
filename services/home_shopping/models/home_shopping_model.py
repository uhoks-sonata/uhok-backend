"""
홈쇼핑 관련 테이블들의 ORM 모델 정의 모듈
- 변수는 소문자, DB 컬럼명은 대문자로 명시적 매핑
- DB 데이터 정의서 기반으로 변수명 통일
"""

from sqlalchemy import Column, Integer, String, DateTime, Text, SmallInt, BigInteger, Enum, ForeignKey
from sqlalchemy.orm import relationship

from common.database.base_mariadb import MariaBase


class HOMESHOPPING_INFO(MariaBase):
    """홈쇼핑 정보 테이블"""
    __tablename__ = "HOMESHOPPING_INFO"
    
    homeshopping_id = Column("HOMESHOPPING_ID", SmallInt, primary_key=True, autoincrement=True, comment="홈쇼핑 인덱스")
    homeshopping_channel_name = Column("HOMESHOPPING_CHANNEL_NAME", String(20), comment="채널명")
    homeshopping_channel_number = Column("HOMSHOPPING_CHANNEL_NUMBER", SmallInt, comment="채널번호")

    # 홈쇼핑 라이브 목록과 1:N 관계 설정
    live_lists = relationship(
        "FCT_HOMESHOPPING_LIST",
        back_populates="homeshopping_info",
        primaryjoin="HOMESHOPPING_INFO.homeshopping_id==FCT_HOMESHOPPING_LIST.homeshopping_id",
        lazy="select"
    )


class FCT_HOMESHOPPING_PRODUCT_INFO(MariaBase):
    """홈쇼핑 제품 정보 테이블"""
    __tablename__ = "FCT_HOMESHOPPING_PRODUCT_INFO"
    
    product_id = Column("PRODUCT_ID", String(15), primary_key=True, comment="제품코드")
    store_name = Column("STORE_NAME", Text, comment="판매자 정보")
    product_name = Column("PRODUCT_NAME", Text, comment="제품명")
    sale_price = Column("SALE_PRICE", BigInteger, comment="원가")
    dc_rate = Column("DC_RATE", BigInteger, comment="할인율")
    dc_price = Column("DC_PRICE", BigInteger, comment="판매가")
    delivery_fee = Column("DELIVERY_FEE", Text, comment="배송비")
    delivery_co = Column("DELIVERY_CO", Text, comment="택배사명")
    return_exchange = Column("RETURN_EXCHANGE", Text, comment="교환/반품 정보")
    term = Column("TERM", Text, comment="소비기한")

    # 홈쇼핑 라이브 목록과 1:N 관계 설정
    live_lists = relationship(
        "FCT_HOMESHOPPING_LIST",
        back_populates="product_info",
        lazy="select"
    )

    # 상세 정보와 1:N 관계 설정
    detail_infos = relationship(
        "FCT_HOMESHOPPING_DETAIL_INFO",
        back_populates="product_info",
        lazy="select"
    )

    # 이미지와 1:N 관계 설정
    images = relationship(
        "FCT_HOMESHOPPING_IMG_URL",
        back_populates="product_info",
        lazy="select"
    )


class FCT_HOMESHOPPING_LIST(MariaBase):
    """홈쇼핑 라이브 목록 테이블"""
    __tablename__ = "FCT_HOMESHOPPING_LIST"
    
    live_id = Column("LIVE_ID", Integer, primary_key=True, autoincrement=True, comment="라이브 인덱스")
    homeshopping_id = Column("HOMESHOPPING_ID", SmallInt, ForeignKey("HOMESHOPPING_INFO.HOMESHOPPING_ID"), comment="홈쇼핑 인덱스")
    live_date = Column("LIVE_DATE", DateTime, comment="방영일")
    live_time = Column("LIVE_TIME", String(20), comment="방영시간")
    promotion_type = Column("PROMOTION_TYPE", Enum('main', 'sub', name='promotion_type_enum'), comment="main/sub")
    live_title = Column("LIVE_TITLE", Text, nullable=True, comment="방송제목")
    product_id = Column("PRODUCT_ID", String(20), ForeignKey("FCT_HOMESHOPPING_PRODUCT_INFO.PRODUCT_ID"), comment="제품 코드")
    product_name = Column("PRODUCT_NAME", Text, comment="제품명")
    sale_price = Column("SALE_PRICE", BigInteger, comment="판매 원가")
    dc_price = Column("DC_PRICE", BigInteger, comment="할인가")
    dc_rate = Column("DC_RATE", BigInteger, comment="할인율")
    thumb_img_url = Column("THUMB_IMG_URL", Text, comment="썸네일 URL")

    # 홈쇼핑 정보와 N:1 관계 설정
    homeshopping_info = relationship(
        "HOMESHOPPING_INFO",
        back_populates="live_lists",
        lazy="select"
    )

    # 제품 정보와 N:1 관계 설정
    product_info = relationship(
        "FCT_HOMESHOPPING_PRODUCT_INFO",
        back_populates="live_lists",
        lazy="select"
    )

    # 상세 정보와 1:N 관계 설정
    detail_infos = relationship(
        "FCT_HOMESHOPPING_DETAIL_INFO",
        back_populates="live_list",
        primaryjoin="FCT_HOMESHOPPING_LIST.product_id==FCT_HOMESHOPPING_DETAIL_INFO.product_id",
        lazy="select"
    )

    # 이미지와 1:N 관계 설정
    images = relationship(
        "FCT_HOMESHOPPING_IMG_URL",
        back_populates="live_list",
        primaryjoin="FCT_HOMESHOPPING_LIST.product_id==FCT_HOMESHOPPING_IMG_URL.product_id",
        lazy="select"
    )


class FCT_HOMESHOPPING_DETAIL_INFO(MariaBase):
    """홈쇼핑 상세 정보 테이블"""
    __tablename__ = "FCT_HOMESHOPPING_DETAIL_INFO"
    
    detail_id = Column("DETAIL_ID", Integer, primary_key=True, autoincrement=True, comment="상세정보 인덱스")
    product_id = Column("PRODUCT_ID", String(20), ForeignKey("FCT_HOMESHOPPING_PRODUCT_INFO.PRODUCT_ID"), comment="제품 코드")
    detail_col = Column("DETAIL_COL", Text, comment="상세정보 컬럼명")
    detail_val = Column("DETAIL_VAL", Text, comment="상세정보 텍스트")

    # 홈쇼핑 라이브 목록과 N:1 관계 설정
    live_list = relationship(
        "FCT_HOMESHOPPING_LIST",
        back_populates="detail_infos",
        lazy="select"
    )

    # 제품 정보와 N:1 관계 설정
    product_info = relationship(
        "FCT_HOMESHOPPING_PRODUCT_INFO",
        back_populates="detail_infos",
        lazy="select"
    )


class FCT_HOMESHOPPING_IMG_URL(MariaBase):
    """홈쇼핑 이미지 URL 테이블"""
    __tablename__ = "FCT_HOMESHOPPING_IMG_URL"
    
    img_id = Column("IMG_ID", Integer, primary_key=True, autoincrement=True, comment="이미지 인덱스")
    product_id = Column("PRODUCT_ID", String(20), ForeignKey("FCT_HOMESHOPPING_PRODUCT_INFO.PRODUCT_ID"), comment="제품코드")
    sort_order = Column("SORT_ORDER", SmallInt, comment="이미지 순서")
    img_url = Column("IMG_URL", Text, comment="이미지 URL")

    # 홈쇼핑 라이브 목록과 N:1 관계 설정
    live_list = relationship(
        "FCT_HOMESHOPPING_LIST",
        back_populates="images",
        lazy="select"
    )

    # 제품 정보와 N:1 관계 설정
    product_info = relationship(
        "FCT_HOMESHOPPING_PRODUCT_INFO",
        back_populates="images",
        lazy="select"
    )
