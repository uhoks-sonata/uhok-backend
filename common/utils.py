# utils.py
"""
공통 유틸 함수 모음 (날짜 문자열 등)
"""
from datetime import datetime

def now_str():
    """현재 시간 문자열 반환"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def truncate_text(text: str, max_length: int = 100):
    """최대 길이 초과 시 텍스트 자르기"""
    return text if len(text) <= max_length else text[:max_length] + "..."
