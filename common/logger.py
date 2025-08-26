# logger.py
"""
로깅 설정 및 logger 객체 반환 함수

    - ✅ 터미널 출력: 기본적으로 활성화
    - ❌ 파일 저장: 현재 비활성화됨
    - ❌ 데이터베이스 저장: 현재 비활성화
    - ✅ 구조화된 로깅: JSON 형식 지원
    - ✅ 로그 레벨별 색상 구분
    - ✅ SQLAlchemy 로깅 제어 기능 추가
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

def configure_sqlalchemy_logging(
    enable: bool = False,
    level: str = "WARNING",
    show_sql: bool = False,
    show_parameters: bool = False,
    show_echo: bool = False
):
    """
    SQLAlchemy 로깅 설정
    
    Args:
        enable: SQLAlchemy 로깅 활성화 여부
        level: 로그 레벨 (DEBUG, INFO, WARNING, ERROR)
        show_sql: SQL 쿼리 표시 여부
        show_parameters: SQL 파라미터 표시 여부
        show_echo: SQLAlchemy echo 모드 여부
    """
    if not enable:
        # SQLAlchemy 로깅 완전 비활성화
        logging.getLogger('sqlalchemy').setLevel(logging.ERROR)
        logging.getLogger('sqlalchemy.engine').setLevel(logging.ERROR)
        logging.getLogger('sqlalchemy.pool').setLevel(logging.ERROR)
        logging.getLogger('sqlalchemy.dialects').setLevel(logging.ERROR)
        logging.getLogger('sqlalchemy.orm').setLevel(logging.ERROR)
        return
    
    # SQLAlchemy 로깅 레벨 설정
    log_level = getattr(logging, level.upper(), logging.WARNING)
    
    # SQLAlchemy 핵심 로거들 설정
    sqlalchemy_logger = logging.getLogger('sqlalchemy')
    sqlalchemy_logger.setLevel(log_level)
    
    # 엔진 로거 설정
    engine_logger = logging.getLogger('sqlalchemy.engine')
    engine_logger.setLevel(log_level)
    
    # 풀 로거 설정
    pool_logger = logging.getLogger('sqlalchemy.pool')
    pool_logger.setLevel(log_level)
    
    # 방언 로거 설정
    dialect_logger = logging.getLogger('sqlalchemy.dialects')
    dialect_logger.setLevel(log_level)
    
    # ORM 로거 설정
    orm_logger = logging.getLogger('sqlalchemy.orm')
    orm_logger.setLevel(log_level)
    
    # SQL 쿼리 표시 설정
    if show_sql:
        engine_logger.setLevel(logging.INFO)
    
    # 파라미터 표시 설정
    if show_parameters:
        engine_logger.setLevel(logging.DEBUG)

def get_logger(
    name: str = "app",
    level: str = "INFO",
    enable_file_logging: bool = False,
    log_file_path: Optional[str] = None,
    enable_json_format: bool = False,
    max_file_size: int = 10 * 1024 * 1024,  # 10MB (사용되지 않음)
    backup_count: int = 5,  # 사용되지 않음
    sqlalchemy_logging: Optional[Dict[str, Any]] = None
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
        sqlalchemy_logging: SQLAlchemy 로깅 설정 딕셔너리
    """
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
    
    # SQLAlchemy 로깅 설정
    if sqlalchemy_logging:
        configure_sqlalchemy_logging(**sqlalchemy_logging)
    else:
        # 기본적으로 SQLAlchemy 로깅 비활성화
        configure_sqlalchemy_logging(enable=False)
    
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
    
    # SQLAlchemy 로깅 설정
    sqlalchemy_enable = os.getenv("SQLALCHEMY_LOGGING", "false").lower() == "true"
    sqlalchemy_level = os.getenv("SQLALCHEMY_LOG_LEVEL", "WARNING")
    sqlalchemy_show_sql = os.getenv("SQLALCHEMY_SHOW_SQL", "false").lower() == "true"
    
    sqlalchemy_config = {
        'enable': sqlalchemy_enable,
        'level': sqlalchemy_level,
        'show_sql': sqlalchemy_show_sql,
        'show_parameters': False,
        'show_echo': False
    }
    
    return get_logger(
        name=name,
        level=log_level,
        enable_file_logging=False,  # 강제로 비활성화
        enable_json_format=json_format,
        sqlalchemy_logging=sqlalchemy_config
    )

def setup_development_logging():
    """개발 환경용 로깅 설정"""
    return get_logger(
        name="dev",
        level="DEBUG",
        sqlalchemy_logging={
            'enable': True,
            'level': 'INFO',
            'show_sql': True,
            'show_parameters': False,
            'show_echo': False
        }
    )

def setup_production_logging():
    """프로덕션 환경용 로깅 설정"""
    return get_logger(
        name="prod",
        level="WARNING",
        sqlalchemy_logging={
            'enable': False,
            'level': 'ERROR',
            'show_sql': False,
            'show_parameters': False,
            'show_echo': False
        }
    )
