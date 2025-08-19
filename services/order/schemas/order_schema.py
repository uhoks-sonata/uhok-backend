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

# -----------------------------
# 결제 관련 스키마
# -----------------------------

class PaymentConfirmV1Request(BaseModel):
    """결제 확인 요청 (v1)"""
    
    class Config:
        from_attributes = True


class PaymentConfirmV1Response(BaseModel):
    """결제 확인 응답 (v1)"""
    payment_id: str
    order_id: str
    status: str
    payment_amount: int
    method: str
    confirmed_at: datetime
    order_id_internal: int  # 내부 주문 ID
    
    class Config:
        from_attributes = True
