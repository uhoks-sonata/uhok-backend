"""
사용자 활동 로그 스키마
- 프론트엔드에서 호출하는 사용자 활동 로그 데이터 구조 정의
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any

class UserActivityLog(BaseModel):
    """
    사용자 활동 로그 요청 스키마
    """
    action: str = Field(..., description="활동 유형 (예: view_order_history, navigation_click)")
    path: Optional[str] = Field(None, description="활동이 발생한 페이지 경로")
    label: Optional[str] = Field(None, description="활동 라벨 또는 설명")
    timestamp: Optional[str] = Field(None, description="활동 발생 시간 (ISO 8601 형식)")
    extra_data: Optional[Dict[str, Any]] = Field(None, description="추가 활동 데이터")


class UserActivityLogResponse(BaseModel):
    """
    사용자 활동 로그 응답 스키마
    """
    message: str = Field(..., description="응답 메시지")
    user_id: int = Field(..., description="사용자 ID")
    action: str = Field(..., description="기록된 활동 유형")
    timestamp: Optional[str] = Field(None, description="활동 시간")
    logged: bool = Field(..., description="로그 기록 성공 여부")
    log_id: Optional[int] = Field(None, description="생성된 로그 ID")
    error: Optional[str] = Field(None, description="에러 메시지 (실패 시)")


class UserActivityLogCreate(BaseModel):
    """
    사용자 활동 로그 생성 스키마 (내부 사용)
    """
    user_id: int
    event_type: str
    event_data: Dict[str, Any]
