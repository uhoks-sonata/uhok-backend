"""
콕 쇼핑몰 관련 테이블들의 ORM 모델 정의 모듈
- 변수는 소문자, DB 컬럼명은 대문자로 명시적 매핑
- API 명세서의 변수명을 기반으로 매핑
"""

from sqlalchemy import Column, Integer, String, ForeignKey, Float, Text, Boolean, DateTime
from sqlalchemy.orm import relationship

from common.database.base_mariadb import MariaBase

class KokProductInfo(MariaBase):
    """
    KOK_PRODUCT_INFO 테이블의 ORM 모델
    변수명은 소문자, DB 컬럼은 대문자 매핑
    API 명세서: productId, productImage, productName, brandName, price, discountRate
    """
    __tablename__ = "KOK_PRODUCT_INFO"

    # 🔹 공통 상품 정보 (메인화면 리스트 공통)
    product_id = Column("KOK_PRODUCT_ID", Integer, primary_key=True, autoincrement=False)  # productId
    product_image = Column("KOK_THUMBNAIL", String(200), nullable=True)  # productImage
    product_name = Column("KOK_PRODUCT_NAME", String(100), nullable=True)  # productName
    brand_name = Column("KOK_STORE_NAME", String(30), nullable=True)  # brandName
    price = Column("KOK_PRODUCT_PRICE", Integer, nullable=True)  # price
    discount_rate = Column("KOK_DISCOUNT_RATE", Integer, nullable=True)  # discountRate

    # 🔹 상품 상세 탭 정보
    description = Column("KOK_DESCRIPTION", Text, nullable=True)  # description (HTML 형식 상품 설명)
    review_count = Column("KOK_REVIEW_CNT", Integer, nullable=True)  # reviewCount
    qna_count = Column("KOK_QNA_CNT", Integer, nullable=True)  # qnaCount

    # 리뷰 관련 정보
    review_score = Column("KOK_REVIEW_SCORE", Float, nullable=True)  # 리뷰 평점 평균
    kok_5_ratio = Column("KOK_5_RATIO", Integer, nullable=True)  # 5점 비율
    kok_4_ratio = Column("KOK_4_RATIO", Integer, nullable=True)  # 4점 비율
    kok_3_ratio = Column("KOK_3_RATIO", Integer, nullable=True)  # 3점 비율
    kok_2_ratio = Column("KOK_2_RATIO", Integer, nullable=True)  # 2점 비율
    kok_1_ratio = Column("KOK_1_RATIO", Integer, nullable=True)  # 1점 비율

    # 평가 정보
    aspect_price = Column("KOK_ASPECT_PRICE", String(20), nullable=True)  # 가격 평가
    aspect_price_ratio = Column("KOK_ASPECT_PRICE_RATIO", Integer, nullable=True)  # 가격 평가 비율
    aspect_delivery = Column("KOK_ASPECT_DELIVERY", String(20), nullable=True)  # 배송 평가
    aspect_delivery_ratio = Column("KOK_ASPECT_DELIVERY_RATIO", Integer, nullable=True)  # 배송 평가 비율
    aspect_taste = Column("KOK_ASPECT_TASTE", String(20), nullable=True)  # 맛 평가
    aspect_taste_ratio = Column("KOK_ASPECT_TASTE_RATIO", Integer, nullable=True)  # 맛 평가 비율

    # 판매자 정보
    seller = Column("KOK_SELLER", String(100), nullable=True)  # 판매자
    co_ceo = Column("KOK_CO_CEO", String(30), nullable=True)  # 상호명/대표자
    co_reg_no = Column("KOK_CO_REG_NO", String(15), nullable=True)  # 사업자등록번호
    co_ec_reg = Column("KOK_CO_EC_REG", String(50), nullable=True)  # 통신판매업신고
    tell = Column("KOK_TELL", String(20), nullable=True)  # 전화번호
    ver_item = Column("KOK_VER_ITEM", String(50), nullable=True)  # 인증완료 항목
    ver_date = Column("KOK_VER_DATE", String(10), nullable=True)  # 인증시기
    co_addr = Column("KOK_CO_ADDR", String(100), nullable=True)  # 영업소재지
    return_addr = Column("KOK_RETURN_ADDR", String(100), nullable=True)  # 반품주소
    exchange_addr = Column("KOK_EXCHANGE_ADDR", String(100), nullable=True)  # 교환주소

    # 이미지 정보와 1:N 관계 설정
    images = relationship(
        "KokImageInfo",
        back_populates="product",
        primaryjoin="KokProductInfo.product_id==KokImageInfo.product_id",
        lazy="joined"
    )

    # 상세 정보와 1:N 관계 설정
    detail_infos = relationship(
        "KokDetailInfo",
        back_populates="product",
        primaryjoin="KokProductInfo.product_id==KokDetailInfo.product_id",
        lazy="joined"
    )

    # 리뷰 예시와 1:N 관계 설정
    review_examples = relationship(
        "KokReviewExample",
        back_populates="product",
        primaryjoin="KokProductInfo.product_id==KokReviewExample.product_id",
        lazy="joined"
    )

    # 가격 정보와 1:N 관계 설정
    price_infos = relationship(
        "KokPriceInfo",
        back_populates="product",
        primaryjoin="KokProductInfo.product_id==KokPriceInfo.product_id",
        lazy="joined"
    )

    # Q&A와 1:N 관계 설정
    qna_list = relationship(
        "KokQna",
        back_populates="product",
        primaryjoin="KokProductInfo.product_id==KokQna.product_id",
        lazy="joined"
    )

    # 찜과 1:N 관계 설정
    likes = relationship(
        "KokLikes",
        back_populates="product",
        primaryjoin="KokProductInfo.product_id==KokLikes.product_id",
        lazy="joined"
    )

    # 장바구니와 1:N 관계 설정
    cart_items = relationship(
        "KokCart",
        back_populates="product",
        primaryjoin="KokProductInfo.product_id==KokCart.product_id",
        lazy="joined"
    )

    # 구매 이력과 1:N 관계 설정
    purchases = relationship(
        "KokPurchase",
        back_populates="product",
        primaryjoin="KokProductInfo.product_id==KokPurchase.product_id",
        lazy="joined"
    )

    # 구매 이력과 1:N 관계 설정
    purchases = relationship(
        "KokPurchase",
        back_populates="product",
        primaryjoin="KokProductInfo.product_id==KokPurchase.product_id",
        lazy="joined"
    )

class KokImageInfo(MariaBase):
    """
    KOK_IMAGE_INFO 테이블의 ORM 모델
    변수명은 소문자, DB 컬럼은 대문자로 매핑
    """
    __tablename__ = "KOK_IMAGE_INFO"

    img_id = Column("KOK_IMG_ID", Integer, primary_key=True, autoincrement=True)  # 이미지 인덱스
    product_id = Column("KOK_PRODUCT_ID", Integer, ForeignKey("KOK_PRODUCT_INFO.KOK_PRODUCT_ID"), nullable=True)  # 제품코드
    img_url = Column("KOK_IMG_URL", String(500), nullable=True)  # 이미지 URL

    # 제품 정보와 N:1 관계 설정
    product = relationship(
        "KokProductInfo",
        back_populates="images",
        lazy="joined"
    )

class KokDetailInfo(MariaBase):
    """
    KOK_DETAIL_INFO 테이블의 ORM 모델
    변수명은 소문자, DB 컬럼은 대문자로 매핑
    """
    __tablename__ = "KOK_DETAIL_INFO"

    detail_col_id = Column("KOK_DETAIL_COL_ID", Integer, primary_key=True, autoincrement=True)  # 상세정보 컬럼 인덱스
    product_id = Column("KOK_PRODUCT_ID", Integer, ForeignKey("KOK_PRODUCT_INFO.KOK_PRODUCT_ID"), nullable=True)  # 제품 코드
    detail_col = Column("KOK_DETAIL_COL", String(100), nullable=True)  # 상세정보 컬럼명
    detail_val = Column("KOK_DETAIL_VAL", String(100), nullable=True)  # 상세정보 내용

    # 제품 정보와 N:1 관계 설정
    product = relationship(
        "KokProductInfo",
        back_populates="detail_infos",
        lazy="joined"
    )

class KokReviewExample(MariaBase):
    """
    KOK_REVIEW_EXAMPLE 테이블의 ORM 모델
    변수명은 소문자, DB 컬럼은 대문자로 매핑
    API 명세서: userName, content, createdAt
    """
    __tablename__ = "KOK_REVIEW_EXAMPLE"

    review_id = Column("KOK_REVIEW_ID", Integer, primary_key=True, autoincrement=True)  # 리뷰 인덱스
    product_id = Column("KOK_PRODUCT_ID", Integer, ForeignKey("KOK_PRODUCT_INFO.KOK_PRODUCT_ID"), nullable=True)  # 제품 코드
    user_name = Column("KOK_NICKNAME", String(15), nullable=True)  # userName - 작성자 닉네임
    content = Column("KOK_REVIEW_TEXT", String(4000), nullable=True)  # content - 리뷰 전문
    created_at = Column("KOK_REVIEW_DATE", String(15), nullable=True)  # createdAt - 작성일
    review_score = Column("KOK_REVIEW_SCORE", Integer, nullable=True)  # 리뷰 점수
    price_eval = Column("KOK_PRICE_EVAL", String(20), nullable=True)  # 가격 평가
    delivery_eval = Column("KOK_DELIVERY_EVAL", String(20), nullable=True)  # 배송 평가
    taste_eval = Column("KOK_TASTE_EVAL", String(20), nullable=True)  # 맛 평가

    # 제품 정보와 N:1 관계 설정
    product = relationship(
        "KokProductInfo",
        back_populates="review_examples",
        lazy="joined"
    )

class KokPriceInfo(MariaBase):
    """
    KOK_PRICE_INFO 테이블의 ORM 모델
    변수명은 소문자, DB 컬럼은 대문자로 매핑
    """
    __tablename__ = "KOK_PRICE_INFO"

    price_id = Column("KOK_PRICE_ID", Integer, primary_key=True, autoincrement=True)  # 가격 인덱스
    product_id = Column("KOK_PRODUCT_ID", Integer, ForeignKey("KOK_PRODUCT_INFO.KOK_PRODUCT_ID"), nullable=True)  # 상품 인덱스
    discount_rate = Column("KOK_DISCOUNT_RATE", Integer, nullable=True)  # 할인율
    discounted_price = Column("KOK_DISCOUNTED_PRICE", Integer, nullable=True)  # 할인적용가격

    # 제품 정보와 N:1 관계 설정
    product = relationship(
        "KokProductInfo",
        back_populates="price_infos",
        lazy="joined"
    )

class KokQna(MariaBase):
    """
    KOK_QNA 테이블의 ORM 모델 (API 명세서 기반 추가)
    변수명은 소문자, DB 컬럼은 대문자로 매핑
    API 명세서: qnaId, question, answer, isAnswered, author, createdAt, answeredAt
    """
    __tablename__ = "KOK_QNA"

    qna_id = Column("KOK_QNA_ID", Integer, primary_key=True, autoincrement=True)  # qnaId - Q&A ID
    product_id = Column("KOK_PRODUCT_ID", Integer, ForeignKey("KOK_PRODUCT_INFO.KOK_PRODUCT_ID"), nullable=True)  # 제품 코드
    question = Column("KOK_QUESTION", String(2000), nullable=True)  # question - 질문
    answer = Column("KOK_ANSWER", String(2000), nullable=True)  # answer - 답변 (없으면 null)
    is_answered = Column("KOK_IS_ANSWERED", Boolean, nullable=True)  # isAnswered - 답변 여부
    author = Column("KOK_AUTHOR", String(50), nullable=True)  # author - 작성자
    created_at = Column("KOK_CREATED_AT", String(15), nullable=True)  # createdAt - 질문 작성일
    answered_at = Column("KOK_ANSWERED_AT", String(15), nullable=True)  # answeredAt - 답변 작성일

    # 제품 정보와 N:1 관계 설정
    product = relationship(
        "KokProductInfo",
        back_populates="qna_list",
        lazy="joined"
    )

class KokSearchHistory(MariaBase):
    """
    KOK_SEARCH_HISTORY 테이블의 ORM 모델
    변수명은 소문자, DB 컬럼은 대문자로 매핑
    """
    __tablename__ = "KOK_SEARCH_HISTORY"

    history_id = Column("KOK_HISTORY_ID", Integer, primary_key=True, autoincrement=True)  # 검색 이력 ID
    user_id = Column("KOK_USER_ID", Integer, nullable=True)  # 사용자 ID
    keyword = Column("KOK_KEYWORD", String(100), nullable=True)  # 검색 키워드
    searched_at = Column("KOK_SEARCHED_AT", String(20), nullable=True)  # 검색 시간

class KokLikes(MariaBase):
    """
    KOK_LIKES 테이블의 ORM 모델
    변수명은 소문자, DB 컬럼은 대문자로 매핑
    """
    __tablename__ = "KOK_LIKES"

    like_id = Column("KOK_LIKE_ID", Integer, primary_key=True, autoincrement=True)  # 찜 ID
    user_id = Column("KOK_USER_ID", Integer, nullable=True)  # 사용자 ID
    product_id = Column("KOK_PRODUCT_ID", Integer, ForeignKey("KOK_PRODUCT_INFO.KOK_PRODUCT_ID"), nullable=True)  # 제품 ID
    created_at = Column("KOK_CREATED_AT", String(20), nullable=True)  # 찜한 시간

    # 제품 정보와 N:1 관계 설정
    product = relationship(
        "KokProductInfo",
        back_populates="likes",
        lazy="joined"
    )

class KokCart(MariaBase):
    """
    KOK_CART 테이블의 ORM 모델
    변수명은 소문자, DB 컬럼은 대문자로 매핑
    """
    __tablename__ = "KOK_CART"

    cart_id = Column("KOK_CART_ID", Integer, primary_key=True, autoincrement=True)  # 장바구니 ID
    user_id = Column("KOK_USER_ID", Integer, nullable=True)  # 사용자 ID
    product_id = Column("KOK_PRODUCT_ID", Integer, ForeignKey("KOK_PRODUCT_INFO.KOK_PRODUCT_ID"), nullable=True)  # 제품 ID
    quantity = Column("KOK_QUANTITY", Integer, nullable=True)  # 수량
    created_at = Column("KOK_CREATED_AT", String(20), nullable=True)  # 추가 시간

    # 제품 정보와 N:1 관계 설정
    product = relationship(
        "KokProductInfo",
        back_populates="cart_items",
        lazy="joined"
    )


class KokPurchase(MariaBase):
    """
    KOK_PURCHASE 테이블의 ORM 모델 (구매 이력)
    변수명은 소문자, DB 컬럼은 대문자로 매핑
    """
    __tablename__ = "KOK_PURCHASE"

    purchase_id = Column("KOK_PURCHASE_ID", Integer, primary_key=True, autoincrement=True)  # 구매 ID
    user_id = Column("KOK_USER_ID", Integer, nullable=True)  # 사용자 ID
    product_id = Column("KOK_PRODUCT_ID", Integer, ForeignKey("KOK_PRODUCT_INFO.KOK_PRODUCT_ID"), nullable=True)  # 제품 ID
    quantity = Column("KOK_QUANTITY", Integer, nullable=True)  # 구매 수량
    purchase_price = Column("KOK_PURCHASE_PRICE", Integer, nullable=True)  # 구매 가격
    purchased_at = Column("KOK_PURCHASED_AT", String(20), nullable=True)  # 구매 시간

    # 제품 정보와 N:1 관계 설정
    product = relationship(
        "KokProductInfo",
        back_populates="purchases",
        lazy="joined"
    )
