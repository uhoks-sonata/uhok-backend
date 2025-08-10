# test_config.py
from common.config import get_settings
from common.logger import get_logger

settings = get_settings()
logger = get_logger("test_config")

logger.info(f"JWT_SECRET: {settings.jwt_secret}")
logger.info(f"JWT_ALGORITHM: {settings.jwt_algorithm}")
logger.info(f"MARIADB_AUTH_URL: {settings.mariadb_auth_url}")
