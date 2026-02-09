"""HomeShopping order schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class HomeshoppingOrderRequest(BaseModel):
    """홈쇼핑 주문 생성 요청 (단건 주문)"""

    product_id: int = Field(..., description="상품 ID")
    quantity: int = Field(1, ge=1, le=99, description="주문 수량")

    class Config:
        from_attributes = True


class HomeshoppingOrderResponse(BaseModel):
    """홈쇼핑 주문 생성 응답"""

    order_id: int = Field(..., description="주문 고유번호")
    homeshopping_order_id: int = Field(..., description="홈쇼핑 주문 상세 고유번호")
    product_id: int = Field(..., description="상품 ID")
    product_name: str = Field(..., description="상품명")
    quantity: int = Field(..., description="주문 수량")
    dc_price: int = Field(..., description="할인가")
    order_price: int = Field(..., description="주문 금액")
    order_time: datetime = Field(..., description="주문 시간")
    message: str = Field(..., description="응답 메시지")

    class Config:
        from_attributes = True


class HomeshoppingOrderSchema(BaseModel):
    """홈쇼핑 주문 상세 스키마 (OrderRead에서 사용)"""

    homeshopping_order_id: int
    product_id: int
    dc_price: int
    quantity: int
    order_price: Optional[int]

    class Config:
        from_attributes = True
