"""
사용자 이벤트 로그 적재 요청/응답용 스키마
"""

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class UserEventLogCreate(BaseModel):
    """
    사용자 로그 생성 요청 스키마
    - user_id는 MariaDB USERS.USER_ID와 동일
    - HTTP 관련 필드는 선택적 (자동 수집)
    """

    user_id: int
    event_type: str
    event_data: Optional[Dict[str, Any]] = Field(default_factory=dict)

    # HTTP 관련 필드들 (선택적)
    http_method: Optional[str] = Field(None, description="HTTP 메서드 (GET, POST, PUT, DELETE 등)")
    api_url: Optional[str] = Field(None, description="API 엔드포인트 URL")
    request_time: Optional[datetime] = Field(None, description="API 요청 시작 시간")
    response_time: Optional[datetime] = Field(None, description="API 응답 완료 시간")
    response_code: Optional[int] = Field(None, description="HTTP 응답 상태 코드 (200, 404, 500 등)")
    client_ip: Optional[str] = Field(None, description="요청자 IP 주소 (IPv4/IPv6 지원)")


class UserEventLogRead(UserEventLogCreate):
    log_id: int
    created_at: datetime
