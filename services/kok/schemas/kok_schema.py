"""
콕 쇼핑몰 응답/요청용 Pydantic 스키마 모듈
- 모든 필드/변수는 소문자
- DB ORM과 분리, API 직렬화/유효성 검증용
- API 명세서의 변수명을 기반으로 작성
"""

from pydantic import BaseModel, Field
from typing import Optional, List

# -----------------------------
# 이미지 정보 스키마
# -----------------------------

class KokImageInfo(BaseModel):
    """이미지 정보"""
    img_id: int
    product_id: Optional[int] = None
    img_url: Optional[str] = None
    
    class Config:
        orm_mode = True

# -----------------------------
# 상세 정보 스키마
# -----------------------------

class KokDetailInfo(BaseModel):
    """상세 정보"""
    detail_col_id: int
    product_id: Optional[int] = None
    detail_col: Optional[str] = None
    detail_val: Optional[str] = None
    
    class Config:
        orm_mode = True

# -----------------------------
# 리뷰 스키마
# -----------------------------

class KokReviewExample(BaseModel):
    """리뷰 예시 정보"""
    review_id: int
    product_id: Optional[int] = None
    user_name: Optional[str] = None  # userName
    content: Optional[str] = None  # content
    created_at: Optional[str] = None  # createdAt
    review_score: Optional[int] = None
    price_eval: Optional[str] = None
    delivery_eval: Optional[str] = None
    taste_eval: Optional[str] = None
    
    class Config:
        orm_mode = True

# -----------------------------
# 가격 정보 스키마
# -----------------------------

class KokPriceInfo(BaseModel):
    """가격 정보"""
    price_id: int
    product_id: Optional[int] = None
    discount_rate: Optional[int] = None
    discounted_price: Optional[int] = None
    
    class Config:
        orm_mode = True

# -----------------------------
# Q&A 스키마
# -----------------------------

class KokQna(BaseModel):
    """Q&A 정보"""
    qna_id: int  # qnaId
    product_id: Optional[int] = None
    question: Optional[str] = None  # question
    answer: Optional[str] = None  # answer
    is_answered: Optional[bool] = None  # isAnswered
    author: Optional[str] = None  # author
    created_at: Optional[str] = None  # createdAt
    answered_at: Optional[str] = None  # answeredAt
    
    class Config:
        orm_mode = True

# -----------------------------
# 제품 기본/목록/상세 스키마
# -----------------------------

class KokProductBase(BaseModel):
    """제품 기본 정보"""
    # 🔹 공통 상품 정보 (메인화면 리스트 공통)
    product_id: int  # productId
    product_image: Optional[str] = None  # productImage
    product_name: Optional[str] = None  # productName
    brand_name: Optional[str] = None  # brandName
    price: Optional[int] = None  # price
    discount_rate: Optional[int] = None  # discountRate
    
    # 🔹 상품 상세 탭 정보
    description: Optional[str] = None  # description (HTML 형식 상품 설명)
    review_count: Optional[int] = None  # reviewCount
    qna_count: Optional[int] = None  # qnaCount
    
    # 리뷰 관련 정보
    review_score: Optional[float] = None  # 리뷰 평점 평균
    kok_5_ratio: Optional[int] = None  # 5점 비율
    kok_4_ratio: Optional[int] = None  # 4점 비율
    kok_3_ratio: Optional[int] = None  # 3점 비율
    kok_2_ratio: Optional[int] = None  # 2점 비율
    kok_1_ratio: Optional[int] = None  # 1점 비율
    
    # 평가 정보
    aspect_price: Optional[str] = None  # 가격 평가
    aspect_price_ratio: Optional[int] = None  # 가격 평가 비율
    aspect_delivery: Optional[str] = None  # 배송 평가
    aspect_delivery_ratio: Optional[int] = None  # 배송 평가 비율
    aspect_taste: Optional[str] = None  # 맛 평가
    aspect_taste_ratio: Optional[int] = None  # 맛 평가 비율
    
    # 판매자 정보
    seller: Optional[str] = None  # 판매자
    co_ceo: Optional[str] = None  # 상호명/대표자
    co_reg_no: Optional[str] = None  # 사업자등록번호
    co_ec_reg: Optional[str] = None  # 통신판매업신고
    tell: Optional[str] = None  # 전화번호
    ver_item: Optional[str] = None  # 인증완료 항목
    ver_date: Optional[str] = None  # 인증시기
    co_addr: Optional[str] = None  # 영업소재지
    return_addr: Optional[str] = None  # 반품주소
    exchange_addr: Optional[str] = None  # 교환주소
    
    class Config:
        orm_mode = True

class KokProductDetailResponse(KokProductBase):
    """제품 상세 응답(이미지, 상세정보, 리뷰, 가격, Q&A 포함)"""
    images: List[KokImageInfo] = Field(default_factory=list)
    detail_infos: List[KokDetailInfo] = Field(default_factory=list)
    review_examples: List[KokReviewExample] = Field(default_factory=list)
    price_infos: List[KokPriceInfo] = Field(default_factory=list)
    qna_list: List[KokQna] = Field(default_factory=list)

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
# 리뷰 리스트 응답 스키마
# -----------------------------

class KokReviewListResponse(BaseModel):
    """리뷰 리스트 응답"""
    total: int
    page: int
    size: int
    items: List[KokReviewExample] = Field(default_factory=list)

# -----------------------------
# Q&A 리스트 응답 스키마
# -----------------------------

class KokQnaListResponse(BaseModel):
    """Q&A 리스트 응답"""
    product_id: int
    qna_list: List[KokQna] = Field(default_factory=list)
    total_count: int

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
    product_id: int

# -----------------------------
# 리뷰 요청 스키마
# -----------------------------

class KokReviewRequest(BaseModel):
    """리뷰 목록 요청"""
    product_id: int
    page: int = 1
    size: int = 10

# -----------------------------
# Q&A 요청 스키마
# -----------------------------

class KokQnaRequest(BaseModel):
    """Q&A 목록 요청"""
    product_id: int
    page: int = 1
    size: int = 10

# -----------------------------
# 검색 이력 스키마
# -----------------------------

class KokSearchHistory(BaseModel):
    """검색 이력"""
    keyword: str
    searched_at: str
    
    class Config:
        orm_mode = True

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
    product_id: int

class KokLikesResponse(BaseModel):
    """찜 응답"""
    liked: bool
    message: str

class KokLikedProduct(BaseModel):
    """찜한 상품 정보"""
    product_id: int
    product_name: Optional[str] = None
    product_image: Optional[str] = None
    price: Optional[int] = None
    thumbnail_url: Optional[str] = None
    
    class Config:
        orm_mode = True

class KokLikesListResponse(BaseModel):
    """찜한 상품 목록 응답"""
    liked_products: List[KokLikedProduct] = Field(default_factory=list)

# -----------------------------
# 장바구니 관련 스키마
# -----------------------------

class KokCartToggle(BaseModel):
    """장바구니 토글 요청"""
    product_id: int

class KokCartResponse(BaseModel):
    """장바구니 응답"""
    in_cart: bool
    message: str

class KokCartItem(BaseModel):
    """장바구니 상품 정보"""
    product_id: int
    product_name: Optional[str] = None
    product_image: Optional[str] = None
    price: Optional[int] = None
    quantity: Optional[int] = None
    
    class Config:
        orm_mode = True

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

class KokNewProductsResponse(BaseModel):
    """신상품 응답"""
    products: List[KokProductBase] = Field(default_factory=list)

class KokRecommendationsResponse(BaseModel):
    """맞춤형 상품 응답"""
    products: List[KokProductBase] = Field(default_factory=list)


# -----------------------------
# 구매 이력 관련 스키마
# -----------------------------

class KokPurchase(BaseModel):
    """구매 이력 정보"""
    purchase_id: int
    user_id: Optional[int] = None
    product_id: Optional[int] = None
    quantity: Optional[int] = None
    purchase_price: Optional[int] = None
    purchased_at: Optional[str] = None
    
    class Config:
        orm_mode = True

class KokPurchaseHistory(BaseModel):
    """구매 이력 상세 정보"""
    purchase_id: int
    product_id: int
    product_name: Optional[str] = None
    product_image: Optional[str] = None
    quantity: Optional[int] = None
    purchase_price: Optional[int] = None
    purchased_at: Optional[str] = None
    
    class Config:
        orm_mode = True

class KokPurchaseHistoryResponse(BaseModel):
    """구매 이력 목록 응답"""
    purchase_history: List[KokPurchaseHistory] = Field(default_factory=list)
    total_count: int

class KokPurchaseCreate(BaseModel):
    """구매 이력 생성 요청"""
    product_id: int
    quantity: int = 1
    purchase_price: Optional[int] = None
