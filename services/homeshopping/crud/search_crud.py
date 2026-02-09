from datetime import datetime
from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from services.homeshopping.models.core_model import HomeshoppingList, HomeshoppingProductInfo
from services.homeshopping.models.interaction_model import HomeshoppingSearchHistory
from .shared import logger

async def search_homeshopping_products(
    db: AsyncSession,
    keyword: str
) -> List[dict]:
    """
    홈쇼핑 상품 검색
    """
    # logger.info(f"홈쇼핑 상품 검색 시작: keyword='{keyword}'")
    
    # 상품명, 판매자명에서 키워드 검색
    stmt = (
        select(HomeshoppingList, HomeshoppingProductInfo)
        .join(HomeshoppingProductInfo, HomeshoppingList.product_id == HomeshoppingProductInfo.product_id)
        .where(
            HomeshoppingList.product_name.contains(keyword) |
            HomeshoppingProductInfo.store_name.contains(keyword)
        )
        .order_by(HomeshoppingList.live_date.asc(), HomeshoppingList.live_start_time.asc(), HomeshoppingList.live_id.asc())
    )
    
    try:
        results = await db.execute(stmt)
        products = results.all()
    except Exception as e:
        logger.error(f"홈쇼핑 상품 검색 SQL 실행 실패: keyword='{keyword}', error={str(e)}")
        raise
    
    product_list = []
    for live, product in products:
        product_list.append({
            "live_id": live.live_id,
            "product_id": live.product_id,
            "product_name": live.product_name,
            "store_name": product.store_name,
            "sale_price": product.sale_price,
            "dc_price": product.dc_price,
            "dc_rate": product.dc_rate,
            "thumb_img_url": live.thumb_img_url,
            "live_date": live.live_date,
            "live_start_time": live.live_start_time,
            "live_end_time": live.live_end_time
        })
    
    # logger.info(f"홈쇼핑 상품 검색 완료: keyword='{keyword}', 결과 수={len(product_list)}")
    return product_list


# -----------------------------
# 검색 이력 관련 CRUD 함수
# -----------------------------

async def add_homeshopping_search_history(
    db: AsyncSession,
    user_id: int,
    keyword: str
) -> dict:
    """
    홈쇼핑 검색 이력 추가
    """
    # logger.info(f"홈쇼핑 검색 이력 추가 시작: user_id={user_id}, keyword='{keyword}'")
    
    # user_id와 keyword 검증
    if user_id <= 0:
        logger.warning(f"유효하지 않은 user_id: {user_id}")
        raise ValueError("유효하지 않은 user_id입니다.")
    
    if not keyword or not keyword.strip():
        logger.warning("빈 검색 키워드")
        raise ValueError("검색 키워드를 입력해주세요.")
    
    searched_at = datetime.now()
    
    new_history = HomeshoppingSearchHistory(
        user_id=user_id,
        homeshopping_keyword=keyword.strip(),
        homeshopping_searched_at=searched_at
    )
    
    db.add(new_history)
    await db.flush()  # commit 전에 flush로 ID 생성
    await db.refresh(new_history)
    
    # logger.info(f"홈쇼핑 검색 이력 추가 완료: history_id={new_history.homeshopping_history_id}")
    return {
        "homeshopping_history_id": new_history.homeshopping_history_id,
        "user_id": new_history.user_id,
        "homeshopping_keyword": new_history.homeshopping_keyword,
        "homeshopping_searched_at": new_history.homeshopping_searched_at
    }


async def get_homeshopping_search_history(
    db: AsyncSession,
    user_id: int,
    limit: int = 5
) -> List[dict]:
    """
    홈쇼핑 검색 이력 조회
    """
    # logger.info(f"홈쇼핑 검색 이력 조회 시작: user_id={user_id}, limit={limit}")
    
    # user_id와 limit 검증
    if user_id <= 0:
        logger.warning(f"유효하지 않은 user_id: {user_id}")
        return []
    
    if limit <= 0 or limit > 100:
        logger.warning(f"유효하지 않은 limit: {limit}")
        limit = 5  # 기본값으로 설정
    
    stmt = (
        select(HomeshoppingSearchHistory)
        .where(HomeshoppingSearchHistory.user_id == user_id)
        .order_by(HomeshoppingSearchHistory.homeshopping_searched_at.desc())
        .limit(limit)
    )
    
    results = await db.execute(stmt)
    history = results.scalars().all()
    
    history_list = []
    for item in history:
        history_list.append({
            "homeshopping_history_id": item.homeshopping_history_id,
            "user_id": item.user_id,
            "homeshopping_keyword": item.homeshopping_keyword,
            "homeshopping_searched_at": item.homeshopping_searched_at
        })
    
    # logger.info(f"홈쇼핑 검색 이력 조회 완료: user_id={user_id}, 결과 수={len(history_list)}")
    return history_list


async def delete_homeshopping_search_history(
    db: AsyncSession,
    user_id: int,
    homeshopping_history_id: int
) -> bool:
    """
    홈쇼핑 검색 이력 삭제
    """
    # logger.info(f"홈쇼핑 검색 이력 삭제 시작: user_id={user_id}, history_id={homeshopping_history_id}")
    
    # user_id와 history_id 검증
    if user_id <= 0:
        logger.warning(f"유효하지 않은 user_id: {user_id}")
        return False
    
    if homeshopping_history_id <= 0:
        logger.warning(f"유효하지 않은 history_id: {homeshopping_history_id}")
        return False
    
    stmt = select(HomeshoppingSearchHistory).where(
        HomeshoppingSearchHistory.homeshopping_history_id == homeshopping_history_id,
        HomeshoppingSearchHistory.user_id == user_id
    )
    
    result = await db.execute(stmt)
    history = result.scalar_one_or_none()
    
    if not history:
        logger.warning(f"삭제할 검색 이력을 찾을 수 없음: user_id={user_id}, history_id={homeshopping_history_id}")
        return False
    
    await db.delete(history)
    
    # logger.info(f"홈쇼핑 검색 이력 삭제 완료: user_id={user_id}, history_id={homeshopping_history_id}")
    return True
