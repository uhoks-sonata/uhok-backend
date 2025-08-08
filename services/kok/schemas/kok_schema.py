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
# 메인화면 상품 리스트 스키마
# -----------------------------

class KokDiscountedProduct(BaseModel):
    """할인 특가 상품 정보"""
    kok_product_id: int
    kok_thumbnail: Optional[str] = None
    kok_discount_rate: Optional[int] = None
    kok_discounted_price: Optional[int] = None
    kok_product_name: Optional[str] = None
    kok_store_name: Optional[str] = None
    
    class Config:
        from_attributes = True

class KokDiscountedProductsResponse(BaseModel):
    """할인 특가 상품 응답"""
    products: List[KokDiscountedProduct] = Field(default_factory=list)

class KokTopSellingProduct(BaseModel):
    """판매율 높은 상품 정보"""
    kok_product_id: int
    kok_thumbnail: Optional[str] = None
    kok_discount_rate: Optional[int] = None
    kok_discounted_price: Optional[int] = None
    kok_product_name: Optional[str] = None
    kok_store_name: Optional[str] = None
    
    class Config:
        from_attributes = True

class KokTopSellingProductsResponse(BaseModel):
    """판매율 높은 상품 응답"""
    products: List[KokTopSellingProduct] = Field(default_factory=list)



class KokUnpurchasedResponse(BaseModel):
    """미구매 상품 응답"""
    products: List[KokProductBase] = Field(default_factory=list)

class KokStoreBestProduct(BaseModel):
    """스토어 베스트 상품 정보"""
    kok_product_id: int
    kok_thumbnail: Optional[str] = None
    kok_discount_rate: Optional[int] = None
    kok_discounted_price: Optional[int] = None
    kok_product_name: Optional[str] = None
    kok_store_name: Optional[str] = None
    
    class Config:
        from_attributes = True

class KokStoreBestProductsResponse(BaseModel):
    """스토어 베스트 상품 응답"""
    products: List[KokStoreBestProduct] = Field(default_factory=list)




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

# -----------------------------
# 찜 관련 스키마
# -----------------------------

class KokLikes(BaseModel):
    """찜 정보"""
    kok_like_id: int
    user_id: int
    kok_product_id: int
    kok_created_at: str
    
    class Config:
        from_attributes = True

class KokLikesToggleRequest(BaseModel):
    """찜 등록/해제 요청"""
    kok_product_id: int

class KokLikesToggleResponse(BaseModel):
    """찜 등록/해제 응답"""
    liked: bool
    message: str

class KokLikedProduct(BaseModel):
    """찜한 상품 정보"""
    kok_product_id: int
    kok_product_name: Optional[str] = None
    kok_thumbnail: Optional[str] = None
    kok_product_price: Optional[int] = None
    kok_discount_rate: Optional[int] = None
    kok_discounted_price: Optional[int] = None
    kok_store_name: Optional[str] = None
    
    class Config:
        from_attributes = True

class KokLikedProductsResponse(BaseModel):
    """찜한 상품 목록 응답"""
    liked_products: List[KokLikedProduct] = Field(default_factory=list)

# -----------------------------
# 장바구니 관련 스키마
# -----------------------------

class KokCart(BaseModel):
    """장바구니 정보"""
    kok_cart_id: int
    user_id: int
    kok_product_id: int
    kok_quantity: int
    kok_created_at: Optional[str] = None
    kok_is_selected: bool = True  # 선택 여부 (기본값: 선택됨)
    
    class Config:
        from_attributes = True

# 새로운 장바구니 스키마들
class KokCartAddRequest(BaseModel):
    """장바구니 추가 요청 (수량은 1개로 고정)"""
    kok_product_id: int
    kok_quantity: int = Field(1, description="수량 (항상 1개로 고정됨)")

class KokCartAddResponse(BaseModel):
    """장바구니 추가 응답"""
    kok_cart_id: int
    message: str



class KokCartUpdateResponse(BaseModel):
    """장바구니 수량 변경 응답"""
    kok_cart_id: int
    kok_quantity: int
    message: str

class KokCartDeleteResponse(BaseModel):
    """장바구니 삭제 응답"""
    message: str

# 기존 스키마들 (하위 호환성을 위해 유지)
class KokCartItem(BaseModel):
    """장바구니 상품 정보"""
    kok_cart_id: int
    kok_product_id: int
    kok_product_name: Optional[str] = None
    kok_thumbnail: Optional[str] = None
    kok_product_price: Optional[int] = None
    kok_discount_rate: Optional[int] = None
    kok_discounted_price: Optional[int] = None
    kok_store_name: Optional[str] = None
    kok_quantity: int
    kok_is_selected: bool = True
    
    class Config:
        from_attributes = True

class KokCartItemsResponse(BaseModel):
    """장바구니 상품 목록 응답"""
    cart_items: List[KokCartItem] = Field(default_factory=list)

# 새로운 주문 관련 스키마
class KokCartOrderItem(BaseModel):
    """주문할 장바구니 상품 정보"""
    cart_id: int = Field(..., description="장바구니 항목 ID")
    quantity: int = Field(..., ge=1, description="주문할 수량")

class KokCartOrderRequest(BaseModel):
    """장바구니에서 선택된 상품들 주문 요청"""
    selected_items: List[KokCartOrderItem] = Field(..., description="선택된 장바구니 상품들과 수량 목록")

class KokCartOrderResponse(BaseModel):
    """장바구니에서 선택된 상품들 주문 응답"""
    order_id: int
    total_amount: int
    order_count: int
    message: str

# 레시피 추천 관련 스키마
class KokCartRecipeRecommendRequest(BaseModel):
    """장바구니에서 선택된 상품들로 레시피 추천 요청"""
    selected_cart_ids: List[int] = Field(..., description="선택된 장바구니 항목 ID 목록")
    page: int = Field(1, ge=1, description="페이지 번호 (1부터 시작)")
    size: int = Field(5, ge=1, le=50, description="페이지당 결과 개수")

class KokCartRecipeRecommendResponse(BaseModel):
    """장바구니에서 선택된 상품들로 레시피 추천 응답"""
    recipes: List[dict] = Field(default_factory=list, description="추천 레시피 목록")
    page: int = Field(..., description="현재 페이지")
    total: int = Field(..., description="전체 결과 개수")
    ingredients_used: List[str] = Field(default_factory=list, description="사용된 재료 목록")

# -----------------------------
# 검색 관련 스키마
# -----------------------------

class KokSearchHistory(BaseModel):
    """검색 이력 정보"""
    kok_history_id: int
    user_id: int
    kok_keyword: str
    kok_searched_at: str
    
    class Config:
        from_attributes = True

class KokSearchRequest(BaseModel):
    """검색 요청"""
    keyword: str

class KokSearchResponse(BaseModel):
    """검색 결과 응답"""
    total: int
    page: int
    size: int
    products: List[dict] = Field(default_factory=list)

class KokSearchHistoryResponse(BaseModel):
    """검색 이력 응답"""
    history: List[KokSearchHistory] = Field(default_factory=list)

class KokSearchHistoryCreate(BaseModel):
    """검색 이력 생성 요청"""
    keyword: str

class KokSearchHistoryDeleteRequest(BaseModel):
    """검색 이력 삭제 요청"""
    kok_history_id: int

class KokSearchHistoryDeleteResponse(BaseModel):
    """검색 이력 삭제 응답"""
    message: str

# -----------------------------
# 알림 관련 스키마
# -----------------------------

class KokNotification(BaseModel):
    """콕 알림 정보"""
    notification_id: int
    user_id: int
    kok_order_id: int
    status_id: int
    title: str
    message: str
    created_at: str
    
    class Config:
        from_attributes = True

class KokNotificationResponse(BaseModel):
    """콕 알림 내역 응답"""
    notifications: List[KokNotification] = Field(default_factory=list)
    total: int = 0
    
    class Config:
        from_attributes = True
