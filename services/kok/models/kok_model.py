"""
콕 쇼핑몰 관련 테이블들의 ORM 모델 정의 모듈
- 변수는 소문자, DB 컬럼명은 대문자로 명시적 매핑
- DB 데이터 정의서 기반으로 변수명 통일
"""

from sqlalchemy import Column, Integer, String, ForeignKey, Float, Text, Boolean, DateTime
from sqlalchemy.orm import relationship

from common.database.base_mariadb import MariaBase

class KokProductInfo(MariaBase):
    """
    FCT_KOK_PRODUCT_INFO 테이블의 ORM 모델
    DB 데이터 정의서 기반으로 변수명 통일
    """
    __tablename__ = "FCT_KOK_PRODUCT_INFO"

    # 🔹 공통 상품 정보 (메인화면 리스트 공통)
    kok_product_id = Column("KOK_PRODUCT_ID", Integer, primary_key=True, autoincrement=False)  # 제품코드
    kok_thumbnail = Column("KOK_THUMBNAIL", Text, nullable=True)  # 썸네일 이미지
    kok_product_name = Column("KOK_PRODUCT_NAME", String(300), nullable=True)  # 상품명
    kok_store_name = Column("KOK_STORE_NAME", String(100), nullable=True)  # 판매자 정보
    kok_product_price = Column("KOK_PRODUCT_PRICE", Integer, nullable=True)  # 상품 원가

    # 🔹 상품 상세 탭 정보
    kok_review_cnt = Column("KOK_REVIEW_CNT", Integer, nullable=True)  # reviewCount

    # 리뷰 관련 정보
    kok_review_score = Column("KOK_REVIEW_SCORE", Float, nullable=True)  # 리뷰 평점 평균
    kok_5_ratio = Column("KOK_5_RATIO", Integer, nullable=True)  # 5점 비율
    kok_4_ratio = Column("KOK_4_RATIO", Integer, nullable=True)  # 4점 비율
    kok_3_ratio = Column("KOK_3_RATIO", Integer, nullable=True)  # 3점 비율
    kok_2_ratio = Column("KOK_2_RATIO", Integer, nullable=True)  # 2점 비율
    kok_1_ratio = Column("KOK_1_RATIO", Integer, nullable=True)  # 1점 비율

    # 평가 정보
    kok_aspect_price = Column("KOK_ASPECT_PRICE", String(30), nullable=True)  # 가격 평가
    kok_aspect_price_ratio = Column("KOK_ASPECT_PRICE_RATIO", Integer, nullable=True)  # 가격 평가 비율
    kok_aspect_delivery = Column("KOK_ASPECT_DELIVERY", String(30), nullable=True)  # 배송 평가
    kok_aspect_delivery_ratio = Column("KOK_ASPECT_DELIVERY_RATIO", Integer, nullable=True)  # 배송 평가 비율
    kok_aspect_taste = Column("KOK_ASPECT_TASTE", String(30), nullable=True)  # 맛 평가
    kok_aspect_taste_ratio = Column("KOK_ASPECT_TASTE_RATIO", Integer, nullable=True)  # 맛 평가 비율

    # 판매자 정보
    kok_seller = Column("KOK_SELLER", String(100), nullable=True)  # 판매자
    kok_co_ceo = Column("KOK_CO_CEO", String(100), nullable=True)  # 상호명/대표자
    kok_co_reg_no = Column("KOK_CO_REG_NO", String(50), nullable=True)  # 사업자등록번호
    kok_co_ec_reg = Column("KOK_CO_EC_REG", String(50), nullable=True)  # 통신판매업신고
    kok_tell = Column("KOK_TELL", String(50), nullable=True)  # 전화번호
    kok_ver_item = Column("KOK_VER_ITEM", String(50), nullable=True)  # 인증완료 항목
    kok_ver_date = Column("KOK_VER_DATE", String(50), nullable=True)  # 인증시기
    kok_co_addr = Column("KOK_CO_ADDR", String(200), nullable=True)  # 영업소재지
    kok_return_addr = Column("KOK_RETURN_ADDR", String(200), nullable=True)  # 반품주소
    kok_exchange_addr = Column("KOK_EXCHANGE_ADDR", String(200), nullable=True)  # 교환주소

    # 이미지 정보와 1:N 관계 설정
    images = relationship(
        "KokImageInfo",
        back_populates="product",
        primaryjoin="KokProductInfo.kok_product_id==KokImageInfo.kok_product_id",
        lazy="select"
    )

    # 상세 정보와 1:N 관계 설정
    detail_infos = relationship(
        "KokDetailInfo",
        back_populates="product",
        primaryjoin="KokProductInfo.kok_product_id==KokDetailInfo.kok_product_id",
        lazy="select"
    )

    # 리뷰 예시와 1:N 관계 설정
    review_examples = relationship(
        "KokReviewExample",
        back_populates="product",
        primaryjoin="KokProductInfo.kok_product_id==KokReviewExample.kok_product_id",
        lazy="select"
    )

    # 가격 정보와 1:N 관계 설정
    price_infos = relationship(
        "KokPriceInfo",
        back_populates="product",
        primaryjoin="KokProductInfo.kok_product_id==KokPriceInfo.kok_product_id",
        lazy="select"
    )

    # 찜과 1:N 관계 설정
    likes = relationship(
        "KokLikes",
        back_populates="product",
        primaryjoin="KokProductInfo.kok_product_id==KokLikes.kok_product_id",
        lazy="select"
    )

    # 장바구니와 1:N 관계 설정
    cart_items = relationship(
        "KokCart",
        back_populates="product",
        primaryjoin="KokProductInfo.kok_product_id==KokCart.kok_product_id",
        lazy="select"
    )



class KokImageInfo(MariaBase):
    """
    FCT_KOK_IMAGE_INFO 테이블의 ORM 모델
    """
    __tablename__ = "FCT_KOK_IMAGE_INFO"

    kok_img_id = Column("KOK_IMG_ID", Integer, primary_key=True, autoincrement=True)  # 이미지 인덱스
    kok_product_id = Column("KOK_PRODUCT_ID", Integer, ForeignKey("FCT_KOK_PRODUCT_INFO.KOK_PRODUCT_ID"), nullable=True)  # 제품코드
    kok_img_url = Column("KOK_IMG_URL", Text, nullable=True)  # 이미지 URL

    # 제품 정보와 N:1 관계 설정
    product = relationship(
        "KokProductInfo",
        back_populates="images",
        lazy="select"
    )

class KokDetailInfo(MariaBase):
    """
    FCT_KOK_DETAIL_INFO 테이블의 ORM 모델
    """
    __tablename__ = "FCT_KOK_DETAIL_INFO"

    kok_detail_col_id = Column("KOK_DETAIL_COL_ID", Integer, primary_key=True, autoincrement=True)  # 상세정보 컬럼 인덱스
    kok_product_id = Column("KOK_PRODUCT_ID", Integer, ForeignKey("FCT_KOK_PRODUCT_INFO.KOK_PRODUCT_ID"), nullable=True)  # 제품 코드
    kok_detail_col = Column("KOK_DETAIL_COL", Text, nullable=True)  # 상세정보 컬럼명
    kok_detail_val = Column("KOK_DETAIL_VAL", Text, nullable=True)  # 상세정보 내용

    # 제품 정보와 N:1 관계 설정
    product = relationship(
        "KokProductInfo",
        back_populates="detail_infos",
        lazy="select"
    )

class KokReviewExample(MariaBase):
    """
    FCT_KOK_REVIEW_EXAMPLE 테이블의 ORM 모델
    """
    __tablename__ = "FCT_KOK_REVIEW_EXAMPLE"

    kok_review_id = Column("KOK_REVIEW_ID", Integer, primary_key=True, autoincrement=True)  # 리뷰 인덱스
    kok_product_id = Column("KOK_PRODUCT_ID", Integer, ForeignKey("FCT_KOK_PRODUCT_INFO.KOK_PRODUCT_ID"), nullable=True)  # 제품 코드
    kok_nickname = Column("KOK_NICKNAME", String(30), nullable=True)  # 작성자 닉네임
    kok_review_text = Column("KOK_REVIEW_TEXT", Text, nullable=True)  # 리뷰 전문
    kok_review_date = Column("KOK_REVIEW_DATE", String(30), nullable=True)  # 작성일
    kok_review_score = Column("KOK_REVIEW_SCORE", Integer, nullable=True)  # 리뷰 점수
    kok_price_eval = Column("KOK_PRICE_EVAL", String(30), nullable=True)  # 가격 평가
    kok_delivery_eval = Column("KOK_DELIVERY_EVAL", String(30), nullable=True)  # 배송 평가
    kok_taste_eval = Column("KOK_TASTE_EVAL", String(30), nullable=True)  # 맛 평가

    # 제품 정보와 N:1 관계 설정
    product = relationship(
        "KokProductInfo",
        back_populates="review_examples",
        lazy="select"
    )

class KokPriceInfo(MariaBase):
    """
    FCT_KOK_PRICE_INFO 테이블의 ORM 모델
    """
    __tablename__ = "FCT_KOK_PRICE_INFO"

    kok_price_id = Column("KOK_PRICE_ID", Integer, primary_key=True, autoincrement=True)  # 가격 인덱스
    kok_product_id = Column("KOK_PRODUCT_ID", Integer, ForeignKey("FCT_KOK_PRODUCT_INFO.KOK_PRODUCT_ID"), nullable=True)  # 상품 인덱스
    kok_discount_rate = Column("KOK_DISCOUNT_RATE", Integer, nullable=True)  # 할인율
    kok_discounted_price = Column("KOK_DISCOUNTED_PRICE", Integer, nullable=True)  # 할인적용가격

    # 제품 정보와 N:1 관계 설정
    product = relationship(
        "KokProductInfo",
        back_populates="price_infos",
        lazy="select"
    )

class KokSearchHistory(MariaBase):
    """
    KOK_SEARCH_HISTORY 테이블의 ORM 모델
    """
    __tablename__ = "KOK_SEARCH_HISTORY"

    kok_history_id = Column("KOK_HISTORY_ID", Integer, primary_key=True, autoincrement=True)  # 검색 이력 ID
    user_id = Column("USER_ID", Integer, nullable=False)  # 사용자 ID (회원 PK 참조)
    kok_keyword = Column("KOK_KEYWORD", String(100), nullable=False)  # 검색 키워드
    kok_searched_at = Column("KOK_SEARCHED_AT", String(20), nullable=False)  # 검색 시간

class KokLikes(MariaBase):
    """
    KOK_LIKES 테이블의 ORM 모델
    """
    __tablename__ = "KOK_LIKES"

    kok_like_id = Column("KOK_LIKE_ID", Integer, primary_key=True, autoincrement=True)  # 찜 ID
    user_id = Column("USER_ID", Integer, nullable=False)  # 사용자 ID (회원 PK 참조)
    kok_product_id = Column("KOK_PRODUCT_ID", Integer, ForeignKey("FCT_KOK_PRODUCT_INFO.KOK_PRODUCT_ID"), nullable=False)  # 제품 ID
    kok_created_at = Column("KOK_CREATED_AT", String(20), nullable=False)  # 찜한 시간

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
    kok_created_at = Column("KOK_CREATED_AT", String(20), nullable=True)  # 추가 시간

    # 제품 정보와 N:1 관계 설정
    product = relationship(
        "KokProductInfo",
        back_populates="cart_items",
        lazy="select"
    )



