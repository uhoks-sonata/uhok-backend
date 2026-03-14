from datetime import date, time
from typing import Optional

from pydantic import BaseModel


class HomeshoppingStreamResponse(BaseModel):
    """Homeshopping live stream payload."""

    homeshopping_id: Optional[int] = None
    homeshopping_name: Optional[str] = None
    live_id: Optional[int] = None
    product_id: Optional[int] = None
    product_name: Optional[str] = None
    stream_url: str
    live_url: Optional[str] = None
    source: str
    is_live: bool = False
    live_date: Optional[date] = None
    live_start_time: Optional[time] = None
    live_end_time: Optional[time] = None
    thumb_img_url: Optional[str] = None
