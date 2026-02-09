"""HomeShopping payment/automation schemas."""

from pydantic import BaseModel, Field


class PaymentConfirmResponse(BaseModel):
    """결제 확인 응답"""

    homeshopping_order_id: int = Field(..., description="홈쇼핑 주문 상세 ID")
    previous_status: str = Field(..., description="이전 상태")
    current_status: str = Field(..., description="현재 상태")
    message: str = Field(..., description="응답 메시지")

    class Config:
        from_attributes = True


class AutoUpdateResponse(BaseModel):
    """자동 상태 업데이트 시작 응답"""

    homeshopping_order_id: int = Field(..., description="홈쇼핑 주문 상세 ID")
    message: str = Field(..., description="응답 메시지")
    auto_update_started: bool = Field(..., description="자동 업데이트 시작 여부")

    class Config:
        from_attributes = True
