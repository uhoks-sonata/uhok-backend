from pydantic import BaseModel
from datetime import datetime
from typing import Optional

# -----------------------------
# 결제 관련 스키마
# -----------------------------

class PaymentConfirmV1Request(BaseModel):
    """
    결제 확인 요청 (v1)
    
    Attributes:
        method: 결제 방법 (기본값: "EXTERNAL_API")
        
    Note:
        - 결제 방법을 선택적으로 지정할 수 있음
        - 지정하지 않으면 기본값 "EXTERNAL_API" 사용
        - 외부 결제 서비스와의 연동 방식 결정
    """
    method: Optional[str] = "EXTERNAL_API"  # 결제 방법 (기본값: EXTERNAL_API)
    
    class Config:
        from_attributes = True


class PaymentConfirmV1Response(BaseModel):
    """
    결제 확인 응답 (v1)
    
    Attributes:
        payment_id: 외부 결제 서비스에서 발급한 결제 ID
        order_id: 주문 ID (숫자 그대로 사용)
        kok_order_ids: 콕 주문 ID 목록 (여러 개 가능)
        hs_order_id: 홈쇼핑 주문 ID (단개 주문만 가능)
        status: 결제 상태
        payment_amount: 결제 금액
        method: 결제 방법
        confirmed_at: 결제 확인 시간
        order_id_internal: 내부 주문 ID
        
    Note:
        - 콕 주문은 여러 개 가능하므로 리스트로 관리
        - 홈쇼핑 주문은 단개 주문만 가능하므로 단일 값
        - 결제 완료 시 하위 주문들의 상태를 PAYMENT_COMPLETED로 변경
    """
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
