"""
홈쇼핑 스키마 패키지
"""

from .home_shopping_schema import (
    # 편성표 관련 스키마
    HomeshoppingScheduleItem,
    HomeshoppingScheduleResponse,
    
    # 상품 검색 관련 스키마
    HomeshoppingSearchRequest,
    HomeshoppingSearchProduct,
    HomeshoppingSearchResponse,
    
    # 검색 이력 관련 스키마
    HomeshoppingSearchHistory,
    HomeshoppingSearchHistoryCreate,
    HomeshoppingSearchHistoryResponse,
    HomeshoppingSearchHistoryDeleteRequest,
    HomeshoppingSearchHistoryDeleteResponse,
    
    # 상품 상세 관련 스키마
    HomeshoppingProductDetail,
    HomeshoppingProductDetailResponse,
    
    # 상품 추천 관련 스키마
    HomeshoppingProductRecommendation,
    HomeshoppingProductRecommendationsResponse,
    
    # 주문 관련 스키마
    HomeshoppingOrderItem,
    HomeshoppingOrderRequest,
    HomeshoppingOrderResponse,
    
    # 스트리밍 관련 스키마
    HomeshoppingStreamResponse,
    
    # 찜 관련 스키마
    HomeshoppingLikesToggleRequest,
    HomeshoppingLikesToggleResponse,
    HomeshoppingLikedProduct,
    HomeshoppingLikesResponse
)

__all__ = [
    "HomeshoppingScheduleItem",
    "HomeshoppingScheduleResponse",
    "HomeshoppingSearchRequest",
    "HomeshoppingSearchProduct",
    "HomeshoppingSearchResponse",
    "HomeshoppingSearchHistory",
    "HomeshoppingSearchHistoryCreate",
    "HomeshoppingSearchHistoryResponse",
    "HomeshoppingSearchHistoryDeleteRequest",
    "HomeshoppingSearchHistoryDeleteResponse",
    "HomeshoppingProductDetail",
    "HomeshoppingProductDetailResponse",
    "HomeshoppingProductRecommendation",
    "HomeshoppingProductRecommendationsResponse",
    "HomeshoppingOrderItem",
    "HomeshoppingOrderRequest",
    "HomeshoppingOrderResponse",
    "HomeshoppingStreamResponse",
    "HomeshoppingLikesToggleRequest",
    "HomeshoppingLikesToggleResponse",
    "HomeshoppingLikedProduct",
    "HomeshoppingLikesResponse"
]
