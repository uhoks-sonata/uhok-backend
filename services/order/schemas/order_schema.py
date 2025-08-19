"""
주문 공통/서비스별 Pydantic 스키마 정의 (HomeShopping 명칭 통일)
"""
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

from services.order.schemas.kok_order_schema import KokOrderSchema
from services.order.schemas.hs_order_schema import HomeshoppingOrderSchema

class OrderRead(BaseModel):
    order_id: int
    user_id: int
    order_time: datetime
    cancel_time: Optional[datetime]
    kok_orders: List[KokOrderSchema] = []
    homeshopping_orders: List[HomeshoppingOrderSchema] = []
        
    class Config:
        from_attributes = True

class OrderCountResponse(BaseModel):
    order_count: int

# -----------------------------
# 결제 관련 스키마
# -----------------------------

class PaymentConfirmV1Request(BaseModel):
    """결제 확인 요청 (v1)"""
    
    class Config:
        from_attributes = True


class PaymentConfirmV1Response(BaseModel):
    """결제 확인 응답 (v1)"""
    payment_id: str
    order_id: str
    status: str
    payment_amount: int
    method: str
    confirmed_at: datetime
    order_id_internal: int  # 내부 주문 ID
    
    class Config:
        from_attributes = True

# -----------------------------
# 최근 주문 내역 표시용 스키마
# -----------------------------

class RecentOrderItem(BaseModel):
    """최근 주문 상품 아이템"""
    order_id: int
    order_number: str  # 주문 번호 (예: 00020250725309)
    order_date: str    # 주문 날짜 (예: 2025. 7. 25)
    delivery_status: str  # 배송 상태 (예: 배송완료)
    delivery_date: str    # 도착 예정일 (예: 7/28(월) 도착)
    product_name: str     # 상품명
    product_image: Optional[str] = None  # 상품 이미지 URL
    price: int            # 가격
    quantity: int         # 수량
    recipe_related: bool = False  # 레시피 관련 구매 여부
    recipe_title: Optional[str] = None  # 관련 레시피 제목
    recipe_rating: Optional[float] = None  # 레시피 별점
    recipe_scrap_count: Optional[int] = None  # 스크랩 수
    recipe_description: Optional[str] = None  # 레시피 설명
    ingredients_owned: Optional[int] = None  # 보유 재료 수
    total_ingredients: Optional[int] = None  # 총 재료 수
    
    class Config:
        from_attributes = True

class RecentOrdersResponse(BaseModel):
    """최근 주문 내역 응답"""
    days: int  # 조회 일수
    order_count: int  # 총 주문 수
    orders: List[RecentOrderItem]  # 주문 목록
    
    class Config:
        from_attributes = True
