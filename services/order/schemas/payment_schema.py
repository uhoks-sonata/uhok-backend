from pydantic import BaseModel
from datetime import datetime
from typing import Optional

# -----------------------------
# 결제 관련 스키마
# -----------------------------

class PaymentConfirmV1Request(BaseModel):
    """결제 확인 요청 (v1)"""
    method: Optional[str] = "EXTERNAL_API"  # 결제 방법 (기본값: EXTERNAL_API)
    
    class Config:
        from_attributes = True


class PaymentConfirmV1Response(BaseModel):
    """결제 확인 응답 (v1)"""
    payment_id: str
    order_id: int  # 숫자 그대로 사용
    kok_order_ids: list[int] = []  # 콕 주문 ID 목록
    hs_order_id: Optional[int] = None  # 홈쇼핑 주문 ID (단개 주문)
    status: str
    payment_amount: int
    method: str
    confirmed_at: datetime
    order_id_internal: int  # 내부 주문 ID
    
    class Config:
        from_attributes = True
