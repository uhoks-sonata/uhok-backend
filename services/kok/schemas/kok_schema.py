"""
콕 쇼핑몰 응답/요청용 Pydantic 스키마 모듈
- 모든 필드/변수는 소문자
- DB ORM과 분리, API 직렬화/유효성 검증용
- DB 데이터 정의서 기반으로 변수명 통일 (KOK_ 접두사 제거 후 소문자)
"""

from pydantic import BaseModel, Field
from typing import Optional, List

# -----------------------------
# 이미지 정보 스키마
# -----------------------------

class KokImageInfo(BaseModel):
    """이미지 정보"""
    kok_img_id: int
    kok_product_id: Optional[int] = None
    kok_img_url: Optional[str] = None
    
    class Config:
        from_attributes = True

# -----------------------------
# 상세 정보 스키마
# -----------------------------

class KokDetailInfo(BaseModel):
    """상세 정보"""
    kok_detail_col_id: int
    kok_product_id: Optional[int] = None
    kok_detail_col: Optional[str] = None
    kok_detail_val: Optional[str] = None
    
    class Config:
        from_attributes = True

# -----------------------------
# 리뷰 스키마
# -----------------------------

class KokReviewExample(BaseModel):
    """리뷰 예시 정보"""
    kok_review_id: int
    kok_product_id: Optional[int] = None
    kok_nickname: Optional[str] = None  # 작성자 닉네임
    kok_review_text: Optional[str] = None  # 리뷰 전문
    kok_review_date: Optional[str] = None  # 작성일
    kok_review_score: Optional[int] = None
    kok_price_eval: Optional[str] = None
    kok_delivery_eval: Optional[str] = None
    kok_taste_eval: Optional[str] = None
    
    class Config:
        from_attributes = True

class KokReviewStats(BaseModel):
    """리뷰 통계 정보 (KOK_PRODUCT_INFO 테이블에서)"""
    kok_review_score: Optional[float] = None  # 리뷰 평점 평균
    kok_review_cnt: Optional[int] = None  # 리뷰 개수
    kok_5_ratio: Optional[int] = None  # 5점 비율
    kok_4_ratio: Optional[int] = None  # 4점 비율
    kok_3_ratio: Optional[int] = None  # 3점 비율
    kok_2_ratio: Optional[int] = None  # 2점 비율
    kok_1_ratio: Optional[int] = None  # 1점 비율
    kok_aspect_price: Optional[str] = None  # 가격 평가
    kok_aspect_price_ratio: Optional[int] = None  # 가격 평가 비율
    kok_aspect_delivery: Optional[str] = None  # 배송 평가
    kok_aspect_delivery_ratio: Optional[int] = None  # 배송 평가 비율
    kok_aspect_taste: Optional[str] = None  # 맛 평가
    kok_aspect_taste_ratio: Optional[int] = None  # 맛 평가 비율
    
    class Config:
        from_attributes = True

class KokReviewDetail(BaseModel):
    """개별 리뷰 상세 정보 (KOK_REVIEW_EXAMPLE 테이블에서)"""
    kok_review_id: int  # 리뷰 인덱스
    kok_product_id: Optional[int] = None  # 제품 코드
    kok_nickname: Optional[str] = None  # 작성자 닉네임
    kok_review_date: Optional[str] = None  # 작성일
    kok_review_score: Optional[int] = None  # 리뷰 점수
    kok_price_eval: Optional[str] = None  # 가격 평가
    kok_delivery_eval: Optional[str] = None  # 배송 평가
    kok_taste_eval: Optional[str] = None  # 맛 평가
    kok_review_text: Optional[str] = None  # 리뷰 전문
    
    class Config:
        from_attributes = True

class KokReviewResponse(BaseModel):
    """리뷰 API 응답"""
    # KOK_PRODUCT_INFO 테이블에서 가져온 통계 정보
    stats: KokReviewStats
    
    # KOK_REVIEW_EXAMPLE 테이블에서 가져온 개별 리뷰 목록
    reviews: List[KokReviewDetail] = Field(default_factory=list)
    
    class Config:
        from_attributes = True

# -----------------------------
# 가격 정보 스키마
# -----------------------------

class KokPriceInfo(BaseModel):
    """가격 정보"""
    kok_price_id: int
    kok_product_id: Optional[int] = None
    kok_discount_rate: Optional[int] = None
    kok_discounted_price: Optional[int] = None
    
    class Config:
        from_attributes = True



# -----------------------------
# 제품 기본/목록/상세 스키마
# -----------------------------

class KokProductBase(BaseModel):
    """제품 기본 정보"""
    # 🔹 공통 상품 정보 (메인화면 리스트 공통)
    kok_product_id: int  # 제품코드
    kok_thumbnail: Optional[str] = None  # 썸네일 이미지
    kok_product_name: Optional[str] = None  # 상품명
    kok_store_name: Optional[str] = None  # 판매자 정보
    kok_product_price: Optional[int] = None  # 상품 원가
    kok_discount_rate: Optional[int] = None  # 할인율
    
    # 🔹 상품 상세 탭 정보
    kok_description: Optional[str] = None  # description (HTML 형식 상품 설명)
    kok_review_cnt: Optional[int] = None  # reviewCount
    
    # 리뷰 관련 정보
    kok_review_score: Optional[float] = None  # 리뷰 평점 평균
    kok_5_ratio: Optional[int] = None  # 5점 비율
    kok_4_ratio: Optional[int] = None  # 4점 비율
    kok_3_ratio: Optional[int] = None  # 3점 비율
    kok_2_ratio: Optional[int] = None  # 2점 비율
    kok_1_ratio: Optional[int] = None  # 1점 비율
    
    # 평가 정보
    kok_aspect_price: Optional[str] = None  # 가격 평가
    kok_aspect_price_ratio: Optional[int] = None  # 가격 평가 비율
    kok_aspect_delivery: Optional[str] = None  # 배송 평가
    kok_aspect_delivery_ratio: Optional[int] = None  # 배송 평가 비율
    kok_aspect_taste: Optional[str] = None  # 맛 평가
    kok_aspect_taste_ratio: Optional[int] = None  # 맛 평가 비율
    
    # 판매자 정보
    kok_seller: Optional[str] = None  # 판매자
    kok_co_ceo: Optional[str] = None  # 상호명/대표자
    kok_co_reg_no: Optional[str] = None  # 사업자등록번호
    kok_co_ec_reg: Optional[str] = None  # 통신판매업신고
    kok_tell: Optional[str] = None  # 전화번호
    kok_ver_item: Optional[str] = None  # 인증완료 항목
    kok_ver_date: Optional[str] = None  # 인증시기
    kok_co_addr: Optional[str] = None  # 영업소재지
    kok_return_addr: Optional[str] = None  # 반품주소
    kok_exchange_addr: Optional[str] = None  # 교환주소
    
    class Config:
        from_attributes = True

class KokProductDetailResponse(KokProductBase):
    """제품 상세 응답(이미지, 상세정보, 리뷰, 가격, Q&A 포함)"""
    images: List[KokImageInfo] = Field(default_factory=list)
    detail_infos: List[KokDetailInfo] = Field(default_factory=list)
    review_examples: List[KokReviewExample] = Field(default_factory=list)
    price_infos: List[KokPriceInfo] = Field(default_factory=list)


class KokProductInfoResponse(BaseModel):
    """상품 기본 정보 응답"""
    kok_product_id: str
    kok_product_name: str
    kok_store_name: str
    kok_thumbnail: str
    kok_product_price: int
    kok_discount_rate: int
    kok_discounted_price: int
    kok_review_cnt: int
    
    class Config:
        from_attributes = True

class KokProductTabsResponse(BaseModel):
    """상품 탭 정보 응답"""
    images: List[dict] = Field(default_factory=list)

# -----------------------------
# 제품 목록 응답 스키마
# -----------------------------

class KokProductListResponse(BaseModel):
    """제품 목록 응답"""
    items: List[KokProductBase] = Field(default_factory=list)
    total: int
    page: int
    size: int

# -----------------------------
# 검색 요청 스키마
# -----------------------------

class KokSearchRequest(BaseModel):
    """제품 검색 요청"""
    keyword: Optional[str] = None
    page: int = 1
    size: int = 10
    sort_by: Optional[str] = None  # price, review_score, review_count 등
    sort_order: Optional[str] = "desc"  # asc, desc

# -----------------------------
# 제품 상세 요청 스키마
# -----------------------------

class KokProductDetailRequest(BaseModel):
    """제품 상세 정보 요청"""
    kok_product_id: int

# -----------------------------
# 리뷰 요청 스키마
# -----------------------------

class KokReviewRequest(BaseModel):
    """리뷰 목록 요청"""
    kok_product_id: int
    page: int = 1
    size: int = 10

# -----------------------------
# Q&A 요청 스키마
# -----------------------------



# -----------------------------
# 검색 이력 스키마
# -----------------------------

class KokSearchHistory(BaseModel):
    """검색 이력"""
    keyword: str
    searched_at: str
    
    class Config:
        from_attributes = True

class KokSearchHistoryResponse(BaseModel):
    """검색 이력 응답"""
    history: List[KokSearchHistory] = Field(default_factory=list)

class KokSearchHistoryCreate(BaseModel):
    """검색 이력 생성"""
    keyword: str

class KokSearchHistoryDelete(BaseModel):
    """검색 이력 삭제"""
    keyword: str

# -----------------------------
# 찜 관련 스키마
# -----------------------------

class KokLikesToggle(BaseModel):
    """찜 토글 요청"""
    kok_product_id: int

class KokLikesResponse(BaseModel):
    """찜 응답"""
    liked: bool
    message: str

class KokLikedProduct(BaseModel):
    """찜한 상품 정보"""
    kok_product_id: int
    kok_product_name: Optional[str] = None
    kok_thumbnail: Optional[str] = None
    kok_product_price: Optional[int] = None
    kok_thumbnail_url: Optional[str] = None
    
    class Config:
        from_attributes = True

class KokLikesListResponse(BaseModel):
    """찜한 상품 목록 응답"""
    liked_products: List[KokLikedProduct] = Field(default_factory=list)

# -----------------------------
# 장바구니 관련 스키마
# -----------------------------

class KokCartToggle(BaseModel):
    """장바구니 토글 요청"""
    kok_product_id: int

class KokCartResponse(BaseModel):
    """장바구니 응답"""
    in_cart: bool
    message: str

class KokCartItem(BaseModel):
    """장바구니 상품 정보"""
    kok_product_id: int
    kok_product_name: Optional[str] = None
    kok_thumbnail: Optional[str] = None
    kok_product_price: Optional[int] = None
    kok_quantity: Optional[int] = None
    
    class Config:
        from_attributes = True

class KokCartListResponse(BaseModel):
    """장바구니 목록 응답"""
    cart_items: List[KokCartItem] = Field(default_factory=list)

# -----------------------------
# 메인화면 상품 리스트 스키마
# -----------------------------

class KokDiscountedProductsResponse(BaseModel):
    """할인 특가 상품 응답"""
    products: List[KokProductBase] = Field(default_factory=list)

class KokTopSellingProductsResponse(BaseModel):
    """판매율 높은 상품 응답"""
    products: List[KokProductBase] = Field(default_factory=list)

class KokUnpurchasedResponse(BaseModel):
    """미구매 상품 응답"""
    products: List[KokProductBase] = Field(default_factory=list)


# -----------------------------
# 구매 이력 관련 스키마
# -----------------------------

class KokPurchase(BaseModel):
    """구매 이력 정보"""
    kok_purchase_id: int
    kok_user_id: Optional[int] = None
    kok_product_id: Optional[int] = None
    kok_quantity: Optional[int] = None
    kok_purchase_price: Optional[int] = None
    kok_purchased_at: Optional[str] = None
    
    class Config:
        from_attributes = True

class KokPurchaseHistory(BaseModel):
    """구매 이력 상세 정보"""
    kok_purchase_id: int
    kok_product_id: int
    kok_product_name: Optional[str] = None
    kok_thumbnail: Optional[str] = None
    kok_quantity: Optional[int] = None
    kok_purchase_price: Optional[int] = None
    kok_purchased_at: Optional[str] = None
    
    class Config:
        from_attributes = True

class KokPurchaseHistoryResponse(BaseModel):
    """구매 이력 목록 응답"""
    purchase_history: List[KokPurchaseHistory] = Field(default_factory=list)
    total_count: int

class KokPurchaseCreate(BaseModel):
    """구매 이력 생성 요청"""
    kok_product_id: int
    kok_quantity: int = 1
    kok_purchase_price: Optional[int] = None

# -----------------------------
# 상품 상세정보 스키마
# -----------------------------

class KokProductDetails(BaseModel):
    """상품 상세정보 (KOK_PRODUCT_INFO 테이블에서)"""
    kok_co_ceo: Optional[str] = None  # 상호명/대표자
    kok_co_reg_no: Optional[str] = None  # 사업자등록번호
    kok_co_ec_reg: Optional[str] = None  # 통신판매업신고
    kok_tell: Optional[str] = None  # 전화번호
    kok_ver_item: Optional[str] = None  # 인증완료 항목
    kok_ver_date: Optional[str] = None  # 인증시기
    kok_co_addr: Optional[str] = None  # 영업소재지
    kok_return_addr: Optional[str] = None  # 반품주소
    
    class Config:
        from_attributes = True

class KokDetailInfoItem(BaseModel):
    """상세정보 항목 (KOK_DETAIL_INFO 테이블에서)"""
    kok_detail_col: Optional[str] = None  # 상세정보 컬럼명
    kok_detail_val: Optional[str] = None  # 상세정보 내용
    
    class Config:
        from_attributes = True

class KokProductDetailsResponse(BaseModel):
    """상품 상세정보 응답"""
    # KOK_PRODUCT_INFO 테이블에서 가져온 판매자 정보
    seller_info: KokProductDetails
    
    # KOK_DETAIL_INFO 테이블에서 가져온 상세정보 목록
    detail_info: List[KokDetailInfoItem] = Field(default_factory=list)
    
    class Config:
        from_attributes = True
