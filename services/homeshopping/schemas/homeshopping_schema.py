"""
홈쇼핑 API 스키마 정의 모듈
- Pydantic BaseModel을 사용한 데이터 검증 및 직렬화
- API 요청/응답 데이터 구조 정의
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from datetime import datetime, date, time

# -----------------------------
# 편성표 관련 스키마
# -----------------------------

class HomeshoppingScheduleItem(BaseModel):
    """홈쇼핑 편성표 항목"""
    live_id: int
    homeshopping_id: int
    homeshopping_name: str
    homeshopping_channel: int
    live_date: date
    live_start_time: time
    live_end_time: time
    promotion_type: str
    product_id: int
    product_name: str
    thumb_img_url: str
    original_price: Optional[int] = None
    discounted_price: Optional[int] = None
    discount_rate: Optional[int] = None
    
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
    product_id: int
    product_name: str
    store_name: Optional[str] = None
    sale_price: Optional[int] = None
    dc_price: Optional[int] = None
    dc_rate: Optional[int] = None
    thumb_img_url: str
    live_date: date
    live_start_time: time
    live_end_time: time
    
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
    product_id: int
    product_name: str
    store_name: Optional[str] = None
    sale_price: Optional[int] = None
    dc_price: Optional[int] = None
    dc_rate: Optional[int] = None
    live_date: date
    live_start_time: time
    live_end_time: time
    thumb_img_url: str
    is_liked: bool = False
    
    class Config:
        from_attributes = True


class HomeshoppingProductImage(BaseModel):
    """상품 이미지 정보"""
    img_url: str
    sort_order: int
    
    class Config:
        from_attributes = True


class HomeshoppingProductDetailInfo(BaseModel):
    """상품 상세 정보"""
    detail_col: str
    detail_val: str
    
    class Config:
        from_attributes = True


class HomeshoppingProductDetailResponse(BaseModel):
    """상품 상세 조회 응답"""
    product: HomeshoppingProductDetail
    detail_infos: List[HomeshoppingProductDetailInfo] = Field(default_factory=list)
    images: List[HomeshoppingProductImage] = Field(default_factory=list)


# -----------------------------
# 상품 추천 관련 스키마
# -----------------------------

class HomeshoppingProductRecommendation(BaseModel):
    """상품 추천 정보"""
    product_id: int
    product_name: str
    recommendation_type: str  # "ingredient" 또는 "recipe"
    reason: str
    
    class Config:
        from_attributes = True


class HomeshoppingProductRecommendationsResponse(BaseModel):
    """상품 추천 응답"""
    recommendations: List[HomeshoppingProductRecommendation] = Field(default_factory=list)


# -----------------------------
# 스트리밍 관련 스키마
# -----------------------------

class HomeshoppingStreamResponse(BaseModel):
    """홈쇼핑 라이브 스트리밍 응답"""
    product_id: int
    stream_url: str
    is_live: bool
    live_start_time: Optional[time] = None
    live_end_time: Optional[time] = None


# -----------------------------
# 찜 관련 스키마
# -----------------------------

class HomeshoppingLikesToggleRequest(BaseModel):
    """찜 등록/해제 요청"""
    product_id: int = Field(..., description="상품 ID")


class HomeshoppingLikesToggleResponse(BaseModel):
    """찜 등록/해제 응답"""
    liked: bool
    message: str


class HomeshoppingLikedProduct(BaseModel):
    """찜한 상품 정보"""
    product_id: int
    product_name: str
    store_name: Optional[str] = None
    dc_price: Optional[int] = None
    dc_rate: Optional[int] = None
    thumb_img_url: str
    homeshopping_like_created_at: datetime
    
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


# -----------------------------
# 통합 알림 관련 스키마 (기존 테이블 활용)
# -----------------------------

class HomeshoppingNotificationCreate(BaseModel):
    """홈쇼핑 알림 생성 스키마"""
    user_id: int = Field(..., description="사용자 ID")
    notification_type: str = Field(..., description="알림 타입 (broadcast_start, order_status)")
    related_entity_type: str = Field(..., description="관련 엔티티 타입 (product, order)")
    related_entity_id: int = Field(..., description="관련 엔티티 ID")
    homeshopping_like_id: Optional[int] = Field(None, description="관련 찜 ID (방송 찜 알림인 경우)")
    homeshopping_order_id: Optional[int] = Field(None, description="관련 주문 ID (주문 상태 알림인 경우)")
    status_id: Optional[int] = Field(None, description="상태 ID (주문 상태 알림인 경우)")
    title: str = Field(..., description="알림 제목")
    message: str = Field(..., description="알림 메시지")


class HomeshoppingNotificationResponse(BaseModel):
    """홈쇼핑 알림 응답 스키마"""
    notification_id: int = Field(..., description="알림 ID")
    user_id: int = Field(..., description="사용자 ID")
    notification_type: str = Field(..., description="알림 타입")
    related_entity_type: str = Field(..., description="관련 엔티티 타입")
    related_entity_id: int = Field(..., description="관련 엔티티 ID")
    homeshopping_like_id: Optional[int] = Field(None, description="관련 찜 ID")
    homeshopping_order_id: Optional[int] = Field(None, description="관련 주문 ID")
    status_id: Optional[int] = Field(None, description="상태 ID")
    title: str = Field(..., description="알림 제목")
    message: str = Field(..., description="알림 메시지")
    product_name: Optional[str] = Field(None, description="상품명")
    is_read: bool = Field(..., description="읽음 여부")
    created_at: datetime = Field(..., description="생성 시각")
    read_at: Optional[datetime] = Field(None, description="읽음 처리 시각")
    
    class Config:
        from_attributes = True


class HomeshoppingNotificationListResponse(BaseModel):
    """홈쇼핑 알림 목록 조회 응답"""
    notifications: List[HomeshoppingNotificationResponse] = Field(default_factory=list, description="알림 목록")
    total_count: int = Field(..., description="전체 알림 개수")
    has_more: bool = Field(..., description="더 많은 알림이 있는지 여부")


class HomeshoppingNotificationFilter(BaseModel):
    """홈쇼핑 알림 필터 스키마"""
    notification_type: Optional[str] = Field(None, description="알림 타입 필터")
    related_entity_type: Optional[str] = Field(None, description="관련 엔티티 타입 필터")
    is_read: Optional[bool] = Field(None, description="읽음 여부 필터")
    limit: int = Field(20, ge=1, le=100, description="조회할 알림 개수")
    offset: int = Field(0, ge=0, description="시작 위치")


class HomeshoppingNotificationUpdate(BaseModel):
    """홈쇼핑 알림 수정 스키마"""
    is_read: Optional[bool] = Field(None, description="읽음 여부")
    read_at: Optional[datetime] = Field(None, description="읽음 처리 시각")
