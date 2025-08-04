"""
주문 관련 Pydantic 스키마 정의 (필드명 소문자)
"""
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class OrderCreate(BaseModel):
    """
    주문 생성 요청 바디 스키마
    """
    user_id: int
    price_id: int

class OrderRead(BaseModel):
    """
    주문 단일 조회/응답 스키마
    """
    order_id: int
    user_id: int
    price_id: int
    order_time: datetime
    cancel_time: Optional[datetime]

    class Config:
        orm_mode = True
