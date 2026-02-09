"""Kok notification schemas."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class KokNotificationSchema(BaseModel):
    notification_id: int
    user_id: int
    kok_order_id: int
    status_id: int
    title: str
    message: str
    created_at: datetime
    order_status: Optional[str] = None
    order_status_name: Optional[str] = None
    product_name: Optional[str] = None

    class Config:
        from_attributes = True


class KokNotificationListResponse(BaseModel):
    notifications: List[KokNotificationSchema] = []
    total_count: int = 0

    class Config:
        from_attributes = True
