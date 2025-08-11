"""
홈쇼핑 관련 DB 접근(CRUD) 함수 (MariaDB)
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional, List, Tuple, Dict
from datetime import datetime
from common.logger import get_logger

from services.home_shopping.models.home_shopping_model import (
    HomeshoppingInfo,
    HomeshoppingList,
    HomeshoppingProductInfo,
    HomeshoppingDetailInfo,
    HomeshoppingImgUrl,
    HomeshoppingSearchHistory,
    HomeshoppingLikes,
    HomeshoppingNotification
)

logger = get_logger("home_shopping_crud")


# -----------------------------
# 편성표 관련 CRUD 함수
# -----------------------------

async def get_homeshopping_schedule(
    db: AsyncSession,
    page: int = 1,
    size: int = 20
) -> List[dict]:
    """
    홈쇼핑 편성표 조회
    """
    logger.info(f"홈쇼핑 편성표 조회 시작: page={page}, size={size}")
    
    offset = (page - 1) * size
    
    stmt = (
        select(HomeshoppingList, HomeshoppingInfo)
        .join(HomeshoppingInfo, HomeshoppingList.homeshopping_id == HomeshoppingInfo.homeshopping_id)
        .order_by(HomeshoppingList.live_date.desc(), HomeshoppingList.live_time.asc())
        .offset(offset)
        .limit(size)
    )
    
    results = await db.execute(stmt)
    schedules = results.all()
    
    schedule_list = []
    for live, info in schedules:
        schedule_list.append({
            "live_id": live.live_id,
            "homeshopping_channel_name": info.homeshopping_channel_name,
            "homeshopping_channel_number": info.homeshopping_channel_number,
            "live_date": live.live_date,
            "live_time": live.live_time,
            "promotion_type": live.promotion_type,
            "live_title": live.live_title,
            "product_id": live.product_id,
            "product_name": live.product_name,
            "dc_price": live.dc_price,
            "dc_rate": live.dc_rate,
            "thumb_img_url": live.thumb_img_url
        })
    
    logger.info(f"홈쇼핑 편성표 조회 완료: page={page}, size={size}, 결과 수={len(schedule_list)}")
    return schedule_list


# -----------------------------
# 상품 검색 관련 CRUD 함수
# -----------------------------

async def search_homeshopping_products(
    db: AsyncSession,
    keyword: str,
    page: int = 1,
    size: int = 20
) -> Tuple[List[dict], int]:
    """
    홈쇼핑 상품 검색
    """
    logger.info(f"홈쇼핑 상품 검색 시작: keyword='{keyword}', page={page}, size={size}")
    
    offset = (page - 1) * size
    
    # 상품명, 판매자명에서 키워드 검색
    stmt = (
        select(HomeshoppingList, HomeshoppingProductInfo)
        .join(HomeshoppingProductInfo, HomeshoppingList.product_id == HomeshoppingProductInfo.product_id)
        .where(
            HomeshoppingList.product_name.contains(keyword) |
            HomeshoppingProductInfo.store_name.contains(keyword)
        )
        .order_by(HomeshoppingList.live_date.desc())
        .offset(offset)
        .limit(size)
    )
    
    results = await db.execute(stmt)
    products = results.all()
    
    # 총 개수 조회
    count_stmt = (
        select(func.count(HomeshoppingList.live_id))
        .join(HomeshoppingProductInfo, HomeshoppingList.product_id == HomeshoppingProductInfo.product_id)
        .where(
            HomeshoppingList.product_name.contains(keyword) |
            HomeshoppingProductInfo.store_name.contains(keyword)
        )
    )
    total = await db.execute(count_stmt)
    total_count = total.scalar()
    
    product_list = []
    for live, product in products:
        product_list.append({
            "product_id": live.product_id,
            "product_name": live.product_name,
            "store_name": product.store_name,
            "sale_price": product.sale_price,
            "dc_price": live.dc_price,
            "dc_rate": live.dc_rate,
            "thumb_img_url": live.thumb_img_url,
            "live_date": live.live_date,
            "live_time": live.live_time
        })
    
    logger.info(f"홈쇼핑 상품 검색 완료: keyword='{keyword}', page={page}, size={size}, 결과 수={len(product_list)}")
    return product_list, total_count


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
    logger.info(f"홈쇼핑 검색 이력 추가 시작: user_id={user_id}, keyword='{keyword}'")
    
    searched_at = datetime.now()
    
    new_history = HomeshoppingSearchHistory(
        user_id=user_id,
        homeshopping_keyword=keyword,
        homeshopping_searched_at=searched_at
    )
    
    db.add(new_history)
    await db.commit()
    await db.refresh(new_history)
    
    logger.info(f"홈쇼핑 검색 이력 추가 완료: history_id={new_history.homeshopping_history_id}")
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
    logger.info(f"홈쇼핑 검색 이력 조회 시작: user_id={user_id}, limit={limit}")
    
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
    
    logger.info(f"홈쇼핑 검색 이력 조회 완료: user_id={user_id}, 결과 수={len(history_list)}")
    return history_list


async def delete_homeshopping_search_history(
    db: AsyncSession,
    user_id: int,
    homeshopping_history_id: int
) -> bool:
    """
    홈쇼핑 검색 이력 삭제
    """
    logger.info(f"홈쇼핑 검색 이력 삭제 시작: user_id={user_id}, history_id={homeshopping_history_id}")
    
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
    await db.commit()
    
    logger.info(f"홈쇼핑 검색 이력 삭제 완료: user_id={user_id}, history_id={homeshopping_history_id}")
    return True


# -----------------------------
# 상품 상세 관련 CRUD 함수
# -----------------------------

async def get_homeshopping_product_detail(
    db: AsyncSession,
    product_id: str,
    user_id: Optional[int] = None
) -> Optional[dict]:
    """
    홈쇼핑 상품 상세 정보 조회
    """
    logger.info(f"홈쇼핑 상품 상세 조회 시작: product_id={product_id}, user_id={user_id}")
    
    # 상품 기본 정보 조회
    stmt = (
        select(HomeshoppingList, HomeshoppingProductInfo)
        .join(HomeshoppingProductInfo, HomeshoppingList.product_id == HomeshoppingProductInfo.product_id)
        .where(HomeshoppingList.product_id == product_id)
    )
    
    result = await db.execute(stmt)
    product_data = result.first()
    
    if not product_data:
        logger.warning(f"상품을 찾을 수 없음: product_id={product_id}")
        return None
    
    live, product = product_data
    
    # 찜 상태 확인
    is_liked = False
    if user_id:
        like_stmt = select(HomeshoppingLikes).where(
            HomeshoppingLikes.user_id == user_id,
            HomeshoppingLikes.product_id == product_id
        )
        like_result = await db.execute(like_stmt)
        is_liked = like_result.scalar_one_or_none() is not None
    
    # 상세 정보 조회
    detail_stmt = (
        select(HomeshoppingDetailInfo)
        .where(HomeshoppingDetailInfo.product_id == product_id)
        .order_by(HomeshoppingDetailInfo.detail_id)
    )
    detail_result = await db.execute(detail_stmt)
    detail_infos = detail_result.scalars().all()
    
    # 이미지 조회
    img_stmt = (
        select(HomeshoppingImgUrl)
        .where(HomeshoppingImgUrl.product_id == product_id)
        .order_by(HomeshoppingImgUrl.sort_order)
    )
    img_result = await db.execute(img_stmt)
    images = img_result.scalars().all()
    
    # 응답 데이터 구성
    product_detail = {
        "product": {
            "product_id": live.product_id,
            "product_name": live.product_name,
            "store_name": product.store_name,
            "sale_price": product.sale_price,
            "dc_price": live.dc_price,
            "dc_rate": live.dc_rate,
            "return_exchange": product.return_exchange,
            "term": product.term,
            "live_date": live.live_date,
            "live_time": live.live_time,
            "thumb_img_url": live.thumb_img_url,
            "is_liked": is_liked
        },
        "detail_infos": [
            {
                "detail_col": detail.detail_col,
                "detail_val": detail.detail_val
            }
            for detail in detail_infos
        ],
        "images": [
            {
                "img_url": img.img_url,
                "sort_order": img.sort_order
            }
            for img in images
        ]
    }
    
    logger.info(f"홈쇼핑 상품 상세 조회 완료: product_id={product_id}, user_id={user_id}")
    return product_detail


# -----------------------------
# 상품 추천 관련 CRUD 함수
# -----------------------------

async def get_homeshopping_product_recommendations(
    db: AsyncSession,
    product_id: str
) -> List[dict]:
    """
    홈쇼핑 상품 추천 조회
    """
    logger.info(f"홈쇼핑 상품 추천 조회 시작: product_id={product_id}")
    
    # 상품 정보 조회
    stmt = select(HomeshoppingList).where(HomeshoppingList.product_id == product_id)
    result = await db.execute(stmt)
    product = result.scalar_one_or_none()
    
    if not product:
        logger.warning(f"상품을 찾을 수 없음: product_id={product_id}")
        return []
    
    # 상품명에서 식재료 여부 판단 (간단한 키워드 기반)
    product_name = product.product_name.lower()
    ingredient_keywords = [
        "고기", "채소", "과일", "생선", "해산물", "곡물", "견과류", "계란", "우유", "치즈",
        "고추", "마늘", "양파", "당근", "감자", "고구마", "쌀", "밀가루", "설탕", "소금"
    ]
    
    is_ingredient = any(keyword in product_name for keyword in ingredient_keywords)
    
    recommendations = []
    
    if is_ingredient:
        # 식재료인 경우 -> 어울리는 요리나 다른 식재료 추천
        # 실제로는 레시피 DB와 연동하여 추천 로직 구현
        recommendations.append({
            "product_id": "REC001",
            "product_name": "고기 요리용 양념 세트",
            "recommendation_type": "recipe",
            "reason": "이 재료와 어울리는 양념 세트"
        })
    else:
        # 완제품인 경우 -> 관련 식재료 추천
        recommendations.append({
            "product_id": "ING001",
            "product_name": "신선한 채소 세트",
            "recommendation_type": "ingredient",
            "reason": "이 상품과 함께 사용할 수 있는 신선한 재료"
        })
    
    logger.info(f"홈쇼핑 상품 추천 조회 완료: product_id={product_id}, 추천 수={len(recommendations)}")
    return recommendations


# -----------------------------
# 찜 관련 CRUD 함수
# -----------------------------

async def toggle_homeshopping_likes(
    db: AsyncSession,
    user_id: int,
    product_id: str
) -> bool:
    """
    홈쇼핑 찜 등록/해제 토글
    """
    logger.info(f"홈쇼핑 찜 토글 시작: user_id={user_id}, product_id={product_id}")
    
    # 기존 찜 확인
    stmt = select(HomeshoppingLikes).where(
        HomeshoppingLikes.user_id == user_id,
        HomeshoppingLikes.product_id == product_id
    )
    result = await db.execute(stmt)
    existing_like = result.scalar_one_or_none()
    
    if existing_like:
        # 찜 해제
        await db.delete(existing_like)
        await db.commit()
        logger.info(f"홈쇼핑 찜 해제 완료: user_id={user_id}, product_id={product_id}")
        return False
    else:
        # 찜 등록
        created_at = datetime.now()
        
        new_like = HomeshoppingLikes(
            user_id=user_id,
            product_id=product_id,
            homeshopping_created_at=created_at
        )
        
        db.add(new_like)
        await db.commit()
        logger.info(f"홈쇼핑 찜 등록 완료: user_id={user_id}, product_id={product_id}")
        return True


async def get_homeshopping_liked_products(
    db: AsyncSession,
    user_id: int,
    limit: int = 50
) -> List[dict]:
    """
    홈쇼핑 찜한 상품 목록 조회
    """
    logger.info(f"홈쇼핑 찜한 상품 조회 시작: user_id={user_id}, limit={limit}")
    
    stmt = (
        select(HomeshoppingLikes, HomeshoppingList, HomeshoppingProductInfo)
        .join(HomeshoppingList, HomeshoppingLikes.product_id == HomeshoppingList.product_id)
        .join(HomeshoppingProductInfo, HomeshoppingList.product_id == HomeshoppingProductInfo.product_id)
        .where(HomeshoppingLikes.user_id == user_id)
        .order_by(HomeshoppingLikes.homeshopping_created_at.desc())
        .limit(limit)
    )
    
    results = await db.execute(stmt)
    liked_products = results.all()
    
    product_list = []
    for like, live, product in liked_products:
        product_list.append({
            "product_id": live.product_id,
            "product_name": live.product_name,
            "store_name": product.store_name,
            "dc_price": live.dc_price,
            "dc_rate": live.dc_rate,
            "thumb_img_url": live.thumb_img_url,
            "homeshopping_created_at": like.homeshopping_created_at
        })
    
    logger.info(f"홈쇼핑 찜한 상품 조회 완료: user_id={user_id}, 결과 수={len(product_list)}")
    return product_list


# -----------------------------
# 주문 관련 CRUD 함수 (기본 구조)
# -----------------------------

async def create_homeshopping_order(
    db: AsyncSession,
    user_id: int,
    items: List[dict],
    delivery_address: str,
    delivery_phone: str
) -> dict:
    """
    홈쇼핑 주문 생성 (기본 구조)
    """
    logger.info(f"홈쇼핑 주문 생성 시작: user_id={user_id}, items_count={len(items)}")
    
    # 실제 구현에서는 주문 테이블에 저장
    # 현재는 기본 응답만 반환
    
    order_id = 1000 + user_id  # 임시 주문 ID 생성
    
    logger.info(f"홈쇼핑 주문 생성 완료: user_id={user_id}, order_id={order_id}")
    return {
        "order_id": order_id,
        "message": "주문이 성공적으로 생성되었습니다."
    }


# -----------------------------
# 스트리밍 관련 CRUD 함수 (기본 구조)
# -----------------------------

async def get_homeshopping_stream_info(
    db: AsyncSession,
    product_id: str
) -> Optional[dict]:
    """
    홈쇼핑 라이브 스트리밍 정보 조회 (기본 구조)
    """
    logger.info(f"홈쇼핑 스트리밍 정보 조회 시작: product_id={product_id}")
    
    # 상품 정보 조회
    stmt = select(HomeshoppingList).where(HomeshoppingList.product_id == product_id)
    result = await db.execute(stmt)
    product = result.scalar_one_or_none()
    
    if not product:
        logger.warning(f"상품을 찾을 수 없음: product_id={product_id}")
        return None
    
    # 현재 시간 기준으로 라이브 여부 판단
    now = datetime.now()
    live_date = product.live_date
    is_live = False
    
    if live_date:
        # 간단한 라이브 판단 로직 (실제로는 더 복잡한 로직 필요)
        time_diff = abs((now - live_date).total_seconds())
        is_live = time_diff < 3600  # 1시간 이내면 라이브로 간주
    
    stream_info = {
        "product_id": product_id,
        "stream_url": f"https://stream.example.com/live/{product_id}",  # 임시 URL
        "is_live": is_live,
        "live_start_time": product.live_date,
        "live_end_time": None  # 실제로는 라이브 종료 시간 필요
    }
    
    logger.info(f"홈쇼핑 스트리밍 정보 조회 완료: product_id={product_id}, is_live={is_live}")
    return stream_info
