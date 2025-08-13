"""
주문 공통/서비스별 Pydantic 스키마 정의 (HomeShopping 명칭 통일)
"""
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

from services.order.schemas.kok_order_schema import KokOrderSchema

class StatusMasterSchema(BaseModel):
    """상태 마스터 스키마"""
    status_id: int
    status_code: str
    status_name: str
    
    class Config:
        from_attributes = True

class OrderRead(BaseModel):
    order_id: int
    user_id: int
    order_time: datetime
    cancel_time: Optional[datetime]
    kok_orders: List[KokOrderSchema] = []
    # homeshopping_order: Optional[HomeShoppingOrderSchema] = None
    
    # kok_orders는 빈 리스트 허용
    
    class Config:
        from_attributes = True

class OrderCountResponse(BaseModel):
    order_count: int
