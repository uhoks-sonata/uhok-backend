#!/usr/bin/env python3
"""
데이터베이스 연결 테스트 스크립트
- MariaDB 및 PostgreSQL 연결 상태 확인
"""

import asyncio

from common.database.mariadb_service import SessionLocal as MariaSessionLocal
from common.database.postgres_log import SessionLocal as PostgresLogSessionLocal
from common.database.postgres_recommend import SessionLocal as PostgresRecommendSessionLocal
from common.logger import get_logger

logger = get_logger("test_db_connection")

async def test_mariadb_connection():
    """MariaDB 연결 테스트"""
    logger.info("=== MariaDB 연결 테스트 ===")
    
    try:
        async with MariaSessionLocal() as db:
            result = await db.execute("SELECT 1 as test")
            test_value = result.scalar()
            
            if test_value == 1:
                logger.info("✅ MariaDB 연결 성공")
                return True
            else:
                logger.error("❌ MariaDB 연결 실패: 예상치 못한 결과")
                return False
                
    except Exception as e:
        logger.error(f"❌ MariaDB 연결 실패: {str(e)}")
        return False

async def test_postgres_log_connection():
    """PostgreSQL Log 연결 테스트"""
    logger.info("=== PostgreSQL Log 연결 테스트 ===")
    
    try:
        async with PostgresLogSessionLocal() as db:
            result = await db.execute("SELECT 1 as test")
            test_value = result.scalar()
            
            if test_value == 1:
                logger.info("✅ PostgreSQL Log 연결 성공")
                return True
            else:
                logger.error("❌ PostgreSQL Log 연결 실패: 예상치 못한 결과")
                return False
                
    except Exception as e:
        logger.error(f"❌ PostgreSQL Log 연결 실패: {str(e)}")
        return False

async def test_postgres_recommend_connection():
    """PostgreSQL Recommend 연결 테스트"""
    logger.info("=== PostgreSQL Recommend 연결 테스트 ===")
    
    try:
        async with PostgresRecommendSessionLocal() as db:
            result = await db.execute("SELECT 1 as test")
            test_value = result.scalar()
            
            if test_value == 1:
                logger.info("✅ PostgreSQL Recommend 연결 성공")
                return True
            else:
                logger.error("❌ PostgreSQL Recommend 연결 실패: 예상치 못한 결과")
                return False
                
    except Exception as e:
        logger.error(f"❌ PostgreSQL Recommend 연결 실패: {str(e)}")
        return False

async def test_all_connections():
    """모든 데이터베이스 연결 테스트"""
    logger.info("=== 모든 데이터베이스 연결 테스트 시작 ===")
    
    results = []
    
    # MariaDB 테스트
    mariadb_result = await test_mariadb_connection()
    results.append(("MariaDB", mariadb_result))
    
    # PostgreSQL Log 테스트
    postgres_log_result = await test_postgres_log_connection()
    results.append(("PostgreSQL Log", postgres_log_result))
    
    # PostgreSQL Recommend 테스트
    postgres_recommend_result = await test_postgres_recommend_connection()
    results.append(("PostgreSQL Recommend", postgres_recommend_result))
    
    # 결과 요약
    logger.info("\n=== 연결 테스트 결과 요약 ===")
    success_count = 0
    for db_name, result in results:
        status = "✅ 성공" if result else "❌ 실패"
        logger.info(f"{db_name}: {status}")
        if result:
            success_count += 1
    
    logger.info(f"\n총 {len(results)}개 중 {success_count}개 연결 성공")
    
    if success_count == len(results):
        logger.info("🎉 모든 데이터베이스 연결 성공!")
    else:
        logger.warning(f"⚠️ {len(results) - success_count}개 데이터베이스 연결 실패")

async def main():
    """메인 함수"""
    try:
        await test_all_connections()
    except Exception as e:
        logger.error(f"데이터베이스 연결 테스트 실패: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
