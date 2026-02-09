from datetime import date, time
from typing import List, Optional

from pydantic import BaseModel, Field

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
    sale_price: Optional[int] = None
    dc_price: Optional[int] = None
    dc_rate: Optional[int] = None
    
    class Config:
        from_attributes = True


class HomeshoppingSchedulePagination(BaseModel):
    """편성표 페이징 정보"""
    page: int = Field(..., description="현재 페이지")
    size: int = Field(..., description="페이지 크기")
    total_count: int = Field(..., description="전체 개수")
    has_more: bool = Field(..., description="더 많은 데이터가 있는지 여부")


class HomeshoppingScheduleResponse(BaseModel):
    """편성표 조회 응답 - 최적화된 버전"""
    schedules: List[HomeshoppingScheduleItem] = Field(default_factory=list)

