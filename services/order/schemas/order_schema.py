"""
주문 관련 API 요청/응답 Pydantic 스키마
"""
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class OrderProduct(BaseModel):
    """
    주문 상품 응답 스키마
    """
    product_id: int
    product_name: str
    product_image: Optional[str]
    brand_name: Optional[str]
    quantity: int
    price: int

class OrderDetailResponse(BaseModel):
    """
    주문 상세 응답 스키마
    """
    order_id: int
    order_date: datetime
    total_price: int
    status: str
    payment_method: str
    shipping_address: str
    products: List[OrderProduct]

class OrderSummary(BaseModel):
    """
    주문 목록/최근 주문 응답용 간단 정보 스키마
    """
    order_id: int
    product_name: str
    product_image: Optional[str]
    brand_name: Optional[str]
    order_date: datetime

class OrderListResponse(BaseModel):
    """
    주문 목록(페이지네이션) 응답 스키마
    """
    total_count: int
    page: int
    size: int
    orders: List[OrderSummary]

class OrderRecentListResponse(BaseModel):
    """
    최근 N일 주문 리스트 응답 스키마
    """
    orders: List[OrderSummary]

class OrderCountResponse(BaseModel):
    """
    주문 개수 응답 스키마
    """
    order_count: int

