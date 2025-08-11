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
    logger.debug(f"now_str() 호출됨, 결과: {result}")
    return result

def truncate_text(text: str, max_length: int = 100):
    """최대 길이 초과 시 텍스트 자르기"""
    if text is None:
        logger.warning("truncate_text() 함수가 None 텍스트로 호출됨")
        return None
    
    original_length = len(text)
    result = text if original_length <= max_length else text[:max_length] + "..."
    
    if original_length > max_length:
        logger.debug(f"truncate_text() 텍스트 자름: {original_length}자에서 {max_length}자로")
    else:
        logger.debug(f"truncate_text() 자르기 불필요, 길이: {original_length}자")
    
    return result
