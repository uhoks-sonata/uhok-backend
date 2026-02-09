from datetime import date, datetime, time
from typing import List, Optional

from pydantic import BaseModel, Field

class HomeshoppingSearchRequest(BaseModel):
    """상품 검색 요청"""
    keyword: str = Field(..., description="검색 키워드")
    page: int = Field(1, ge=1, description="페이지 번호")
    size: int = Field(20, ge=1, le=100, description="페이지 크기")


class HomeshoppingSearchProduct(BaseModel):
    """검색 결과 상품 정보"""
    live_id: int
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
