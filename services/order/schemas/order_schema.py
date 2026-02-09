"""
주문 공통/서비스별 Pydantic 스키마 정의 (HomeShopping 명칭 통일)
"""
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

from services.order.schemas.homeshopping.order_schema import HomeshoppingOrderSchema
from services.order.schemas.kok.status_schema import KokOrderSchema

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
# 최근 주문 내역 표시용 스키마
# -----------------------------

class RecentOrderItem(BaseModel):
    """최근 주문 상품 아이템"""
    order_id: int
    order_number: str  # 주문 번호 (예: 00020250725309)
    order_date: str    # 주문 날짜 (예: 2025. 7. 25)
    delivery_status: str  # 배송 상태 (예: 배송완료)
    delivery_date: str    # 도착 예정일 (예: 7/28(월) 도착)
    product_id: int       # 상품 ID
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
    days: int  # 조회 개수
    order_count: int  # 총 주문 수
    orders: List[RecentOrderItem]  # 주문 목록
    
    class Config:
        from_attributes = True

# -----------------------------
# 주문 내역 그룹화용 스키마
# -----------------------------

class OrderGroupItem(BaseModel):
    """주문 그룹 내 개별 상품 아이템"""
    product_name: str     # 상품명
    product_image: Optional[str] = None  # 상품 이미지 URL
    price: int            # 가격
    quantity: int         # 수량
    delivery_status: str  # 배송 상태
    delivery_date: str    # 도착 예정일
    recipe_related: bool = False  # 레시피 관련 구매 여부
    recipe_title: Optional[str] = None  # 관련 레시피 제목
    recipe_rating: Optional[float] = None  # 레시피 별점
    recipe_scrap_count: Optional[int] = None  # 스크랩 수
    recipe_description: Optional[str] = None  # 레시피 설명
    ingredients_owned: Optional[int] = None  # 보유 재료 수
    total_ingredients: Optional[int] = None  # 총 재료 수
    
    class Config:
        from_attributes = True

class OrderGroup(BaseModel):
    """주문 ID별로 그룹화된 주문 정보"""
    order_id: int
    order_number: str     # 주문 번호 (예: 00020250725309)
    order_date: str       # 주문 날짜 (예: 2025. 7. 25)
    total_amount: int     # 주문 총액
    item_count: int       # 주문 상품 수
    items: List[OrderGroupItem]  # 주문 상품 목록
    
    class Config:
        from_attributes = True

class OrdersListResponse(BaseModel):
    """주문 목록 응답 (order_id로 그룹화)"""
    limit: int            # 조회 개수
    total_count: int      # 전체 주문 수
    order_groups: List[OrderGroup]  # 주문 그룹 목록
    
    class Config:
        from_attributes = True
