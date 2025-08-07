"""
주문 공통/서비스별 Pydantic 스키마 정의 (HomeShopping 명칭 통일)
"""
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class StatusMasterSchema(BaseModel):
    """상태 마스터 스키마"""
    status_id: int
    status_code: str
    status_name: str
    
    class Config:
        from_attributes = True

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
    current_status: Optional[StatusMasterSchema] = None

class HomeShoppingOrderSchema(BaseModel):
    homeshopping_order_id: int
    live_id: int

class KokOrderStatusHistorySchema(BaseModel):
    """콕 주문 상태 변경 이력 스키마"""
    history_id: int
    kok_order_id: int
    status: StatusMasterSchema
    changed_at: datetime
    changed_by: Optional[int] = None
    
    class Config:
        from_attributes = True

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

class KokOrderStatusUpdate(BaseModel):
    """콕 주문 상태 업데이트 요청"""
    new_status_code: str
    changed_by: Optional[int] = None

class KokOrderStatusResponse(BaseModel):
    """콕 주문 상태 응답"""
    kok_order_id: int
    current_status: StatusMasterSchema
    status_history: List[KokOrderStatusHistorySchema] = []
    
    class Config:
        from_attributes = True
