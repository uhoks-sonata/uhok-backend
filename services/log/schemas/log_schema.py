"""
사용자 로그 적재 요청/응답용 스키마
"""
from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any

class UserLogCreate(BaseModel):
    """
    사용자 로그 생성 요청 스키마
    - user_id는 MariaDB USERS.USER_ID와 동일
    """
    user_id: int                   # MariaDB USERS.USER_ID와 동일한 값
    event_type: str                # ex. 'cart_add', 'order', 'login' 등
    event_data: Optional[Dict[str, Any]] = Field(default_factory=dict)  # 이벤트 상세 데이터(JSON)

class UserLogRead(UserLogCreate):
    log_id: int
    created_at: datetime    # ← 반드시 이렇게!
