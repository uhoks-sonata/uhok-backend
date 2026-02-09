from datetime import date, time
from typing import List, Optional

from pydantic import BaseModel, Field

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
    
    # 채널 정보 추가
    homeshopping_id: Optional[int] = None
    homeshopping_name: Optional[str] = None
    homeshopping_channel: Optional[int] = None
    homeshopping_channel_name: Optional[str] = None
    homeshopping_channel_image: Optional[str] = None
    
    class Config:
        from_attributes = True


class HomeshoppingProductImage(BaseModel):
    """상품 이미지 정보"""
    img_url: Optional[str] = None
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

