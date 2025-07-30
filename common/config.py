# config.py
"""
환경 변수 및 설정값 로딩을 위한 Pydantic 설정 클래스
"""
from pydantic import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "U+콕 홈쇼핑 추천 서비스"
    DEBUG: bool = True
    DATABASE_URL: str = "mysql://user:password@localhost/db"
    JWT_SECRET: str = "your_secret_key"

    class Config:
        env_file = ".env"

settings = Settings()
