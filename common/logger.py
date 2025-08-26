# logger.py
"""
로깅 설정 및 logger 객체 반환 함수

    - ✅ 터미널 출력: 기본적으로 활성화
    - ❌ 파일 저장: 현재 비활성화됨
    - ❌ 데이터베이스 저장: 현재 비활성화
    - ✅ 구조화된 로깅: JSON 형식 지원
    - ✅ 로그 레벨별 색상 구분
"""
import logging
# import logging.handlers  # 파일 로깅에 사용되지만 현재 비활성화됨
import os
import json
from datetime import datetime
from typing import Optional, Dict, Any

class ColoredFormatter(logging.Formatter):
    """컬러 로그 포맷터"""
    
    COLORS = {
        'DEBUG': '\033[36m',      # 청록색
        'INFO': '\033[32m',       # 초록색
        'WARNING': '\033[33m',    # 노란색
        'ERROR': '\033[31m',      # 빨간색
        'CRITICAL': '\033[35m',   # 보라색
        'RESET': '\033[0m'        # 리셋
    }
    
    def format(self, record):
        # 로그 레벨에 따른 색상 적용
        levelname = record.levelname
        if levelname in self.COLORS:
            record.levelname = f"{self.COLORS[levelname]}{levelname}{self.COLORS['RESET']}"
        
        return super().format(record)

class JSONFormatter(logging.Formatter):
    """JSON 형식 로그 포맷터"""
    
    def format(self, record):
        log_entry = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }
        
        # 예외 정보가 있으면 추가
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)
        
        # 추가 필드가 있으면 추가
        if hasattr(record, 'extra_fields'):
            log_entry.update(record.extra_fields)
        
        return json.dumps(log_entry, ensure_ascii=False)

def get_logger(
    name: str = "app",
    level: str = "INFO",
    enable_file_logging: bool = False,
    log_file_path: Optional[str] = None,
    enable_json_format: bool = False,
    max_file_size: int = 10 * 1024 * 1024,  # 10MB (사용되지 않음)
    backup_count: int = 5  # 사용되지 않음
) -> logging.Logger:
    """
    logger 객체 생성 및 포맷 지정
    
    Args:
        name: 로거 이름
        level: 로그 레벨 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        enable_file_logging: 파일 로깅 활성화 여부 (현재 비활성화됨)
        log_file_path: 로그 파일 경로 (사용되지 않음)
        enable_json_format: JSON 형식 로깅 사용 여부
        max_file_size: 로그 파일 최대 크기 (사용되지 않음)
        backup_count: 백업 파일 개수 (사용되지 않음)
    """
    # SQLAlchemy 쿼리 로깅 비활성화
    logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
    logging.getLogger('sqlalchemy.pool').setLevel(logging.WARNING)
    logging.getLogger('sqlalchemy.dialects').setLevel(logging.WARNING)
    logging.getLogger('sqlalchemy.orm').setLevel(logging.WARNING)
    
    logger = logging.getLogger(name)
    
    # 이미 핸들러가 설정되어 있으면 기존 로거 반환
    if logger.handlers:
        return logger
    
    # 로그 레벨 설정
    log_level = getattr(logging, level.upper(), logging.INFO)
    logger.setLevel(log_level)
    
    # 터미널 핸들러 (기본)
    console_handler = logging.StreamHandler()
    
    if enable_json_format:
        console_formatter = JSONFormatter()
    else:
        console_formatter = ColoredFormatter(
            '[%(asctime)s] %(levelname)s - %(name)s - %(message)s'
        )
    
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # 파일 핸들러 (현재 비활성화됨)
    # if enable_file_logging:
    #     # 파일 로깅 기능이 비활성화되어 있습니다
    #     pass
    
    return logger

def log_with_context(logger: logging.Logger, level: str, message: str, **kwargs):
    """
    컨텍스트 정보와 함께 로깅
    
    Args:
        logger: 로거 객체
        level: 로그 레벨
        message: 로그 메시지
        **kwargs: 추가 컨텍스트 정보
    """
    extra_fields = kwargs if kwargs else {}
    
    if level.upper() == 'DEBUG':
        logger.debug(message, extra={'extra_fields': extra_fields})
    elif level.upper() == 'INFO':
        logger.info(message, extra={'extra_fields': extra_fields})
    elif level.upper() == 'WARNING':
        logger.warning(message, extra={'extra_fields': extra_fields})
    elif level.upper() == 'ERROR':
        logger.error(message, extra={'extra_fields': extra_fields})
    elif level.upper() == 'CRITICAL':
        logger.critical(message, extra={'extra_fields': extra_fields})

# 기본 로거 생성
logger = get_logger()

# 환경 변수로 로깅 설정 제어
def get_logger_from_env(name: str = "app") -> logging.Logger:
    """환경 변수를 기반으로 로거 생성"""
    # 파일 로깅은 현재 비활성화되어 있습니다
    # enable_file = os.getenv("ENABLE_FILE_LOGGING", "false").lower() == "true"
    log_level = os.getenv("LOG_LEVEL", "INFO")
    json_format = os.getenv("LOG_JSON_FORMAT", "false").lower() == "true"
    
    return get_logger(
        name=name,
        level=log_level,
        enable_file_logging=False,  # 강제로 비활성화
        enable_json_format=json_format
    )
