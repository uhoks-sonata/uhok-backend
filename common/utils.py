# utils.py
"""
공통 유틸 함수 모음 (날짜 문자열 등)
"""
from datetime import datetime
from common.logger import get_logger

logger = get_logger("utils")

def now_str():
    """현재 시간 문자열 반환"""
    result = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logger.debug(f"now_str() called, result: {result}")
    return result

def truncate_text(text: str, max_length: int = 100):
    """최대 길이 초과 시 텍스트 자르기"""
    if text is None:
        logger.warning("truncate_text() called with None text")
        return None
    
    original_length = len(text)
    result = text if original_length <= max_length else text[:max_length] + "..."
    
    if original_length > max_length:
        logger.debug(f"truncate_text() truncated text from {original_length} to {max_length} characters")
    else:
        logger.debug(f"truncate_text() no truncation needed, length: {original_length}")
    
    return result
