"""
BackgroundTasks용 로그 API 호출 함수 (.env config 사용)
"""
import requests
from common.config import get_settings

settings = get_settings()
api_url = settings.log_api_url   # .env에서 불러옴

def send_user_log(user_id: int, event_type: str, event_data: dict = None):
    """
    사용자 행동 로그를 로그 서비스로 전송 (BackgroundTasks)
    """
    log_payload = {
        "user_id": user_id,
        "event_type": event_type,
        "event_data": event_data or {}
    }
    try:
        res = requests.post(api_url, json=log_payload, timeout=2)
        res.raise_for_status()
        return res.json()
    except Exception as e:
        print(f"[WARN] 로그 적재 실패: {e}")
