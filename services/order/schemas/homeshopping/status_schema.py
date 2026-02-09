"""HomeShopping order status schemas."""

from datetime import datetime

from pydantic import BaseModel, Field

from services.order.schemas.common_schema import StatusMasterSchema


class HomeshoppingOrderStatusHistorySchema(BaseModel):
    """홈쇼핑 주문 상태 변경 이력 스키마"""

    history_id: int
    homeshopping_order_id: int
    status: StatusMasterSchema
    created_at: datetime

    class Config:
        from_attributes = True


class HomeshoppingOrderStatusResponse(BaseModel):
    """홈쇼핑 주문 상태 조회 응답"""

    homeshopping_order_id: int = Field(..., description="홈쇼핑 주문 상세 ID")
    current_status: StatusMasterSchema = Field(..., description="현재 상태")
    status_history: list[HomeshoppingOrderStatusHistorySchema] = Field(default_factory=list, description="상태 변경 이력")

    class Config:
        from_attributes = True


class HomeshoppingOrderWithStatusResponse(BaseModel):
    """홈쇼핑 주문과 상태 함께 조회 응답"""

    order_id: int = Field(..., description="주문 고유번호")
    homeshopping_order_id: int = Field(..., description="홈쇼핑 주문 상세 고유번호")
    product_id: int = Field(..., description="상품 ID")
    product_name: str = Field(..., description="상품명")
    quantity: int = Field(..., description="주문 수량")
    dc_price: int = Field(..., description="할인가")
    order_price: int = Field(..., description="주문 금액")
    order_time: datetime = Field(..., description="주문 시간")
    current_status: StatusMasterSchema = Field(..., description="현재 상태")

    class Config:
        from_attributes = True
