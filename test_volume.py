#!/usr/bin/env python3
"""
볼륨 테스트 스크립트
- 데이터베이스 테이블 크기 및 데이터량 확인
"""

import asyncio
import sys
import os
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
sys.path.append(str(Path(__file__).parent))

from common.database.mariadb_service import SessionLocal as MariaSessionLocal
from common.database.postgres_log import SessionLocal as PostgresLogSessionLocal
from common.database.postgres_recommend import SessionLocal as PostgresRecommendSessionLocal
from common.logger import get_logger

logger = get_logger("test_volume")

async def test_mariadb_volume():
    """MariaDB 테이블 볼륨 확인"""
    logger.info("=== MariaDB 테이블 볼륨 확인 ===")
    
    try:
        async with MariaSessionLocal() as db:
            # 홈쇼핑 관련 테이블 크기 확인
            volume_query = """
            SELECT 
                table_name,
                table_rows,
                ROUND(((data_length + index_length) / 1024 / 1024), 2) AS 'Size (MB)'
            FROM information_schema.tables 
            WHERE table_schema = DATABASE()
            AND table_name IN (
                'FCT_HOMESHOPPING_LIST',
                'HOMESHOPPING_INFO', 
                'FCT_HOMESHOPPING_PRODUCT_INFO',
                'HOMESHOPPING_CLASSIFY'
            )
            ORDER BY (data_length + index_length) DESC
            """
            
            result = await db.execute(volume_query)
            tables = result.fetchall()
            
            logger.info("MariaDB 홈쇼핑 테이블 볼륨:")
            for table in tables:
                logger.info(f"  {table[0]}: {table[1]:,} rows, {table[2]} MB")
            
            # 전체 데이터베이스 크기
            db_size_query = """
            SELECT 
                ROUND(SUM(data_length + index_length) / 1024 / 1024, 2) AS 'DB Size (MB)'
            FROM information_schema.tables 
            WHERE table_schema = DATABASE()
            """
            
            result = await db.execute(db_size_query)
            db_size = result.scalar()
            logger.info(f"전체 MariaDB 크기: {db_size} MB")
            
            logger.info("✅ MariaDB 볼륨 확인 완료")
            return True
            
    except Exception as e:
        logger.error(f"❌ MariaDB 볼륨 확인 실패: {str(e)}")
        return False

async def test_postgres_volume():
    """PostgreSQL 테이블 볼륨 확인"""
    logger.info("=== PostgreSQL 테이블 볼륨 확인 ===")
    
    try:
        # PostgreSQL Log
        async with PostgresLogSessionLocal() as db:
            log_volume_query = """
            SELECT 
                schemaname,
                tablename,
                n_tup_ins as inserts,
                n_tup_upd as updates,
                n_tup_del as deletes,
                n_live_tup as live_tuples,
                n_dead_tup as dead_tuples
            FROM pg_stat_user_tables
            ORDER BY n_live_tup DESC
            """
            
            result = await db.execute(log_volume_query)
            tables = result.fetchall()
            
            logger.info("PostgreSQL Log 테이블 통계:")
            for table in tables:
                logger.info(f"  {table[1]}: {table[5]:,} live tuples")
        
        # PostgreSQL Recommend
        async with PostgresRecommendSessionLocal() as db:
            recommend_volume_query = """
            SELECT 
                schemaname,
                tablename,
                n_tup_ins as inserts,
                n_tup_upd as updates,
                n_tup_del as deletes,
                n_live_tup as live_tuples,
                n_dead_tup as dead_tuples
            FROM pg_stat_user_tables
            ORDER BY n_live_tup DESC
            """
            
            result = await db.execute(recommend_volume_query)
            tables = result.fetchall()
            
            logger.info("PostgreSQL Recommend 테이블 통계:")
            for table in tables:
                logger.info(f"  {table[1]}: {table[5]:,} live tuples")
        
        logger.info("✅ PostgreSQL 볼륨 확인 완료")
        return True
        
    except Exception as e:
        logger.error(f"❌ PostgreSQL 볼륨 확인 실패: {str(e)}")
        return False

async def test_all_volumes():
    """모든 데이터베이스 볼륨 테스트"""
    logger.info("=== 데이터베이스 볼륨 테스트 시작 ===")
    
    results = []
    
    # MariaDB 볼륨 테스트
    mariadb_result = await test_mariadb_volume()
    results.append(("MariaDB", mariadb_result))
    
    # PostgreSQL 볼륨 테스트
    postgres_result = await test_postgres_volume()
    results.append(("PostgreSQL", postgres_result))
    
    # 결과 요약
    logger.info("\n=== 볼륨 테스트 결과 요약 ===")
    success_count = 0
    for db_name, result in results:
        status = "✅ 성공" if result else "❌ 실패"
        logger.info(f"{db_name}: {status}")
        if result:
            success_count += 1
    
    logger.info(f"\n총 {len(results)}개 중 {success_count}개 테스트 성공")
    
    if success_count == len(results):
        logger.info("🎉 모든 볼륨 테스트 성공!")
    else:
        logger.warning(f"⚠️ {len(results) - success_count}개 볼륨 테스트 실패")

async def main():
    """메인 함수"""
    try:
        await test_all_volumes()
    except Exception as e:
        logger.error(f"볼륨 테스트 실패: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
