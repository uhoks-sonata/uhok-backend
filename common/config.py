# common/config.py

from pydantic import BaseSettings, Field
from functools import lru_cache

class Settings(BaseSettings):
    # 🔐 JWT 인증 설정
    jwt_secret: str = Field(..., env="JWT_SECRET")
    jwt_algorithm: str = Field("HS256", env="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(30, env="ACCESS_TOKEN_EXPIRE_MINUTES")

    # 🌐 DB 연결
    mariadb_url: str = Field(..., env="MARIADB_URL")       # 서비스용 DB
    postgres_url: str = Field(..., env="POSTGRES_URL")     # 로그, 추천용 DB

    # ⚙️ 앱 설정
    app_name: str = Field("U+콕 레시피 추천 서비스", env="APP_NAME")
    debug: bool = Field(False, env="DEBUG")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
