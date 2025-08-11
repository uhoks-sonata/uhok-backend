# common/config.py

import os
from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache
from common.logger import get_logger

logger = get_logger("config")

class Settings(BaseSettings):
    jwt_secret: str = Field(..., env="JWT_SECRET")
    jwt_algorithm: str = Field(..., env="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(..., env="ACCESS_TOKEN_EXPIRE_MINUTES")

    mariadb_auth_url: str = Field(..., env="MARIADB_AUTH_URL")
    mariadb_auth_migrate_url: str = Field(..., env="MARIADB_AUTH_MIGRATE_URL")
    mariadb_service_url: str = Field(..., env="MARIADB_SERVICE_URL")

    postgres_recommend_url: str = Field(..., env="POSTGRES_RECOMMEND_URL")
    postgres_log_url: str = Field(..., env="POSTGRES_LOG_URL")
    postgres_log_migrate_url: str = Field(..., env="POSTGRES_LOG_MIGRATE_URL")

    log_api_url: str = Field(..., env="LOG_API_URL")

    app_name: str = Field(..., env="APP_NAME")
    debug: bool = Field(..., env="DEBUG")

    class Config:
        env_file = os.path.join(os.path.dirname(__file__), "..", ".env")
        env_file_encoding = "utf-8"
        extra = "ignore"  # 정의되지 않은 환경변수 무시

@lru_cache()
def get_settings() -> Settings:
    logger.debug("환경 변수에서 애플리케이션 설정 로드 중")
    try:
        settings = Settings()
        logger.info(f"설정 로드 완료: 앱명={settings.app_name}, 디버그={settings.debug}")
        logger.debug(f"데이터베이스 URL 설정됨: MariaDB auth, MariaDB service, PostgreSQL recommend, PostgreSQL log")
        return settings
    except Exception as e:
        logger.error(f"설정 로드 실패: {str(e)}")
        raise
