# logger.py
"""
로깅 설정 및 logger 객체 반환 함수
"""
import logging

def get_logger(name: str = "app"):
    """logger 객체 생성 및 포맷 지정"""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter('[%(asctime)s] %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger

logger = get_logger()
