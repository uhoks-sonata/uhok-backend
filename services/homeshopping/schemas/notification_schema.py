from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

class HomeshoppingNotificationItem(BaseModel):
    """홈쇼핑 알림 정보"""
    notification_id: int = Field(..., description="알림 ID")
    homeshopping_order_id: int = Field(..., description="관련 주문 상세 ID")
    status_id: int = Field(..., description="상태 코드 ID")
    title: str = Field(..., description="알림 제목")
    message: str = Field(..., description="알림 메시지")
    created_at: datetime = Field(..., description="알림 생성 시각")
    
    class Config:
        from_attributes = True


class HomeshoppingNotificationHistoryResponse(BaseModel):
    """홈쇼핑 알림 내역 조회 응답"""
    notifications: List[HomeshoppingNotificationItem] = Field(default_factory=list, description="알림 목록")
    total_count: int = Field(..., description="전체 알림 개수")


# -----------------------------
# 통합 알림 관련 스키마 (기존 테이블 활용)
# -----------------------------

class HomeshoppingNotificationCreate(BaseModel):
    """홈쇼핑 알림 생성 스키마"""
    user_id: int = Field(..., description="사용자 ID")
    notification_type: str = Field(..., description="알림 타입 (broadcast_start, order_status)")
    related_entity_type: str = Field(..., description="관련 엔티티 타입 (product, order)")
    related_entity_id: int = Field(..., description="관련 엔티티 ID")
    homeshopping_like_id: Optional[int] = Field(None, description="관련 찜 ID (방송 찜 알림인 경우)")
    homeshopping_order_id: Optional[int] = Field(None, description="관련 주문 ID (주문 상태 알림인 경우)")
    status_id: Optional[int] = Field(None, description="상태 ID (주문 상태 알림인 경우)")
    title: str = Field(..., description="알림 제목")
    message: str = Field(..., description="알림 메시지")


class HomeshoppingNotificationResponse(BaseModel):
    """홈쇼핑 알림 응답 스키마"""
    notification_id: int = Field(..., description="알림 ID")
    user_id: int = Field(..., description="사용자 ID")
    notification_type: str = Field(..., description="알림 타입")
    related_entity_type: str = Field(..., description="관련 엔티티 타입")
    related_entity_id: int = Field(..., description="관련 엔티티 ID")
    homeshopping_like_id: Optional[int] = Field(None, description="관련 찜 ID")
    homeshopping_order_id: Optional[int] = Field(None, description="관련 주문 ID")
    status_id: Optional[int] = Field(None, description="상태 ID")
    title: str = Field(..., description="알림 제목")
    message: str = Field(..., description="알림 메시지")
    product_name: Optional[str] = Field(None, description="상품명")
    is_read: bool = Field(..., description="읽음 여부")
    created_at: datetime = Field(..., description="생성 시각")
    read_at: Optional[datetime] = Field(None, description="읽음 처리 시각")
    
    class Config:
        from_attributes = True


class HomeshoppingNotificationListResponse(BaseModel):
    """홈쇼핑 알림 목록 조회 응답"""
    notifications: List[HomeshoppingNotificationResponse] = Field(default_factory=list, description="알림 목록")
    total_count: int = Field(..., description="전체 알림 개수")
    has_more: bool = Field(..., description="더 많은 알림이 있는지 여부")


class HomeshoppingNotificationFilter(BaseModel):
    """홈쇼핑 알림 필터 스키마"""
    notification_type: Optional[str] = Field(None, description="알림 타입 필터")
    related_entity_type: Optional[str] = Field(None, description="관련 엔티티 타입 필터")
    is_read: Optional[bool] = Field(None, description="읽음 여부 필터")
    limit: int = Field(20, ge=1, le=100, description="조회할 알림 개수")
    offset: int = Field(0, ge=0, description="시작 위치")


class HomeshoppingNotificationUpdate(BaseModel):
    """홈쇼핑 알림 수정 스키마"""
    is_read: Optional[bool] = Field(None, description="읽음 여부")
    read_at: Optional[datetime] = Field(None, description="읽음 처리 시각")

