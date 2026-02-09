from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

class KokLikes(BaseModel):
    """찜 정보"""
    kok_like_id: int
    user_id: int
    kok_product_id: int
    kok_created_at: datetime
    
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
    kok_price_id: int
    kok_quantity: int
    kok_created_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

# 새로운 장바구니 스키마들
class KokCartAddRequest(BaseModel):
    """장바구니 추가 요청"""
    kok_product_id: int
    kok_quantity: int = Field(1, ge=1, description="추가할 수량")
    recipe_id: Optional[int] = Field(None, description="레시피ID (레시피 상세에서 유입된 경우)")

class KokCartAddResponse(BaseModel):
    """장바구니 추가 응답"""
    kok_cart_id: int
    message: str

class KokCartUpdateRequest(BaseModel):
    """장바구니 수량 변경 요청"""
    kok_quantity: int = Field(..., ge=1, description="변경할 수량")

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
    kok_price_id: int  # 자동으로 최신 가격 ID 사용
    recipe_id: Optional[int] = None
    kok_product_name: Optional[str] = None
    kok_thumbnail: Optional[str] = None
    kok_product_price: Optional[int] = None
    kok_discount_rate: Optional[int] = None
    kok_discounted_price: Optional[int] = None
    kok_store_name: Optional[str] = None
    kok_quantity: int
    
    class Config:
        from_attributes = True

class KokCartItemsResponse(BaseModel):
    """장바구니 상품 목록 응답"""
    cart_items: List[KokCartItem] = Field(default_factory=list)


# -----------------------------
# 검색 관련 스키마
# -----------------------------

class KokSearchHistory(BaseModel):
    """검색 이력 정보"""
    kok_history_id: int
    user_id: int
    kok_keyword: str
    kok_searched_at: datetime
    
    class Config:
        from_attributes = True

class KokSearchRequest(BaseModel):
    """검색 요청"""
    keyword: str

class KokSearchProduct(BaseModel):
    """검색 결과 상품 정보"""
    kok_product_id: int
    kok_product_name: Optional[str] = None
    kok_store_name: Optional[str] = None
    kok_thumbnail: Optional[str] = None
    kok_product_price: Optional[int] = None
    kok_discount_rate: Optional[int] = None
    kok_discounted_price: Optional[int] = None
    kok_review_cnt: Optional[int] = None
    kok_review_score: Optional[float] = None
    
    class Config:
        from_attributes = True

class KokSearchResponse(BaseModel):
    """검색 결과 응답"""
    total: int
    page: int
    size: int
    products: List[KokSearchProduct] = Field(default_factory=list)

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
    created_at: datetime
    
    class Config:
        from_attributes = True

class KokNotificationResponse(BaseModel):
    """콕 알림 내역 응답"""
    notifications: List[KokNotification] = Field(default_factory=list)
    total: int = 0
    
    class Config:
        from_attributes = True

# -----------------------------
# 장바구니 레시피 추천 관련 스키마
# -----------------------------

class KokCartRecipeRecommendRequest(BaseModel):
    """장바구니 상품 기반 레시피 추천 요청"""
    selected_cart_ids: List[int] = Field(..., description="선택된 장바구니 상품 ID 목록")
    page: int = Field(1, ge=1, description="페이지 번호 (1부터 시작)")
    size: int = Field(10, ge=1, le=100, description="페이지당 레시피 수")

class KokCartRecipeRecommendResponse(BaseModel):
    """장바구니 상품 기반 레시피 추천 응답"""
    recipes: List[Dict[str, Any]] = Field(..., description="추천된 레시피 목록")
    total_count: int = Field(..., description="전체 레시피 수")
    page: int = Field(..., description="현재 페이지 번호")
    size: int = Field(..., description="페이지당 레시피 수")
    total_pages: int = Field(..., description="전체 페이지 수")
    keyword_extraction: List[str] = Field(..., description="추출된 키워드 목록")
