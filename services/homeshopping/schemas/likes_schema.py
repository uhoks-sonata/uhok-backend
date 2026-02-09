from datetime import date, datetime, time
from typing import List, Optional

from pydantic import BaseModel, Field

class HomeshoppingLikesToggleRequest(BaseModel):
    """찜 등록/해제 요청"""
    live_id: int = Field(..., description="방송 ID")


class HomeshoppingLikesToggleResponse(BaseModel):
    """찜 등록/해제 응답"""
    liked: bool
    message: str


class HomeshoppingLikedProduct(BaseModel):
    """찜한 상품 정보"""
    live_id: Optional[int] = None
    product_id: int
    product_name: str
    store_name: Optional[str] = None
    dc_price: Optional[int] = None
    dc_rate: Optional[int] = None
    thumb_img_url: str
    homeshopping_like_created_at: datetime
    homeshopping_id: Optional[int] = None
    live_date: Optional[date] = None
    live_start_time: Optional[time] = None
    live_end_time: Optional[time] = None
    
    class Config:
        from_attributes = True


class HomeshoppingLikesResponse(BaseModel):
    """찜한 상품 목록 응답"""
    liked_products: List[HomeshoppingLikedProduct] = Field(default_factory=list)

