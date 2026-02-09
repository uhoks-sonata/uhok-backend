from datetime import time
from typing import Optional

from pydantic import BaseModel

class HomeshoppingStreamResponse(BaseModel):
    """홈쇼핑 라이브 스트리밍 응답"""
    homeshopping_id: int
    live_url: str
    is_live: bool
    live_start_time: Optional[time] = None
    live_end_time: Optional[time] = None
    product_id: int

