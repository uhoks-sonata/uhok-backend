"""
홈쇼핑 API 스키마 정의 모듈
- Pydantic BaseModel을 사용한 데이터 검증 및 직렬화
- API 요청/응답 데이터 구조 정의
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from datetime import datetime


# -----------------------------
# 편성표 관련 스키마
# -----------------------------

class HomeshoppingScheduleItem(BaseModel):
    """홈쇼핑 편성표 항목"""
    live_id: int
    homeshopping_channel_name: str
    homeshopping_channel_number: int
    live_date: datetime
    live_time: str
    promotion_type: str
    live_title: Optional[str] = None
    product_id: str
    product_name: str
    dc_price: int
    dc_rate: int
    thumb_img_url: str
    
    class Config:
        from_attributes = True


class HomeshoppingScheduleResponse(BaseModel):
    """편성표 조회 응답"""
    schedules: List[HomeshoppingScheduleItem] = Field(default_factory=list)


# -----------------------------
# 상품 검색 관련 스키마
# -----------------------------

class HomeshoppingSearchRequest(BaseModel):
    """상품 검색 요청"""
    keyword: str = Field(..., description="검색 키워드")
    page: int = Field(1, ge=1, description="페이지 번호")
    size: int = Field(20, ge=1, le=100, description="페이지 크기")


class HomeshoppingSearchProduct(BaseModel):
    """검색 결과 상품 정보"""
    product_id: str
    product_name: str
    store_name: str
    sale_price: int
    dc_price: int
    dc_rate: int
    thumb_img_url: str
    live_date: datetime
    live_time: str
    
    class Config:
        from_attributes = True


class HomeshoppingSearchResponse(BaseModel):
    """상품 검색 응답"""
    total: int
    page: int
    size: int
    products: List[HomeshoppingSearchProduct] = Field(default_factory=list)


# -----------------------------
# 검색 이력 관련 스키마
# -----------------------------

class HomeshoppingSearchHistory(BaseModel):
    """검색 이력 정보"""
    homeshopping_history_id: int
    user_id: int
    homeshopping_keyword: str
    homeshopping_searched_at: datetime
    
    class Config:
        from_attributes = True


class HomeshoppingSearchHistoryCreate(BaseModel):
    """검색 이력 생성 요청"""
    keyword: str = Field(..., description="검색 키워드")


class HomeshoppingSearchHistoryResponse(BaseModel):
    """검색 이력 조회 응답"""
    history: List[HomeshoppingSearchHistory] = Field(default_factory=list)


class HomeshoppingSearchHistoryDeleteRequest(BaseModel):
    """검색 이력 삭제 요청"""
    homeshopping_history_id: int = Field(..., description="삭제할 검색 이력 ID")


class HomeshoppingSearchHistoryDeleteResponse(BaseModel):
    """검색 이력 삭제 응답"""
    message: str


# -----------------------------
# 상품 상세 관련 스키마
# -----------------------------

class HomeshoppingProductDetail(BaseModel):
    """홈쇼핑 상품 상세 정보"""
    product_id: str
    product_name: str
    store_name: str
    sale_price: int
    dc_price: int
    dc_rate: int
    return_exchange: str
    term: str
    live_date: datetime
    live_time: str
    thumb_img_url: str
    is_liked: bool = False
    
    class Config:
        from_attributes = True


class HomeshoppingProductDetailResponse(BaseModel):
    """상품 상세 조회 응답"""
    product: HomeshoppingProductDetail
    detail_infos: List[Dict[str, str]] = Field(default_factory=list)
    images: List[Dict[str, str]] = Field(default_factory=list)


# -----------------------------
# 상품 추천 관련 스키마
# -----------------------------

class HomeshoppingProductRecommendation(BaseModel):
    """상품 추천 정보"""
    product_id: str
    product_name: str
    recommendation_type: str  # "ingredient" 또는 "recipe"
    reason: str
    
    class Config:
        from_attributes = True


class HomeshoppingProductRecommendationsResponse(BaseModel):
    """상품 추천 응답"""
    recommendations: List[HomeshoppingProductRecommendation] = Field(default_factory=list)


# -----------------------------
# 주문 관련 스키마
# -----------------------------

class HomeshoppingOrderItem(BaseModel):
    """홈쇼핑 주문 항목"""
    product_id: str = Field(..., description="상품 ID")
    quantity: int = Field(..., ge=1, description="주문 수량")


class HomeshoppingOrderRequest(BaseModel):
    """홈쇼핑 주문 생성 요청"""
    items: List[HomeshoppingOrderItem] = Field(..., description="주문 상품 목록")
    delivery_address: str = Field(..., description="배송 주소")
    delivery_phone: str = Field(..., description="배송 연락처")


class HomeshoppingOrderResponse(BaseModel):
    """홈쇼핑 주문 생성 응답"""
    order_id: int
    message: str


# -----------------------------
# 스트리밍 관련 스키마
# -----------------------------

class HomeshoppingStreamResponse(BaseModel):
    """홈쇼핑 라이브 스트리밍 응답"""
    product_id: str
    stream_url: str
    is_live: bool
    live_start_time: Optional[datetime] = None
    live_end_time: Optional[datetime] = None


# -----------------------------
# 찜 관련 스키마
# -----------------------------

class HomeshoppingLikesToggleRequest(BaseModel):
    """찜 등록/해제 요청"""
    product_id: str = Field(..., description="상품 ID")


class HomeshoppingLikesToggleResponse(BaseModel):
    """찜 등록/해제 응답"""
    liked: bool
    message: str


class HomeshoppingLikedProduct(BaseModel):
    """찜한 상품 정보"""
    product_id: str
    product_name: str
    store_name: str
    dc_price: int
    dc_rate: int
    thumb_img_url: str
    homeshopping_created_at: datetime
    
    class Config:
        from_attributes = True


class HomeshoppingLikesResponse(BaseModel):
    """찜한 상품 목록 응답"""
    liked_products: List[HomeshoppingLikedProduct] = Field(default_factory=list)

# -----------------------------
# 알림 관련 스키마
# -----------------------------

class HomeshoppingNotificationItem(BaseModel):
    """홈쇼핑 알림 정보"""
    notification_id: int = Field(..., description="알림 ID")
    homeshopping_order_id: int = Field(..., description="관련 주문 상세 ID")
    status_id: int = Field(..., description="상태 코드 ID")
    title: str = Field(..., description="알림 제목")
    message: str = Field(..., description="알림 메시지")
    created_at: datetime = Field(..., description="알림 생성 시각")
    
    class Config:
        from_attributes = True


class HomeshoppingNotificationHistoryResponse(BaseModel):
    """홈쇼핑 알림 내역 조회 응답"""
    notifications: List[HomeshoppingNotificationItem] = Field(default_factory=list, description="알림 목록")
    total_count: int = Field(..., description="전체 알림 개수")
