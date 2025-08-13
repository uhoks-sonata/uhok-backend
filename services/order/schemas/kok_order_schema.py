from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

from services.order.schemas.common_schema import StatusMasterSchema

# -----------------------------
# 장바구니 선택 주문 스키마
# -----------------------------

class KokCartOrderItem(BaseModel):
    cart_id: int = Field(..., description="장바구니 ID")
    quantity: int = Field(..., ge=1, description="주문 수량")

class KokCartOrderRequest(BaseModel):
    selected_items: List[KokCartOrderItem]

class KokCartOrderResponse(BaseModel):
    order_id: int
    order_count: int
    message: str

# -----------------------------
# 주문 상태 관련 스키마
# -----------------------------

class KokOrderSchema(BaseModel):
    kok_order_id: int
    kok_price_id: int
    kok_product_id: int
    quantity: int
    order_price: Optional[int]
    recipe_id: Optional[int] = None
    
    class Config:
        from_attributes = True

class KokOrderStatusHistorySchema(BaseModel):
    """콕 주문 상태 변경 이력 스키마"""
    history_id: int
    kok_order_id: int
    status: StatusMasterSchema
    changed_at: datetime
    changed_by: Optional[int] = None
    
    class Config:
        from_attributes = True

class KokOrderStatusUpdate(BaseModel):
    """콕 주문 상태 업데이트 요청"""
    new_status_code: str
    changed_by: Optional[int] = None

class KokOrderStatusResponse(BaseModel):
    """콕 주문 상태 응답"""
    kok_order_id: int
    current_status: Optional[StatusMasterSchema] = None
    status_history: List[KokOrderStatusHistorySchema] = []
    
    class Config:
        from_attributes = True

class KokOrderWithStatusResponse(BaseModel):
    """콕 주문과 현재 상태를 함께 응답"""
    kok_order: KokOrderSchema
    current_status: Optional[StatusMasterSchema] = None
    
    class Config:
        from_attributes = True

class KokNotificationSchema(BaseModel):
    """콕 알림 스키마"""
    notification_id: int
    user_id: int
    kok_order_id: int
    status_id: int
    title: str
    message: str
    created_at: datetime
    
    class Config:
        from_attributes = True

class KokNotificationListResponse(BaseModel):
    """콕 알림 목록 응답"""
    notifications: List[KokNotificationSchema] = []
    total_count: int = 0
    
    class Config:
        from_attributes = True

# class KokOrderCreate(BaseModel):
#     kok_price_id: int
#     kok_product_id: int
#     quantity: int = 1
#     recipe_id: Optional[int] = None
