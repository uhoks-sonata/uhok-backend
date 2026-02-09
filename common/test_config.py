#!/usr/bin/env python3
"""
설정 테스트 스크립트
- 환경 변수 및 설정 값 검증
"""

import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
sys.path.append(str(Path(__file__).parent.parent))

from common.config import get_settings
from common.logger import get_logger

logger = get_logger("test_config")

def test_config():
    """설정 값 테스트"""
    logger.info("=== 설정 테스트 시작 ===")
    
    try:
        settings = get_settings()
        
        # 데이터베이스 설정 확인
        logger.info(f"MariaDB Service URL: {settings.mariadb_service_url}")
        logger.info(f"PostgreSQL Log URL: {settings.postgres_log_url}")
        logger.info(f"PostgreSQL Recommend URL: {settings.postgres_recommend_url}")
        
        # Redis 설정 확인
        logger.info(f"Redis URL: {getattr(settings, 'redis_url', 'Not configured')}")
        
        # JWT 설정 확인
        logger.info(f"JWT Secret Key: {'설정됨' if settings.jwt_secret_key else '미설정'}")
        logger.info(f"JWT Algorithm: {settings.jwt_algorithm}")
        logger.info(f"JWT Expire Minutes: {settings.jwt_expire_minutes}")
        
        logger.info("✅ 설정 테스트 완료")
        
    except Exception as e:
        logger.error(f"설정 테스트 실패: {str(e)}")
        raise

if __name__ == "__main__":
    test_config()
