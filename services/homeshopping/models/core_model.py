from sqlalchemy import BigInteger, Column, Date, Enum, ForeignKey, Integer, SMALLINT, String, Text, Time
from sqlalchemy.orm import relationship

from common.database.base_mariadb import MariaBase

class HomeshoppingInfo(MariaBase):
    """홈쇼핑 정보 테이블"""
    __tablename__ = "HOMESHOPPING_INFO"
    
    homeshopping_id = Column("HOMESHOPPING_ID", SMALLINT, primary_key=True, comment="홈쇼핑 인덱스")
    homeshopping_name = Column("HOMESHOPPING_NAME", String(20), comment="홈쇼핑명")
    homeshopping_channel = Column("HOMESHOPPING_CHANNEL", SMALLINT, comment="홈쇼핑 채널")
    live_url = Column("LIVE_URL", String(200), comment="홈쇼핑 라이브 URL")
    
    # 홈쇼핑 라이브 목록과 1:N 관계 설정
    live_lists = relationship(
        "HomeshoppingList",
        back_populates="homeshopping_info",
        lazy="select"
    )


class HomeshoppingList(MariaBase):
    """홈쇼핑 라이브 목록 테이블"""
    __tablename__ = "FCT_HOMESHOPPING_LIST"
    
    live_id = Column("LIVE_ID", Integer, primary_key=True, comment="라이브 인덱스")
    homeshopping_id = Column("HOMESHOPPING_ID", SMALLINT, ForeignKey("HOMESHOPPING_INFO.HOMESHOPPING_ID"), comment="홈쇼핑 인덱스")
    live_date = Column("LIVE_DATE", Date, comment="방영일")
    live_start_time = Column("LIVE_START_TIME", Time, comment="방영 시작 시간")
    live_end_time = Column("LIVE_END_TIME", Time, comment="방영 종료 시간")
    promotion_type = Column("PROMOTION_TYPE", Enum('main', 'sub', name='promotion_type_enum'), comment="main/sub")
    product_id = Column("PRODUCT_ID", BigInteger, comment="제품 코드")
    product_name = Column("PRODUCT_NAME", Text, comment="제품명")
    thumb_img_url = Column("THUMB_IMG_URL", Text, comment="썸네일 URL")
    scheduled_or_cancelled = Column("SCHEDULED_OR_CANCELLED", Integer, nullable=False, default=1, comment="방송 예정 또는 취소 여부 (1: 예정, 0: 취소)")

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
