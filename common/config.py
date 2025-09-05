# common/config.py
"""
애플리케이션 설정 관리 모듈

이 모듈은 애플리케이션의 모든 설정값을 중앙에서 관리합니다.
환경 변수, 데이터베이스 연결 정보, JWT 설정 등을 포함합니다.

주요 기능:
- 환경 변수 기반 설정 로드
- 데이터베이스 연결 설정 파싱
- JWT 인증 설정 관리
- 로깅 설정 관리

사용법:
    from common.config import get_settings, get_mariadb_config
    
    settings = get_settings()
    db_config = get_mariadb_config()
"""

import os
from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache
from common.logger import get_logger
from typing import Optional

# 로거 초기화 (SQLAlchemy 로깅 비활성화)
logger = get_logger("config", sqlalchemy_logging={'enable': False})

class Settings(BaseSettings):
    """
    애플리케이션 설정 클래스
    
    Pydantic BaseSettings를 상속받아 환경 변수에서 설정값을 자동으로 로드합니다.
    모든 설정값은 환경 변수와 매핑되며, 타입 검증이 자동으로 수행됩니다.
    """
    
    # JWT 인증 관련 설정
    jwt_secret: str = Field(..., env="JWT_SECRET", description="JWT 토큰 서명에 사용되는 비밀키")
    jwt_algorithm: str = Field(..., env="JWT_ALGORITHM", description="JWT 토큰 서명 알고리즘 (예: HS256)")
    access_token_expire_minutes: int = Field(..., env="ACCESS_TOKEN_EXPIRE_MINUTES", description="액세스 토큰 만료 시간(분)")
    
    # 웹훅 관련 설정
    webhook_base_url: str = Field(..., env="WEBHOOK_BASE_URL", description="웹훅 콜백 URL의 기본 도메인")
    # webhook_secret: Optional[str] = Field(None, env="WEBHOOK_SECRET", description="웹훅 서명 검증용 시크릿 키")
    
    # MariaDB 데이터베이스 연결 설정
    mariadb_auth_url: str = Field(..., env="MARIADB_AUTH_URL", description="사용자 인증용 MariaDB 연결 URL")
    mariadb_auth_migrate_url: str = Field(..., env="MARIADB_AUTH_MIGRATE_URL", description="인증 DB 마이그레이션용 연결 URL")
    mariadb_service_url: str = Field(..., env="MARIADB_SERVICE_URL", description="서비스 데이터용 MariaDB 연결 URL")
    
    # PostgreSQL 데이터베이스 연결 설정
    postgres_recommend_url: str = Field(..., env="POSTGRES_RECOMMEND_URL", description="추천 시스템용 PostgreSQL 연결 URL")
    postgres_log_url: str = Field(..., env="POSTGRES_LOG_URL", description="로그 저장용 PostgreSQL 연결 URL")
    postgres_log_migrate_url: str = Field(..., env="POSTGRES_LOG_MIGRATE_URL", description="로그 DB 마이그레이션용 연결 URL")
    
    # Redis 캐시 설정
    redis_url: str = Field("redis://redis:6379/0", env="REDIS_URL", description="Redis 연결 URL")

    # ML 서비스 설정
    ml_mode: str = Field("remote_embed", env="ML_MODE", description="ML 서비스 모드")
    ml_service_url: str = Field("http://ml-inference:8001", env="ML_SERVICE_URL", description="ML 서비스 URL")
    
    # 외부 API 설정 (로그 전송 불필요하므로 제거)
    
    # 애플리케이션 기본 설정
    app_name: str = Field(..., env="APP_NAME", description="애플리케이션 이름")
    debug: bool = Field(..., env="DEBUG", description="디버그 모드 활성화 여부")

    class Config:
        """Pydantic 설정 클래스"""
        env_file = os.path.join(os.path.dirname(__file__), "..", ".env")  # .env 파일 경로
        env_file_encoding = "utf-8"  # 환경 변수 파일 인코딩
        extra = "ignore"  # 정의되지 않은 환경변수 무시

@lru_cache()
def get_settings() -> Settings:
    """
    애플리케이션 설정을 로드하고 반환하는 함수
    
    LRU 캐시를 사용하여 설정 로딩 성능을 최적화합니다.
    환경 변수에서 설정값을 읽어 Settings 인스턴스를 생성합니다.
    
    Returns:
        Settings: 로드된 설정 객체
        
    Raises:
        Exception: 설정 로드 실패 시 예외 발생
        
    Example:
        >>> settings = get_settings()
        >>> print(settings.app_name)
        >>> print(settings.debug)
    """
    logger.debug("환경 변수에서 애플리케이션 설정 로드 중")
    try:
        settings = Settings()
        logger.info(f"설정 로드 완료: 앱명={settings.app_name}, 디버그={settings.debug}")
        logger.debug(f"데이터베이스 URL 설정됨: MariaDB auth, MariaDB service, PostgreSQL recommend, PostgreSQL log")
        return settings
    except Exception as e:
        logger.error(f"설정 로드 실패: {str(e)}")
        raise

def get_mariadb_config() -> dict:
    """
    MariaDB 연결 설정을 딕셔너리 형태로 반환
    
    mariadb_service_url을 파싱하여 host, port, user, password, database 정보를 추출합니다.
    이 함수는 TEST_MTRL 테이블이 있는 데이터베이스 연결에 사용됩니다.
    
    Returns:
        dict: MariaDB 연결 설정 딕셔너리
            - host: 데이터베이스 호스트 주소
            - port: 데이터베이스 포트 번호
            - user: 데이터베이스 사용자명
            - password: 데이터베이스 비밀번호
            - database: 데이터베이스명
            
    Example:
        >>> config = get_mariadb_config()
        >>> print(f"호스트: {config['host']}")
        >>> print(f"포트: {config['port']}")
        >>> print(f"사용자: {config['user']}")
        >>> print(f"데이터베이스: {config['database']}")
        
    Note:
        mariadb_service_url 형식: mysql+pymysql://user:password@host:port/database
        포트가 지정되지 않은 경우 기본값 3306을 사용합니다.
    """
    from urllib.parse import urlparse
    
    settings = get_settings()
    
    # mariadb_service_url을 파싱하여 연결 정보 추출
    # 예: mysql+pymysql://user:password@host:port/database
    url = urlparse(settings.mariadb_service_url.replace('mysql+pymysql://', ''))
    
    # URL에서 사용자명과 비밀번호 추출
    user_password = url.netloc.split('@')[0]
    user, password = user_password.split(':') if ':' in user_password else (user_password, '')
    
    # 호스트와 포트 추출
    host_port = url.netloc.split('@')[1] if '@' in url.netloc else url.netloc
    host, port = host_port.split(':') if ':' in host_port else (host_port, '3306')
    
    # 데이터베이스명 추출
    database = url.path.lstrip('/')
    
    return {
        'host': host,
        'port': int(port),
        'user': user,
        'password': password,
        'database': database
    }
