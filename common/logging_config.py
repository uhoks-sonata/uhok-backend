# logging_config.py
"""
로깅 설정을 위한 환경별 설정 파일
"""

import os
from typing import Dict, Any

# 환경별 SQLAlchemy 로깅 설정
SQLALCHEMY_LOGGING_CONFIGS = {
    'development': {
        'enable': False,
        'level': 'ERROR',
        'show_sql': False,
        'show_parameters': False,
        'show_echo': False
    },
    'testing': {
        'enable': False,
        'level': 'ERROR',
        'show_sql': False,
        'show_parameters': False,
        'show_echo': False
    },
    'staging': {
        'enable': False,
        'level': 'ERROR',
        'show_sql': False,
        'show_parameters': False,
        'show_echo': False
    },
    'production': {
        'enable': False,
        'level': 'ERROR',
        'show_sql': False,
        'show_parameters': False,
        'show_echo': False
    }
}

def get_sqlalchemy_logging_config(environment: str = None) -> Dict[str, Any]:
    """
    환경에 따른 SQLAlchemy 로깅 설정 반환
    
    Args:
        environment: 환경명 (development, testing, staging, production)
    
    Returns:
        SQLAlchemy 로깅 설정 딕셔너리
    """
    if not environment:
        environment = os.getenv('ENVIRONMENT', 'development')
    
    return SQLALCHEMY_LOGGING_CONFIGS.get(
        environment.lower(), 
        SQLALCHEMY_LOGGING_CONFIGS['development']
    )

def get_environment_logging_config(environment: str = None) -> Dict[str, Any]:
    """
    환경에 따른 전체 로깅 설정 반환
    
    Args:
        environment: 환경명
    
    Returns:
        전체 로깅 설정 딕셔너리
    """
    if not environment:
        environment = os.getenv('ENVIRONMENT', 'development')
    
    base_config = {
        'development': {
            'level': 'DEBUG',
            'enable_json_format': False,
            'sqlalchemy_logging': get_sqlalchemy_logging_config('development')
        },
        'testing': {
            'level': 'INFO',
            'enable_json_format': False,
            'sqlalchemy_logging': get_sqlalchemy_logging_config('testing')
        },
        'staging': {
            'level': 'WARNING',
            'enable_json_format': True,
            'sqlalchemy_logging': get_sqlalchemy_logging_config('staging')
        },
        'production': {
            'level': 'WARNING',
            'enable_json_format': True,
            'sqlalchemy_logging': get_sqlalchemy_logging_config('production')
        }
    }
    
    return base_config.get(
        environment.lower(), 
        base_config['development']
    )

# 환경 변수로 SQLAlchemy 로깅 제어
def get_sqlalchemy_logging_from_env() -> Dict[str, Any]:
    """
    환경 변수에서 SQLAlchemy 로깅 설정 읽기
    """
    return {
        'enable': os.getenv('SQLALCHEMY_LOGGING', 'false').lower() == 'true',
        'level': os.getenv('SQLALCHEMY_LOG_LEVEL', 'WARNING'),
        'show_sql': os.getenv('SQLALCHEMY_SHOW_SQL', 'false').lower() == 'true',
        'show_parameters': os.getenv('SQLALCHEMY_SHOW_PARAMETERS', 'false').lower() == 'true',
        'show_echo': os.getenv('SQLALCHEMY_ECHO', 'false').lower() == 'true'
    }

# SQLAlchemy 로깅 완전 비활성화
def disable_sqlalchemy_logging():
    """
    SQLAlchemy 로깅을 완전히 비활성화
    """
    import logging
    
    sqlalchemy_loggers = [
        'sqlalchemy',
        'sqlalchemy.engine',
        'sqlalchemy.pool',
        'sqlalchemy.dialects',
        'sqlalchemy.orm',
        'sqlalchemy.sql',
        'sqlalchemy.engine.base',
        'sqlalchemy.engine.default',
        'sqlalchemy.engine.reflection',
        'sqlalchemy.engine.result',
        'sqlalchemy.engine.strategies',
        'sqlalchemy.engine.url',
        'sqlalchemy.event',
        'sqlalchemy.interfaces',
        'sqlalchemy.log',
        'sqlalchemy.pool.base',
        'sqlalchemy.pool.dbapi_proxy',
        'sqlalchemy.pool.manage',
        'sqlalchemy.pool.null',
        'sqlalchemy.pool.queue',
        'sqlalchemy.pool.singleton',
        'sqlalchemy.pool.static',
        'sqlalchemy.pool.threadlocal',
        'sqlalchemy.processors',
        'sqlalchemy.schema',
        'sqlalchemy.sql.base',
        'sqlalchemy.sql.compiler',
        'sqlalchemy.sql.ddl',
        'sqlalchemy.sql.default_comparator',
        'sqlalchemy.sql.dml',
        'sqlalchemy.sql.elements',
        'sqlalchemy.sql.expression',
        'sqlalchemy.sql.functions',
        'sqlalchemy.sql.naming',
        'sqlalchemy.sql.operators',
        'sqlalchemy.sql.selectable',
        'sqlalchemy.sql.schema',
        'sqlalchemy.sql.sqltypes',
        'sqlalchemy.sql.table',
        'sqlalchemy.sql.text',
        'sqlalchemy.sql.util',
        'sqlalchemy.sql.visitors',
        'sqlalchemy.types',
        'sqlalchemy.util',
        'sqlalchemy.util.deprecations',
        'sqlalchemy.util.langhelpers',
        'sqlalchemy.util.queue'
    ]
    
    for logger_name in sqlalchemy_loggers:
        logging.getLogger(logger_name).setLevel(logging.ERROR)
        logging.getLogger(logger_name).propagate = False

# SQLAlchemy 로깅 레벨만 조정
def set_sqlalchemy_log_level(level: str = 'WARNING'):
    """
    SQLAlchemy 로깅 레벨만 설정
    
    Args:
        level: 로그 레벨 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    import logging
    
    log_level = getattr(logging, level.upper(), logging.WARNING)
    
    sqlalchemy_loggers = [
        'sqlalchemy',
        'sqlalchemy.engine',
        'sqlalchemy.pool',
        'sqlalchemy.dialects',
        'sqlalchemy.orm'
    ]
    
    for logger_name in sqlalchemy_loggers:
        logging.getLogger(logger_name).setLevel(log_level)
