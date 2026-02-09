"""Kok order status schemas."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel

from services.order.schemas.common_schema import StatusMasterSchema


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
    history_id: int
    kok_order_id: int
    status: StatusMasterSchema
    changed_at: datetime
    changed_by: Optional[int] = None

    class Config:
        from_attributes = True


class KokOrderStatusUpdate(BaseModel):
    new_status_code: str
    changed_by: Optional[int] = None


class KokOrderStatusResponse(BaseModel):
    kok_order_id: int
    current_status: Optional[StatusMasterSchema] = None
    status_history: List[KokOrderStatusHistorySchema] = []

    class Config:
        from_attributes = True


class KokOrderWithStatusResponse(BaseModel):
    kok_order: KokOrderSchema
    current_status: Optional[StatusMasterSchema] = None

    class Config:
        from_attributes = True
