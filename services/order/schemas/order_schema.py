"""
주문 공통/서비스별 Pydantic 스키마 정의 (HomeShopping 명칭 통일)
"""
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

from services.order.schemas.kok_order_schema import KokOrderSchema
from services.order.schemas.hs_order_schema import HomeshoppingOrderSchema

class OrderRead(BaseModel):
    order_id: int
    user_id: int
    order_time: datetime
    cancel_time: Optional[datetime]
    kok_orders: List[KokOrderSchema] = []
    homeshopping_orders: List[HomeshoppingOrderSchema] = []
        
    class Config:
        from_attributes = True

class OrderCountResponse(BaseModel):
    order_count: int
