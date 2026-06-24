#!/usr/bin/env python3
"""
PostgreSQL 데이터베이스 테스트 스크립트
- PostgreSQL 연결 및 기본 쿼리 테스트
"""

import asyncio

from common.database.postgres_log import SessionLocal as PostgresLogSessionLocal
from common.database.postgres_recommend import SessionLocal as PostgresRecommendSessionLocal
from common.logger import get_logger

logger = get_logger("test_db_postgres")

async def test_postgres_log_queries():
    """PostgreSQL Log 쿼리 테스트"""
    logger.info("=== PostgreSQL Log 쿼리 테스트 ===")
    
    try:
        async with PostgresLogSessionLocal() as db:
            # 테이블 존재 확인
            tables_query = """
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name
            """
            
            result = await db.execute(tables_query)
            tables = result.fetchall()
            
            logger.info(f"PostgreSQL Log 테이블 목록: {[table[0] for table in tables]}")
            
            # 사용자 활동 로그 테이블 확인
            if any('user_activity_log' in str(table) for table in tables):
                count_query = "SELECT COUNT(*) FROM user_activity_log"
                result = await db.execute(count_query)
                count = result.scalar()
                logger.info(f"user_activity_log 레코드 수: {count}")
            
            logger.info("✅ PostgreSQL Log 쿼리 테스트 성공")
            return True
            
    except Exception as e:
        logger.error(f"❌ PostgreSQL Log 쿼리 테스트 실패: {str(e)}")
        return False

async def test_postgres_recommend_queries():
    """PostgreSQL Recommend 쿼리 테스트"""
    logger.info("=== PostgreSQL Recommend 쿼리 테스트 ===")
    
    try:
        async with PostgresRecommendSessionLocal() as db:
            # 테이블 존재 확인
            tables_query = """
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name
            """
            
            result = await db.execute(tables_query)
            tables = result.fetchall()
            
            logger.info(f"PostgreSQL Recommend 테이블 목록: {[table[0] for table in tables]}")
            
            # 벡터 확장 확인
            extension_query = "SELECT * FROM pg_extension WHERE extname = 'vector'"
            result = await db.execute(extension_query)
            vector_extension = result.fetchall()
            
            if vector_extension:
                logger.info("✅ pgvector 확장이 설치되어 있습니다.")
            else:
                logger.warning("⚠️ pgvector 확장이 설치되어 있지 않습니다.")
            
            logger.info("✅ PostgreSQL Recommend 쿼리 테스트 성공")
            return True
            
    except Exception as e:
        logger.error(f"❌ PostgreSQL Recommend 쿼리 테스트 실패: {str(e)}")
        return False

async def test_all_postgres():
    """모든 PostgreSQL 테스트"""
    logger.info("=== PostgreSQL 데이터베이스 테스트 시작 ===")
    
    results = []
    
    # PostgreSQL Log 테스트
    log_result = await test_postgres_log_queries()
    results.append(("PostgreSQL Log", log_result))
    
    # PostgreSQL Recommend 테스트
    recommend_result = await test_postgres_recommend_queries()
    results.append(("PostgreSQL Recommend", recommend_result))
    
    # 결과 요약
    logger.info("\n=== PostgreSQL 테스트 결과 요약 ===")
    success_count = 0
    for db_name, result in results:
        status = "✅ 성공" if result else "❌ 실패"
        logger.info(f"{db_name}: {status}")
        if result:
            success_count += 1
    
    logger.info(f"\n총 {len(results)}개 중 {success_count}개 테스트 성공")
    
    if success_count == len(results):
        logger.info("🎉 모든 PostgreSQL 테스트 성공!")
    else:
        logger.warning(f"⚠️ {len(results) - success_count}개 PostgreSQL 테스트 실패")

async def main():
    """메인 함수"""
    try:
        await test_all_postgres()
    except Exception as e:
        logger.error(f"PostgreSQL 테스트 실패: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
