#!/usr/bin/env python3
"""
홈쇼핑 중복 찜 데이터 정리 스크립트
- 같은 사용자가 같은 상품을 여러 번 찜한 중복 데이터를 정리
- 가장 오래된 찜만 남기고 나머지는 삭제
"""

import asyncio
import sys
import os
from datetime import datetime
from sqlalchemy import select, and_, delete
from sqlalchemy.ext.asyncio import AsyncSession

# 프로젝트 루트를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from common.database.mariadb_service import get_maria_service_db, SessionLocal
from services.homeshopping.models.homeshopping_model import HomeshoppingLikes, HomeshoppingNotification
from common.logger import get_logger

logger = get_logger("cleanup_duplicate_likes")

async def cleanup_duplicate_likes():
    """중복 찜 데이터 정리"""
    logger.info("중복 찜 데이터 정리 시작")
    
    try:
        async with SessionLocal() as db:
            # 중복 데이터 조회
            duplicate_query = """
                SELECT user_id, product_id, COUNT(*) as count
                FROM HOMESHOPPING_LIKES
                GROUP BY user_id, product_id
                HAVING COUNT(*) > 1
                ORDER BY user_id, product_id
            """
            
            result = await db.execute(duplicate_query)
            duplicates = result.fetchall()
            
            if not duplicates:
                logger.info("중복 찜 데이터가 없습니다.")
                return
            
            logger.info(f"중복 찜 데이터 {len(duplicates)}건 발견")
            
            total_deleted = 0
            
            for duplicate in duplicates:
                user_id, product_id, count = duplicate
                logger.info(f"사용자 {user_id}, 상품 {product_id}: {count}개 중복")
                
                # 해당 사용자/상품의 모든 찜 데이터 조회
                likes_result = await db.execute(
                    select(HomeshoppingLikes).where(
                        and_(
                            HomeshoppingLikes.user_id == user_id,
                            HomeshoppingLikes.product_id == product_id
                        )
                    ).order_by(HomeshoppingLikes.homeshopping_like_created_at)
                )
                
                all_likes = likes_result.scalars().all()
                
                # 가장 오래된 것만 남기고 나머지는 삭제
                likes_to_delete = all_likes[1:]
                
                for like_to_delete in likes_to_delete:
                    # 관련 방송 알림도 함께 삭제
                    await delete_broadcast_notifications_for_like(db, like_to_delete.homeshopping_like_id)
                    
                    # 찜 레코드 삭제
                    await db.delete(like_to_delete)
                    total_deleted += 1
                
                logger.info(f"사용자 {user_id}, 상품 {product_id}: {len(likes_to_delete)}개 중복 데이터 삭제 완료")
            
            # 변경사항 커밋
            await db.commit()
            logger.info(f"중복 찜 데이터 정리 완료: 총 {total_deleted}개 삭제")
            
    except Exception as e:
        logger.error(f"중복 찜 데이터 정리 실패: {str(e)}")
        raise

async def delete_broadcast_notifications_for_like(db: AsyncSession, like_id: int):
    """특정 찜에 대한 방송 알림 삭제"""
    try:
        # 방송 시작 알림 삭제
        stmt = delete(HomeshoppingNotification).where(
            and_(
                HomeshoppingNotification.homeshopping_like_id == like_id,
                HomeshoppingNotification.notification_type == "broadcast_start"
            )
        )
        
        result = await db.execute(stmt)
        deleted_count = result.rowcount
        
        if deleted_count > 0:
            logger.debug(f"방송 알림 {deleted_count}개 삭제: like_id={like_id}")
            
    except Exception as e:
        logger.warning(f"방송 알림 삭제 실패: like_id={like_id}, error={str(e)}")

async def add_unique_constraint():
    """중복 방지를 위한 유니크 제약 조건 추가 (선택사항)"""
    logger.info("유니크 제약 조건 추가 시도")
    
    try:
        async with SessionLocal() as db:
            # MariaDB에서 유니크 인덱스 추가
            add_constraint_sql = """
                ALTER TABLE HOMESHOPPING_LIKES 
                ADD UNIQUE INDEX idx_user_product_unique (user_id, product_id)
            """
            
            await db.execute(add_constraint_sql)
            await db.commit()
            logger.info("유니크 제약 조건 추가 완료")
            
    except Exception as e:
        logger.warning(f"유니크 제약 조건 추가 실패 (이미 존재할 수 있음): {str(e)}")

async def main():
    """메인 함수"""
    logger.info("=== 홈쇼핑 중복 찜 데이터 정리 시작 ===")
    
    try:
        # 1. 중복 데이터 정리
        await cleanup_duplicate_likes()
        
        # 2. 유니크 제약 조건 추가 (선택사항)
        user_input = input("\n유니크 제약 조건을 추가하시겠습니까? (y/N): ").strip().lower()
        if user_input in ['y', 'yes']:
            await add_unique_constraint()
        
        logger.info("=== 중복 찜 데이터 정리 완료 ===")
        
    except Exception as e:
        logger.error(f"스크립트 실행 실패: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
