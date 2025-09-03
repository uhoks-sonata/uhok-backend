from pydantic import BaseModel
from datetime import datetime
from typing import Optional

# -----------------------------
# 결제 관련 스키마
# -----------------------------

class PaymentConfirmV1Request(BaseModel):
    """
    결제 확인 요청 (v1/v2 공통)
    
    Attributes:
        method: 결제 방법 (기본값: "EXTERNAL_API")
        timeout_sec: 타임아웃 시간 (초, v2에서 사용, 기본값: 25초)
        
    Note:
        - 결제 방법을 선택적으로 지정할 수 있음
        - 지정하지 않으면 기본값 "EXTERNAL_API" 사용
        - 외부 결제 서비스와의 연동 방식 결정
        - v2에서는 웹훅 대기 시간으로 사용
    """
    method: Optional[str] = "EXTERNAL_API"  # 결제 방법 (기본값: EXTERNAL_API)
    timeout_sec: Optional[int] = 25  # 타임아웃 시간 (초, v2에서 사용)
    
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


class PaymentConfirmV2Response(BaseModel):
    """
    결제 확인 응답 (v2)
    
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
        tx_id: 트랜잭션 ID (v2 전용)
        
    Note:
        - 콕 주문은 여러 개 가능하므로 리스트로 관리
        - 홈쇼핑 주문은 단개 주문만 가능하므로 단일 값
        - v2는 웹훅 방식으로 결제 완료를 처리
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
    tx_id: str  # 트랜잭션 ID (v2 전용)
    
    class Config:
        from_attributes = True


class LongPollQuery(BaseModel):
    timeout_sec: int = 25  # LB/프록시 idle timeout 고려


class PaymentErrorResponse(BaseModel):
    """
    결제 관련 에러 응답 (v1/v2 공통)
    
    Attributes:
        order_id: 주문 ID
        status: 에러 상태 (TIMEOUT, PAYMENT_FAILED, VALIDATION_ERROR 등)
        error_code: 에러 코드
        message: 에러 메시지
        detail: 상세 에러 설명
        timestamp: 에러 발생 시간
        retry_available: 재시도 가능 여부
    """
    order_id: int
    status: str
    error_code: str
    message: str
    detail: str
    timestamp: datetime
    retry_available: bool = True
    
    class Config:
        from_attributes = True


class PaymentTimeoutResponse(PaymentErrorResponse):
    """
    결제 타임아웃 에러 응답
    
    Attributes:
        timeout_seconds: 설정된 타임아웃 시간 (초)
        waited_until: 대기 종료 시간
    """
    timeout_seconds: int
    waited_until: datetime
    
    class Config:
        from_attributes = True


class PaymentFailedResponse(PaymentErrorResponse):
    """
    결제 실패 에러 응답
    
    Attributes:
        failure_reason: 실패 사유
        payment_id: 결제 ID (있는 경우)
        retry_count: 재시도 횟수
    """
    failure_reason: str
    payment_id: Optional[str] = None
    retry_count: int = 0
    
    class Config:
        from_attributes = True 