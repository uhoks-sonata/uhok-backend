"""
사용자 로그 적재 요청/응답용 스키마
"""
from pydantic import BaseModel
from typing import Optional, Dict, Any

class UserLogCreate(BaseModel):
    """
    사용자 로그 생성 요청 스키마
    - user_id는 MariaDB USERS.USER_ID와 동일
    """
    user_id: int                   # MariaDB USERS.USER_ID와 동일한 값
    event_type: str                # ex. 'cart_add', 'order', 'login' 등
    event_data: Optional[Dict[str, Any]] = None  # 이벤트 상세 데이터(JSON)

class UserLogRead(UserLogCreate):
    """
    사용자 로그 응답 스키마
    """
    log_id: int
    created_at: str
