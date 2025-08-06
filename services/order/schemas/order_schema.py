"""
주문 공통/서비스별 Pydantic 스키마 정의 (HomeShopping 명칭 통일)
"""
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class KokOrderCreate(BaseModel):
    kok_price_id: int
    kok_product_id: int
    quantity: int = 1

class HomeShoppingOrderCreate(BaseModel):
    live_id: int

class KokOrderSchema(BaseModel):
    kok_order_id: int
    kok_price_id: int
    kok_product_id: int
    quantity: int
    order_price: Optional[int]

class HomeShoppingOrderSchema(BaseModel):
    homeshopping_order_id: int
    live_id: int

class OrderRead(BaseModel):
    order_id: int
    user_id: int
    order_time: datetime
    cancel_time: Optional[datetime]
    kok_order: Optional[KokOrderSchema]
    homeshopping_order: Optional[HomeShoppingOrderSchema]
    class Config:
        from_attributes = True

class OrderCountResponse(BaseModel):
    order_count: int
