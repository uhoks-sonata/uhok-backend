# common/config.py

import os
from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache

class Settings(BaseSettings):
    jwt_secret: str = Field(..., env="JWT_SECRET")
    jwt_algorithm: str = Field("HS256", env="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(..., env="ACCESS_TOKEN_EXPIRE_MINUTES")

    mariadb_url: str = Field(..., env="MARIADB_URL")
    postgres_url: str = Field(..., env="POSTGRES_URL")

    app_name: str = Field("U+콕 레시피 추천 서비스", env="APP_NAME")
    debug: bool = Field(False, env="DEBUG")

    class Config:
        env_file = os.path.join(os.path.dirname(__file__), "..", ".env")
        env_file_encoding = "utf-8"

@lru_cache()
def get_settings() -> Settings:
    return Settings()
