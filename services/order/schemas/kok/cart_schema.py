"""Kok cart-order schemas."""

from datetime import datetime
from typing import List

from pydantic import BaseModel, Field


class KokCartOrderItem(BaseModel):
    kok_cart_id: int = Field(..., description="장바구니 ID")
    quantity: int = Field(..., ge=1, description="주문 수량")


class KokCartOrderRequest(BaseModel):
    selected_items: List[KokCartOrderItem]


class KokOrderDetail(BaseModel):
    kok_order_id: int
    kok_product_id: int
    kok_product_name: str
    quantity: int
    unit_price: int
    total_price: int


class KokCartOrderResponse(BaseModel):
    order_id: int
    total_amount: int
    order_count: int
    order_details: List[KokOrderDetail]
    message: str
    order_time: datetime
