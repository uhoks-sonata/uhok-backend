#!/usr/bin/env python3
"""
홈쇼핑 중복 좋아요 정리 스크립트
- 중복된 좋아요 데이터를 정리하는 유틸리티
- 사용자당 상품당 하나의 좋아요만 유지
"""

import asyncio
import os
import sys

from sqlalchemy import text

# 프로젝트 루트를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from common.database.mariadb_service import SessionLocal
from common.logger import get_logger

logger = get_logger("cleanup_duplicate_likes")

async def cleanup_duplicate_likes():
    """중복 좋아요 정리"""
    logger.info("=== 홈쇼핑 중복 좋아요 정리 시작 ===")
    
    try:
        async with SessionLocal() as db:
            # 1. 중복 좋아요 확인
            check_sql = """
            SELECT 
                user_id, 
                product_id, 
                COUNT(*) as duplicate_count
            FROM homeshopping_likes 
            GROUP BY user_id, product_id 
            HAVING COUNT(*) > 1
            ORDER BY duplicate_count DESC
            """
            
            result = await db.execute(text(check_sql))
            duplicates = result.fetchall()
            
            if not duplicates:
                logger.info("중복 좋아요가 없습니다.")
                return
            
            logger.info(f"중복 좋아요 발견: {len(duplicates)}개 그룹")
            
            # 2. 중복 제거 (가장 최근 것만 유지)
            cleanup_sql = """
            DELETE h1 FROM homeshopping_likes h1
            INNER JOIN homeshopping_likes h2 
            WHERE h1.user_id = h2.user_id 
            AND h1.product_id = h2.product_id 
            AND h1.created_at < h2.created_at
            """
            
            result = await db.execute(text(cleanup_sql))
            deleted_count = result.rowcount
            await db.commit()
            
            logger.info(f"중복 좋아요 정리 완료: {deleted_count}개 삭제")
            
            # 3. 정리 후 확인
            result = await db.execute(text(check_sql))
            remaining_duplicates = result.fetchall()
            
            if not remaining_duplicates:
                logger.info("✅ 모든 중복 좋아요가 정리되었습니다.")
            else:
                logger.warning(f"⚠️ {len(remaining_duplicates)}개 그룹의 중복이 남아있습니다.")
                
    except Exception as e:
        logger.error(f"중복 좋아요 정리 실패: {str(e)}")
        raise

async def main():
    """메인 함수"""
    try:
        await cleanup_duplicate_likes()
        logger.info("=== 홈쇼핑 중복 좋아요 정리 완료 ===")
    except Exception as e:
        logger.error(f"스크립트 실행 실패: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
