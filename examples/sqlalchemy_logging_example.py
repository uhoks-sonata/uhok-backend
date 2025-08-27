# sqlalchemy_logging_example.py
"""
SQLAlchemy 로깅 제어 사용 예시
"""

from common.logger import get_logger, setup_development_logging, setup_production_logging
from common.logging_config import (
    get_sqlalchemy_logging_config,
    get_environment_logging_config,
    disable_sqlalchemy_logging,
    set_sqlalchemy_log_level
)

def example_basic_usage():
    """기본 사용법 예시"""
    print("=== 기본 사용법 예시 ===")
    
    # 1. SQLAlchemy 로깅 비활성화 (기본값)
    logger1 = get_logger("app1")
    logger1.info("SQLAlchemy 로깅이 비활성화된 로거")
    
    # 2. SQLAlchemy 로깅 활성화
    logger2 = get_logger(
        "app2",
        sqlalchemy_logging={
            'enable': True,
            'level': 'INFO',
            'show_sql': True,
            'show_parameters': False,
            'show_echo': False
        }
    )
    logger2.info("SQLAlchemy 로깅이 활성화된 로거")
    
    print()

def example_environment_based():
    """환경별 설정 예시"""
    print("=== 환경별 설정 예시 ===")
    
    # 개발 환경 설정
    dev_config = get_environment_logging_config('development')
    dev_logger = get_logger("dev_app", **dev_config)
    dev_logger.info("개발 환경 로거 - SQL 쿼리 표시됨")
    
    # 프로덕션 환경 설정
    prod_config = get_environment_logging_config('production')
    prod_logger = get_logger("prod_app", **prod_config)
    prod_logger.info("프로덕션 환경 로거 - SQLAlchemy 로깅 비활성화")
    
    print()

def example_quick_setup():
    """빠른 설정 함수 예시"""
    print("=== 빠른 설정 함수 예시 ===")
    
    # 개발 환경용 로거
    dev_logger = setup_development_logging()
    dev_logger.info("개발 환경용 로거 (자동 설정)")
    
    # 프로덕션 환경용 로거
    prod_logger = setup_production_logging()
    prod_logger.info("프로덕션 환경용 로거 (자동 설정)")
    
    print()

def example_manual_control():
    """수동 제어 예시"""
    print("=== 수동 제어 예시 ===")
    
    # SQLAlchemy 로깅 완전 비활성화
    disable_sqlalchemy_logging()
    print("SQLAlchemy 로깅이 완전히 비활성화되었습니다.")
    
    # SQLAlchemy 로깅 레벨만 조정
    set_sqlalchemy_log_level('WARNING')
    print("SQLAlchemy 로깅 레벨이 WARNING으로 설정되었습니다.")
    
    print()

def example_custom_config():
    """커스텀 설정 예시"""
    print("=== 커스텀 설정 예시 ===")
    
    # 커스텀 SQLAlchemy 로깅 설정
    custom_sqlalchemy_config = {
        'enable': True,
        'level': 'DEBUG',
        'show_sql': True,
        'show_parameters': True,  # 파라미터도 표시
        'show_echo': False
    }
    
    custom_logger = get_logger(
        "custom_app",
        level="DEBUG",
        sqlalchemy_logging=custom_sqlalchemy_config
    )
    custom_logger.info("커스텀 설정된 로거 - SQL 쿼리와 파라미터 모두 표시")
    
    print()

def main():
    """메인 함수"""
    print("SQLAlchemy 로깅 제어 예시\n")
    
    example_basic_usage()
    example_environment_based()
    example_quick_setup()
    example_manual_control()
    example_custom_config()
    
    print("모든 예시가 완료되었습니다.")

if __name__ == "__main__":
    main()
