from datetime import datetime
from typing import List, Tuple

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from services.kok.models.interaction_model import KokNotification, KokSearchHistory
from services.kok.models.product_model import KokPriceInfo, KokProductInfo

from .shared import logger

async def search_kok_products(
    db: AsyncSession,
    keyword: str,
    page: int = 1,
    size: int = 20
) -> Tuple[List[dict], int]:
    """
    키워드로 콕 상품 검색 (최적화: 윈도우 함수 사용으로 N+1 문제 해결)
    """
    try:
        # logger.info(f"상품 검색 시작: keyword='{keyword}', page={page}, size={size}")
        offset = (page - 1) * size
        
        # 최적화된 검색 쿼리: 윈도우 함수를 사용하여 상품 정보와 최신 가격 정보를 한 번에 조회
        windowed_query = (
            select(
                KokProductInfo.kok_product_id,
                KokProductInfo.kok_thumbnail,
                KokProductInfo.kok_product_name,
                KokProductInfo.kok_store_name,
                KokProductInfo.kok_product_price,
                KokProductInfo.kok_review_cnt,
                KokProductInfo.kok_review_score,
                KokPriceInfo.kok_discount_rate,
                KokPriceInfo.kok_discounted_price,
                func.row_number().over(
                    partition_by=KokPriceInfo.kok_product_id,
                    order_by=KokPriceInfo.kok_price_id.desc()
                ).label('rn')
            )
            .join(
                KokPriceInfo,
                KokProductInfo.kok_product_id == KokPriceInfo.kok_product_id
            )
            .where(
                KokProductInfo.kok_product_name.ilike(f"%{keyword}%") |
                KokProductInfo.kok_store_name.ilike(f"%{keyword}%")
            )
            .order_by(KokProductInfo.kok_product_id.desc())
        )
        
        # 최신 가격만 필터링하여 검색 결과 조회
        subquery = windowed_query.subquery()
        search_stmt = (
            select(
                subquery.c.kok_product_id,
                subquery.c.kok_thumbnail,
                subquery.c.kok_product_name,
                subquery.c.kok_store_name,
                subquery.c.kok_product_price,
                subquery.c.kok_review_cnt,
                subquery.c.kok_review_score,
                subquery.c.kok_discount_rate,
                subquery.c.kok_discounted_price
            )
            .select_from(subquery)
            .where(subquery.c.rn == 1)
            .offset(offset)
            .limit(size)
        )
        
        try:
            results = (await db.execute(search_stmt)).all()
        except Exception as e:
            logger.error(f"상품 검색 SQL 실행 실패: keyword={keyword}, page={page}, size={size}, error={str(e)}")
            raise
        
        # 총 개수 조회 (최적화: 윈도우 함수 사용)
        count_windowed_query = (
            select(
                KokProductInfo.kok_product_id,
                func.row_number().over(
                    partition_by=KokPriceInfo.kok_product_id,
                    order_by=KokPriceInfo.kok_price_id.desc()
                ).label('rn')
            )
            .join(
                KokPriceInfo,
                KokProductInfo.kok_product_id == KokPriceInfo.kok_product_id
            )
            .where(
                KokProductInfo.kok_product_name.ilike(f"%{keyword}%") |
                KokProductInfo.kok_store_name.ilike(f"%{keyword}%")
            )
        )
        
        count_subquery = count_windowed_query.subquery().alias('count_subquery')
        count_stmt = (
            select(func.count())
            .select_from(count_subquery)
            .where(count_subquery.c.rn == 1)
        )
        
        try:
            total = (await db.execute(count_stmt)).scalar()
        except Exception as e:
            logger.error(f"상품 검색 개수 조회 SQL 실행 실패: keyword={keyword}, error={str(e)}")
            total = 0
        
        # 결과 변환 (N+1 문제 해결: 이미 가격 정보가 포함됨)
        products = []
        for row in results:
            products.append({
                "kok_product_id": row.kok_product_id,
                "kok_product_name": row.kok_product_name,
                "kok_store_name": row.kok_store_name,
                "kok_thumbnail": row.kok_thumbnail,
                "kok_product_price": row.kok_product_price,
                "kok_discount_rate": row.kok_discount_rate or 0,
                "kok_discounted_price": row.kok_discounted_price or row.kok_product_price,
                "kok_review_cnt": row.kok_review_cnt,
                "kok_review_score": row.kok_review_score,
            })
        
        # logger.info(f"상품 검색 완료: keyword='{keyword}', 결과 수={len(products)}, 총 개수={total}")
        return products, total
        
    except Exception as e:
        logger.error(f"상품 검색 중 오류 발생: keyword='{keyword}', error={str(e)}")
        raise Exception(f"상품 검색 중 데이터베이스 오류가 발생했습니다: {str(e)}")


async def get_kok_search_history(
    db: AsyncSession,
    user_id: int,
    limit: int = 10
) -> List[dict]:
    """
    사용자의 검색 이력 조회
    """
    stmt = (
        select(KokSearchHistory)
        .where(KokSearchHistory.user_id == user_id)
        .order_by(KokSearchHistory.kok_searched_at.desc())
        .limit(limit)
    )
    
    try:
        results = (await db.execute(stmt)).scalars().all()
    except Exception as e:
        logger.error(f"검색 이력 조회 SQL 실행 실패: user_id={user_id}, limit={limit}, error={str(e)}")
        return []
    
    return [
        {
            "kok_history_id": history.kok_history_id,
            "user_id": history.user_id,
            "kok_keyword": history.kok_keyword,
            "kok_searched_at": history.kok_searched_at,
        }
        for history in results
    ]

async def add_kok_search_history(
    db: AsyncSession,
    user_id: int,
    keyword: str
) -> dict:
    """
    검색 이력 추가
    """
    # logger.info(f"검색 이력 추가 시작: user_id={user_id}, keyword='{keyword}'")
    
    searched_at = datetime.now()
    
    new_history = KokSearchHistory(
        user_id=user_id,
        kok_keyword=keyword,
        kok_searched_at=searched_at
    )
    
    db.add(new_history)
    await db.flush()  # commit 전에 flush로 ID 생성
    await db.refresh(new_history)
    
    # logger.info(f"검색 이력 추가 완료: user_id={user_id}, keyword={keyword}, history_id={new_history.kok_history_id}")
    return {
        "kok_history_id": new_history.kok_history_id,
        "user_id": user_id,
        "kok_keyword": keyword,
        "kok_searched_at": searched_at,
    }


async def delete_kok_search_history(
    db: AsyncSession,
    user_id: int,
    kok_history_id: int
) -> bool:
    """
    특정 검색 이력 ID로 검색 이력 삭제
    """
    # logger.info(f"검색 이력 삭제 시작: user_id={user_id}, history_id={kok_history_id}")
    
    stmt = (
        select(KokSearchHistory)
        .where(KokSearchHistory.user_id == user_id)
        .where(KokSearchHistory.kok_history_id == kok_history_id)
    )
    
    try:
        result = await db.execute(stmt)
        history = result.scalar_one_or_none()
    except Exception as e:
        logger.error(f"검색 이력 삭제 확인 SQL 실행 실패: user_id={user_id}, kok_history_id={kok_history_id}, error={str(e)}")
        return False
    
    if history:
        await db.delete(history)
    # logger.info(f"검색 이력 삭제 완료: user_id={user_id}, history_id={kok_history_id}")
        return True
    
    logger.warning(f"검색 이력을 찾을 수 없음: user_id={user_id}, history_id={kok_history_id}")
    return False


async def get_kok_notifications(
    db: AsyncSession,
    user_id: int,
    limit: int = 50
) -> List[dict]:
    """
    사용자의 알림 목록 조회
    """
    stmt = (
        select(KokNotification)
        .where(KokNotification.user_id == user_id)
        .order_by(KokNotification.notification_id.desc())
        .limit(limit)
    )
    
    try:
        results = (await db.execute(stmt)).scalars().all()
    except Exception as e:
        logger.error(f"알림 목록 조회 SQL 실행 실패: user_id={user_id}, limit={limit}, error={str(e)}")
        return []
    
    notifications = []
    for notification in results:
        notifications.append({
            "notification_id": notification.notification_id,
            "user_id": notification.user_id,
            "kok_order_id": notification.kok_order_id,
            "status_id": notification.status_id,
            "title": notification.title,
            "message": notification.message,
            "created_at": notification.created_at
        })
    
    return notifications


