# test_config.py
from common.config import get_settings

settings = get_settings()
print("JWT_SECRET:", settings.jwt_secret)
print("JWT_ALGORITHM:", settings.jwt_algorithm)

print("MARIADB_AUTH_URL:", settings.mariadb_auth_url)
