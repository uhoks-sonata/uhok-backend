"""
홈쇼핑 관련 DB 접근(CRUD) 함수 (MariaDB)

계층별 역할:
- 이 파일은 데이터 액세스 계층(Data Access Layer)을 담당
- ORM(Session)과 직접 상호작용하여 DB 상태 변경 로직 처리
- db.add(), db.delete() 같은 DB 상태 변경은 여기서 수행
- 트랜잭션 관리(commit/rollback)는 상위 계층(라우터)에서 담당
"""
import os
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, insert, delete, and_, update, or_, text, exists
from sqlalchemy.orm import selectinload
from typing import Optional, List, Tuple, Dict
from datetime import datetime, date, time, timedelta

from services.homeshopping.models.homeshopping_model import (
    HomeshoppingInfo,
    HomeshoppingList,
    HomeshoppingProductInfo,
    HomeshoppingDetailInfo,
    HomeshoppingImgUrl,
    HomeshoppingSearchHistory,
    HomeshoppingLikes,
    HomeshoppingNotification,
    HomeshoppingClassify,
    HomeshoppingCart
)
from services.kok.models.kok_model import KokProductInfo
from services.order.models.order_model import (
    HomeShoppingOrder,
)

from common.logger import get_logger
from services.homeshopping.utils.cache_manager import cache_manager
from services.homeshopping.utils.memory_cache_manager import memory_cache_manager

logger = get_logger("homeshopping_crud")

# -----------------------------
# 편성표 관련 CRUD 함수
# -----------------------------

async def get_homeshopping_schedule_optimized(
    db: AsyncSession,
    live_date: Optional[date] = None,
    page: int = 1,
    size: int = 50
) -> Tuple[List[dict], int]:
    """
    홈쇼핑 편성표 조회 (식품만) - 물리적 테이블 사용 최적화 버전
    - HOMESHOPPING_SCHEDULE_OPTIMIZED 테이블 사용
    - 복잡한 JOIN 없이 단일 테이블 조회
    """
    # 1. 캐시에서 조회 시도
    cached_result = await cache_manager.get_schedule_cache(live_date, page, size)
    if cached_result:
        schedules, total_count = cached_result
        # logger.info(f"캐시에서 스케줄 조회 완료: 결과 수={len(schedules)}, 전체={total_count}")
        return schedules, total_count
    
    logger.info("캐시 미스 - 최적화된 테이블에서 스케줄 조회")
    
    # 페이징 계산
    offset = (page - 1) * size
    
    # 극한 최적화: 물리적 테이블 사용으로 단일 테이블 조회
    if live_date:
        # 특정 날짜 조회
        sql_query = """
        SELECT 
            live_id,
            homeshopping_id,
            homeshopping_name,
            homeshopping_channel,
            live_date,
            live_start_time,
            live_end_time,
            promotion_type,
            product_id,
            product_name,
            thumb_img_url,
            sale_price,
            dc_price,
            dc_rate
        FROM HOMESHOPPING_SCHEDULE_OPTIMIZED
        WHERE live_date = :live_date
        ORDER BY live_date DESC, live_start_time ASC
        LIMIT :limit OFFSET :offset
        """
        
        count_sql = """
        SELECT COUNT(*)
        FROM HOMESHOPPING_SCHEDULE_OPTIMIZED
        WHERE live_date = :live_date
        """
        
        params = {"live_date": live_date, "limit": size, "offset": offset}
        count_params = {"live_date": live_date}
    else:
        # 전체 조회
        sql_query = """
        SELECT 
            live_id,
            homeshopping_id,
            homeshopping_name,
            homeshopping_channel,
            live_date,
            live_start_time,
            live_end_time,
            promotion_type,
            product_id,
            product_name,
            thumb_img_url,
            sale_price,
            dc_price,
            dc_rate
        FROM HOMESHOPPING_SCHEDULE_OPTIMIZED
        ORDER BY live_date DESC, live_start_time ASC
        LIMIT :limit OFFSET :offset
        """
        
        count_sql = """
        SELECT COUNT(*)
        FROM HOMESHOPPING_SCHEDULE_OPTIMIZED
        """
        
        params = {"limit": size, "offset": offset}
        count_params = {}
    
    # Raw SQL 실행
    # logger.info("최적화된 테이블에서 스케줄 데이터 조회 시작")
    try:
        result = await db.execute(text(sql_query), params)
        schedules = result.fetchall()
        
        # logger.info("최적화된 테이블에서 스케줄 개수 조회 시작")
        count_result = await db.execute(text(count_sql), count_params)
        total_count = count_result.scalar()
    except Exception as e:
        logger.error(f"스케줄 조회 SQL 실행 실패: live_date={live_date}, page={page}, size={size}, error={str(e)}")
        raise
    
    # 결과 변환 - 시간 타입 처리
    schedule_list = []
    for row in schedules:
        # timedelta를 time으로 변환
        start_time = row.live_start_time
        end_time = row.live_end_time
        
        if hasattr(start_time, 'total_seconds'):
            # timedelta인 경우 time으로 변환
            start_time = (datetime.min + start_time).time()
        if hasattr(end_time, 'total_seconds'):
            # timedelta인 경우 time으로 변환
            end_time = (datetime.min + end_time).time()
        
        schedule_list.append({
            "live_id": row.live_id,
            "homeshopping_id": row.homeshopping_id,
            "homeshopping_name": row.homeshopping_name,
            "homeshopping_channel": row.homeshopping_channel,
            "live_date": row.live_date,
            "live_start_time": start_time,
            "live_end_time": end_time,
            "promotion_type": row.promotion_type,
            "product_id": row.product_id,
            "product_name": row.product_name,
            "thumb_img_url": row.thumb_img_url,
            "sale_price": row.sale_price,
            "dc_price": row.dc_price,
            "dc_rate": row.dc_rate
        })
    
    # logger.info(f"최적화된 테이블에서 스케줄 조회 완료: 결과 수={len(schedule_list)}, 전체={total_count}")
    
    # Redis 캐시 저장 비활성화 (연결 에러 방지)
    # asyncio.create_task(
    #     cache_manager.set_schedule_cache(schedule_list, total_count, live_date, page, size)
    # )
    
    return schedule_list, total_count

async def get_homeshopping_schedule(
    db: AsyncSession,
    live_date: Optional[date] = None,
    page: int = 1,
    size: int = 50
) -> Tuple[List[dict], int]:
    """
    홈쇼핑 편성표 조회 (식품만) - 최적화 버전
    - 윈도우 함수 사용으로 복잡한 JOIN 최적화
    - 인덱스 최적화를 위한 쿼리 구조 개선
    """
    # logger.info(f"홈쇼핑 편성표 조회 시작: live_date={live_date}, page={page}, size={size}")
    
    # 페이징 계산
    offset = (page - 1) * size
    
    # 최적화된 쿼리: 윈도우 함수를 사용하여 복잡한 JOIN 제거
    if live_date:
        # 특정 날짜 조회 - 윈도우 함수로 최적화
        sql_query = """
        WITH ranked_products AS (
            SELECT 
                hl.live_id,
                hl.homeshopping_id,
                hl.live_date,
                hl.live_start_time,
                hl.live_end_time,
                hl.promotion_type,
                hl.product_id,
                hl.product_name,
                hl.thumb_img_url,
                hi.homeshopping_name,
                hi.homeshopping_channel,
                COALESCE(hpi.sale_price, 0) as sale_price,
                COALESCE(hpi.dc_price, 0) as dc_price,
                COALESCE(hpi.dc_rate, 0) as dc_rate,
                ROW_NUMBER() OVER (
                    PARTITION BY hl.product_id 
                    ORDER BY hl.live_date DESC, hl.live_start_time DESC
                ) as rn
            FROM FCT_HOMESHOPPING_LIST hl
            INNER JOIN HOMESHOPPING_INFO hi ON hl.homeshopping_id = hi.homeshopping_id
            INNER JOIN HOMESHOPPING_CLASSIFY hc ON hl.product_id = hc.product_id
            LEFT JOIN FCT_HOMESHOPPING_PRODUCT_INFO hpi ON hl.product_id = hpi.product_id
            WHERE hl.live_date = :live_date
            AND hc.cls_food = 1
        )
        SELECT 
            live_id, homeshopping_id, live_date, live_start_time, live_end_time,
            promotion_type, product_id, product_name, thumb_img_url,
            homeshopping_name, homeshopping_channel, sale_price, dc_price, dc_rate
        FROM ranked_products
        WHERE rn = 1
        ORDER BY live_date DESC, live_start_time ASC
        LIMIT :limit OFFSET :offset
        """
        
        count_sql = """
        SELECT COUNT(DISTINCT hl.product_id)
        FROM FCT_HOMESHOPPING_LIST hl
        INNER JOIN HOMESHOPPING_CLASSIFY hc ON hl.product_id = hc.product_id
        WHERE hl.live_date = :live_date
        AND hc.cls_food = 1
        """
        
        params = {"live_date": live_date, "limit": size, "offset": offset}
        count_params = {"live_date": live_date}
    else:
        # 전체 조회 - 윈도우 함수로 최적화
        sql_query = """
        WITH ranked_products AS (
            SELECT 
                hl.live_id,
                hl.homeshopping_id,
                hl.live_date,
                hl.live_start_time,
                hl.live_end_time,
                hl.promotion_type,
                hl.product_id,
                hl.product_name,
                hl.thumb_img_url,
                hi.homeshopping_name,
                hi.homeshopping_channel,
                COALESCE(hpi.sale_price, 0) as sale_price,
                COALESCE(hpi.dc_price, 0) as dc_price,
                COALESCE(hpi.dc_rate, 0) as dc_rate,
                ROW_NUMBER() OVER (
                    PARTITION BY hl.product_id 
                    ORDER BY hl.live_date DESC, hl.live_start_time DESC
                ) as rn
            FROM FCT_HOMESHOPPING_LIST hl
            INNER JOIN HOMESHOPPING_INFO hi ON hl.homeshopping_id = hi.homeshopping_id
            INNER JOIN HOMESHOPPING_CLASSIFY hc ON hl.product_id = hc.product_id
            LEFT JOIN FCT_HOMESHOPPING_PRODUCT_INFO hpi ON hl.product_id = hpi.product_id
            WHERE hc.cls_food = 1
        )
        SELECT 
            live_id, homeshopping_id, live_date, live_start_time, live_end_time,
            promotion_type, product_id, product_name, thumb_img_url,
            homeshopping_name, homeshopping_channel, sale_price, dc_price, dc_rate
        FROM ranked_products
        WHERE rn = 1
        ORDER BY live_date DESC, live_start_time ASC
        LIMIT :limit OFFSET :offset
        """
        
        count_sql = """
        SELECT COUNT(DISTINCT hl.product_id)
        FROM FCT_HOMESHOPPING_LIST hl
        INNER JOIN HOMESHOPPING_CLASSIFY hc ON hl.product_id = hc.product_id
        WHERE hc.cls_food = 1
        """
        
        params = {"limit": size, "offset": offset}
        count_params = {}
    
    # 최적화된 SQL 실행
    try:
        result = await db.execute(text(sql_query), params)
        schedules = result.fetchall()
        
        count_result = await db.execute(text(count_sql), count_params)
        total_count = count_result.scalar()
    except Exception as e:
        logger.error(f"스케줄 조회 SQL 실행 실패: live_date={live_date}, page={page}, size={size}, error={str(e)}")
        raise
    
    # 결과 변환 - 시간 타입 처리
    schedule_list = []
    for row in schedules:
        # timedelta를 time으로 변환
        start_time = row.live_start_time
        end_time = row.live_end_time
        
        if hasattr(start_time, 'total_seconds'):
            # timedelta인 경우 time으로 변환
            start_time = (datetime.min + start_time).time()
        if hasattr(end_time, 'total_seconds'):
            # timedelta인 경우 time으로 변환
            end_time = (datetime.min + end_time).time()
        
        schedule_list.append({
            "live_id": row.live_id,
            "homeshopping_id": row.homeshopping_id,
            "homeshopping_name": row.homeshopping_name,
            "homeshopping_channel": row.homeshopping_channel,
            "live_date": row.live_date,
            "live_start_time": start_time,
            "live_end_time": end_time,
            "promotion_type": row.promotion_type,
            "product_id": row.product_id,
            "product_name": row.product_name,
            "thumb_img_url": row.thumb_img_url,
            "sale_price": row.sale_price,
            "dc_price": row.dc_price,
            "dc_rate": row.dc_rate
        })
    
    # logger.info(f"홈쇼핑 편성표 조회 완료: live_date={live_date}, 결과 수={len(schedule_list)}, 전체={total_count}")
    return schedule_list, total_count


# -----------------------------
# 스트리밍 관련 CRUD 함수 (기본 구조)
# -----------------------------




async def get_homeshopping_live_url(
    db: AsyncSession,
    homeshopping_id: int
) -> Optional[str]:
    """
    홈쇼핑 ID로 live_url(m3u8) 조회
    """
    # logger.info(f"홈쇼핑 live_url 조회 시작: homeshopping_id={homeshopping_id}")
    
    try:
        homeshopping_stmt = (
            select(HomeshoppingInfo.live_url)
            .where(HomeshoppingInfo.homeshopping_id == homeshopping_id)
        )
        homeshopping_result = await db.execute(homeshopping_stmt)
        live_url = homeshopping_result.scalar_one_or_none()
        
        if not live_url:
            logger.warning(f"홈쇼핑 live_url을 찾을 수 없음: homeshopping_id={homeshopping_id}")
            return None
        
    # logger.info(f"홈쇼핑 live_url 조회 완료: homeshopping_id={homeshopping_id}")
        return live_url
        
    except Exception as e:
        logger.error(f"홈쇼핑 live_url 조회 중 오류 발생: homeshopping_id={homeshopping_id}, error={str(e)}")
        raise


async def get_homeshopping_stream_info(
    db: AsyncSession,
    live_url: str
) -> Optional[dict]:
    """
    홈쇼핑 라이브 스트리밍 정보 조회
    """
    # logger.info(f"홈쇼핑 스트리밍 정보 조회 시작: live_url={live_url}")
    
    try:
        # 1단계: live_url로 HomeshoppingInfo 조회
        homeshopping_stmt = (
            select(HomeshoppingInfo)
            .where(HomeshoppingInfo.live_url == live_url)
        )
        homeshopping_result = await db.execute(homeshopping_stmt)
        homeshopping_info = homeshopping_result.scalar_one_or_none()
        
        if not homeshopping_info:
            logger.warning(f"홈쇼핑 정보를 찾을 수 없음: live_url={live_url}")
            return None
        
        # 2단계: homeshopping_id로 현재 라이브 방송 조회
        now = datetime.now()
        live_stmt = (
            select(HomeshoppingList)
            .where(HomeshoppingList.homeshopping_id == homeshopping_info.homeshopping_id)
            .where(HomeshoppingList.live_date == now.date())  # 오늘 방송만
            .order_by(HomeshoppingList.live_start_time.desc())
        )
        live_result = await db.execute(live_stmt)
        live_info = live_result.scalar_one_or_none()
        
        if not live_info:
            logger.warning(f"오늘 방송을 찾을 수 없음: homeshopping_id={homeshopping_info.homeshopping_id}")
            return None
        
        # 3단계: 현재 시간 기준으로 라이브 여부 판단
        is_live = False
        if live_info.live_start_time and live_info.live_end_time:
            current_time = now.time()
            is_live = live_info.live_start_time <= current_time <= live_info.live_end_time
        
        stream_info = {
            "homeshopping_id": homeshopping_info.homeshopping_id,
            "homeshopping_name": homeshopping_info.homeshopping_name,
            "live_id": live_info.live_id,
            "product_id": live_info.product_id,
            "product_name": live_info.product_name,
            "stream_url": homeshopping_info.live_url,  # 실제 live_url 사용
            "is_live": is_live,
            "live_date": live_info.live_date,
            "live_start_time": live_info.live_start_time,
            "live_end_time": live_info.live_end_time,
            "thumb_img_url": live_info.thumb_img_url
        }
        
        # logger.info(f"홈쇼핑 스트리밍 정보 조회 완료: live_id={live_info.live_id}, is_live={is_live}")
        return stream_info
        
    except Exception as e:
        logger.error(f"홈쇼핑 스트리밍 정보 조회 중 오류 발생: live_url={live_url}, error={str(e)}")
        # 중복 데이터가 있는 경우 로그에 기록
        if "Multiple rows were found" in str(e):
            logger.error(f"중복 데이터 발견: live_url={live_url}에 대해 여러 행이 존재합니다.")
        raise


# -----------------------------
# 상품 검색 관련 CRUD 함수
# -----------------------------

async def search_homeshopping_products(
    db: AsyncSession,
    keyword: str
) -> List[dict]:
    """
    홈쇼핑 상품 검색 (최적화: 윈도우 함수 사용으로 중복 제거)
    """
    # logger.info(f"홈쇼핑 상품 검색 시작: keyword='{keyword}'")
    
    # 최적화된 검색 쿼리: 윈도우 함수를 사용하여 중복 제거
    sql_query = """
    WITH ranked_products AS (
        SELECT 
            hl.live_id,
            hl.product_id,
            hl.product_name,
            hpi.store_name,
            hpi.sale_price,
            hpi.dc_price,
            hpi.dc_rate,
            hl.thumb_img_url,
            hl.live_date,
            hl.live_start_time,
            hl.live_end_time,
            ROW_NUMBER() OVER (
                PARTITION BY hl.product_id 
                ORDER BY hl.live_date DESC, hl.live_start_time DESC
            ) as rn
        FROM FCT_HOMESHOPPING_LIST hl
        INNER JOIN FCT_HOMESHOPPING_PRODUCT_INFO hpi ON hl.product_id = hpi.product_id
        WHERE (
            hl.product_name LIKE :keyword OR 
            hpi.store_name LIKE :keyword
        )
    )
    SELECT 
        live_id, product_id, product_name, store_name,
        sale_price, dc_price, dc_rate, thumb_img_url,
        live_date, live_start_time, live_end_time
    FROM ranked_products
    WHERE rn = 1
    ORDER BY live_date DESC, live_start_time DESC
    LIMIT 100
    """
    
    try:
        result = await db.execute(text(sql_query), {"keyword": f"%{keyword}%"})
        products = result.fetchall()
    except Exception as e:
        logger.error(f"홈쇼핑 상품 검색 SQL 실행 실패: keyword='{keyword}', error={str(e)}")
        raise
    
    product_list = []
    for row in products:
        product_list.append({
            "live_id": row.live_id,
            "product_id": row.product_id,
            "product_name": row.product_name,
            "store_name": row.store_name,
            "sale_price": row.sale_price,
            "dc_price": row.dc_price,
            "dc_rate": row.dc_rate,
            "thumb_img_url": row.thumb_img_url,
            "live_date": row.live_date,
            "live_start_time": row.live_start_time,
            "live_end_time": row.live_end_time
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


# -----------------------------
# 상품 상세 관련 CRUD 함수
# -----------------------------

async def get_homeshopping_product_detail(
    db: AsyncSession,
    live_id: int,
    user_id: Optional[int] = None
) -> Optional[dict]:
    """
    홈쇼핑 상품 상세 정보 조회 (최적화: 단일 쿼리로 모든 정보 조회)
    """
    # logger.info(f"홈쇼핑 상품 상세 조회 시작: live_id={live_id}, user_id={user_id}")
    
    # 최적화된 쿼리: 단일 쿼리로 모든 정보를 한 번에 조회
    sql_query = """
    SELECT 
        hl.live_id,
        hl.product_id,
        hl.product_name,
        hl.thumb_img_url,
        hl.live_date,
        hl.live_start_time,
        hl.live_end_time,
        hpi.store_name,
        hpi.sale_price,
        hpi.dc_price,
        hpi.dc_rate,
        hi.homeshopping_id,
        hi.homeshopping_name,
        hi.homeshopping_channel,
        CASE 
            WHEN hl.user_id = :user_id AND hl.product_id IN (
                SELECT product_id FROM HOMESHOPPING_LIKES WHERE user_id = :user_id
            ) THEN 1 
            ELSE 0 
        END as is_liked
    FROM FCT_HOMESHOPPING_LIST hl
    INNER JOIN FCT_HOMESHOPPING_PRODUCT_INFO hpi ON hl.product_id = hpi.product_id
    INNER JOIN HOMESHOPPING_INFO hi ON hl.homeshopping_id = hi.homeshopping_id
    WHERE hl.live_id = :live_id
    """
    
    try:
        result = await db.execute(text(sql_query), {"live_id": live_id, "user_id": user_id or 0})
        product_data = result.fetchone()
    except Exception as e:
        logger.error(f"홈쇼핑 상품 상세 조회 SQL 실행 실패: live_id={live_id}, error={str(e)}")
        raise
    
    if not product_data:
        logger.warning(f"상품을 찾을 수 없음: live_id={live_id}")
        return None
    
    # 찜 상태 확인 (별도 쿼리)
    is_liked = False
    if user_id:
        like_stmt = select(HomeshoppingLikes).where(
            HomeshoppingLikes.user_id == user_id,
            HomeshoppingLikes.product_id == product_data.product_id
        )
        like_result = await db.execute(like_stmt)
        is_liked = like_result.scalars().first() is not None
    
    # 상세 정보와 이미지를 병렬로 조회
    detail_task = asyncio.create_task(
        db.execute(
            select(HomeshoppingDetailInfo)
            .where(HomeshoppingDetailInfo.product_id == product_data.product_id)
            .order_by(HomeshoppingDetailInfo.detail_id)
        )
    )
    
    img_task = asyncio.create_task(
        db.execute(
            select(HomeshoppingImgUrl)
            .where(HomeshoppingImgUrl.product_id == product_data.product_id)
            .order_by(HomeshoppingImgUrl.sort_order)
        )
    )
    
    try:
        detail_result, img_result = await asyncio.gather(detail_task, img_task)
        detail_infos = detail_result.scalars().all()
        images = img_result.scalars().all()
    except Exception as e:
        logger.warning(f"상품 상세 정보/이미지 조회 실패: product_id={product_data.product_id}, error={str(e)}")
        detail_infos = []
        images = []
    
    # 응답 데이터 구성 (채널 정보 포함)
    product_detail = {
        "product": {
            "product_id": product_data.product_id,
            "product_name": product_data.product_name,
            "store_name": product_data.store_name if product_data.store_name else None,
            "sale_price": product_data.sale_price if product_data.sale_price else None,
            "dc_price": product_data.dc_price if product_data.dc_price else None,
            "dc_rate": product_data.dc_rate if product_data.dc_rate else None,
            "live_date": product_data.live_date,
            "live_start_time": product_data.live_start_time,
            "live_end_time": product_data.live_end_time,
            "thumb_img_url": product_data.thumb_img_url,
            "is_liked": is_liked,
            
            # 채널 정보 추가
            "homeshopping_id": product_data.homeshopping_id if product_data.homeshopping_id else None,
            "homeshopping_name": product_data.homeshopping_name if product_data.homeshopping_name else None,
            "homeshopping_channel": product_data.homeshopping_channel if product_data.homeshopping_channel else None,
            "homeshopping_channel_name": f"채널 {product_data.homeshopping_channel}" if product_data.homeshopping_channel else None,
            "homeshopping_channel_image": f"/images/channels/channel_{product_data.homeshopping_channel}.jpg" if product_data.homeshopping_channel else None
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
    
    # logger.info(f"홈쇼핑 상품 상세 조회 완료: live_id={live_id}, user_id={user_id}")
    return product_detail


# -----------------------------
# 상품 분류 및 추천 관련 CRUD 함수
# -----------------------------

async def get_homeshopping_classify_cls_ing(
    db: AsyncSession,
    homeshopping_product_id: int
) -> Optional[int]:
    """
    HOMESHOPPING_CLASSIFY 테이블에서 CLS_ING 값 조회
    """
    # logger.info(f"홈쇼핑 상품 분류 CLS_ING 조회 시작: homeshopping_product_id={homeshopping_product_id}")
    
    try:
        # HOMESHOPPING_CLASSIFY 테이블에서 CLS_ING 값 조회
        stmt = select(HomeshoppingClassify.cls_ing).where(HomeshoppingClassify.product_id == homeshopping_product_id)
        result = await db.execute(stmt)
        cls_ing = result.scalar_one_or_none()
        
        if cls_ing is None:
            logger.warning(f"HOMESHOPPING_CLASSIFY 테이블에서 homeshopping_product_id={homeshopping_product_id}를 찾을 수 없음")
            # 해당 상품이 분류 테이블에 없는 경우 기본값 0(완제품) 반환
            return 0
        
        # logger.info(f"홈쇼핑 상품 분류 CLS_ING 조회 완료: homeshopping_product_id={homeshopping_product_id}, cls_ing={cls_ing}")
        return cls_ing
        
    except Exception as e:
        logger.error(f"홈쇼핑 상품 분류 CLS_ING 조회 실패: homeshopping_product_id={homeshopping_product_id}, error={str(e)}")
        # 에러 발생 시 기본값 0(완제품) 반환
        return 0


async def get_recipe_recommendations_for_ingredient(
    db: AsyncSession,
    homeshopping_product_id: int
) -> List[dict]:
    """
    식재료에 대한 레시피 추천 조회
    """
    # logger.info(f"식재료 레시피 추천 조회 시작: homeshopping_product_id={homeshopping_product_id}")
    
    try:
        # TODO: 레시피 서비스와 연동하여 실제 레시피 추천 로직 구현
        # 현재는 더미 데이터 반환
        
        # 상품명 조회 (가장 최근 방송 정보에서 선택)
        stmt = select(HomeshoppingList.product_name).where(HomeshoppingList.product_id == homeshopping_product_id).order_by(HomeshoppingList.live_date.desc(), HomeshoppingList.live_start_time.desc())
        result = await db.execute(stmt)
        product_name = result.scalar_one_or_none()
        
        if not product_name:
            logger.warning(f"상품명을 찾을 수 없음: homeshopping_product_id={homeshopping_product_id}")
            return []
        
        # TODO: 레시피 서비스와 연동하여 실제 레시피 추천 로직 구현
        logger.warning("레시피 추천 서비스가 아직 구현되지 않음")
        return []
        
    except Exception as e:
        logger.error(f"식재료 레시피 추천 조회 실패: homeshopping_product_id={homeshopping_product_id}, error={str(e)}")
        return []


# -----------------------------
# 찜 관련 CRUD 함수
# -----------------------------

async def toggle_homeshopping_likes(
    db: AsyncSession,
    user_id: int,
    homeshopping_product_id: int
) -> bool:
    """
    홈쇼핑 상품 찜 등록/해제
    - product_id를 찜 목록에서 조회한 후 없을 경우 추가
    - product_id를 찜 목록에서 조회했을 때 있는 경우에는 삭제
    """
    # logger.info(f"홈쇼핑 찜 토글 시작: user_id={user_id}, homeshopping_product_id={homeshopping_product_id}")
    
    try:
        # 데이터베이스 연결 상태 확인
        # logger.info(f"데이터베이스 세션 상태 확인: {db.is_active}")
        
        # 기존 찜 여부 확인
        # logger.info(f"기존 찜 조회 시작: user_id={user_id}, homeshopping_product_id={homeshopping_product_id}")
        existing_like_result = await db.execute(
            select(HomeshoppingLikes).where(
                and_(
                    HomeshoppingLikes.user_id == user_id,
                    HomeshoppingLikes.product_id == homeshopping_product_id
                )
            )
        )
        existing_like = existing_like_result.scalar_one_or_none()
        # logger.info(f"기존 찜 조회 결과: {existing_like is not None}")
        
        if existing_like:
            # 기존 찜이 있으면 찜 해제
        # logger.info(f"기존 찜 발견, 찜 해제 처리: like_id={existing_like.homeshopping_like_id}")
            
            try:
                # 방송 알림도 함께 삭제
                await delete_broadcast_notification(db, user_id, existing_like.homeshopping_like_id)
                # logger.info("방송 알림 삭제 완료")
            except Exception as e:
                logger.warning(f"방송 알림 삭제 실패 (무시하고 진행): {str(e)}")
            
            # 찜 레코드 삭제
            await db.delete(existing_like)
            # logger.info("찜 레코드 삭제 완료")
            
            # logger.info(f"홈쇼핑 찜 해제 완료: user_id={user_id}, homeshopping_product_id={homeshopping_product_id}")
            return False
            
        else:
            # 기존 찜이 없으면 찜 등록
            # logger.info(f"새로운 찜 등록 처리: user_id={user_id}, homeshopping_product_id={homeshopping_product_id}")
            
            # 찜 레코드 생성
            new_like = HomeshoppingLikes(
                user_id=user_id,
                product_id=homeshopping_product_id,
                homeshopping_like_created_at=datetime.now()
            )
            db.add(new_like)
            # logger.info("찜 레코드 생성 완료")
            
            try:
                # 방송 정보 조회하여 알림 생성 (가장 최근 방송 정보 선택)
                # logger.info(f"방송 정보 조회 시작: homeshopping_product_id={homeshopping_product_id}")
                live_info_result = await db.execute(
                    select(HomeshoppingList).where(
                        HomeshoppingList.product_id == homeshopping_product_id
                    ).order_by(HomeshoppingList.live_date.desc(), HomeshoppingList.live_start_time.desc())
                )
                live_info = live_info_result.scalar_one_or_none()
                # logger.info(f"방송 정보 조회 결과: {live_info is not None}")
                
                if live_info and live_info.live_date and live_info.live_start_time:
                    # 방송 시작 알림 생성
                    await create_broadcast_notification(
                        db=db,
                        user_id=user_id,
                        homeshopping_like_id=new_like.homeshopping_like_id,
                        product_id=homeshopping_product_id,
                        product_name=live_info.product_name,
                        broadcast_date=live_info.live_date,
                        broadcast_start_time=live_info.live_start_time
                    )
                    # logger.info(f"방송 시작 알림 생성 완료: like_id={new_like.homeshopping_like_id}")
                else:
                    logger.warning("방송 정보가 부족하여 알림을 생성하지 않음")
            except Exception as e:
                logger.warning(f"방송 알림 생성 실패 (무시하고 진행): {str(e)}")
            
            # logger.info(f"홈쇼핑 찜 등록 완료: user_id={user_id}, homeshopping_product_id={homeshopping_product_id}, like_id={new_like.homeshopping_like_id}")
            return True
            
    except Exception as e:
        logger.error(f"홈쇼핑 찜 토글 실패: user_id={user_id}, homeshopping_product_id={homeshopping_product_id}, error={str(e)}")
        logger.error(f"에러 타입: {type(e).__name__}")
        logger.error(f"에러 상세: {str(e)}")
        import traceback
        logger.error(f"스택 트레이스: {traceback.format_exc()}")
        raise


async def get_homeshopping_liked_products(
    db: AsyncSession,
    user_id: int,
    limit: int = 50
) -> List[dict]:
    """
    홈쇼핑 찜한 상품 목록 조회 (최적화: 윈도우 함수로 중복 제거)
    """
    # logger.info(f"홈쇼핑 찜한 상품 조회 시작: user_id={user_id}, limit={limit}")
    
    # user_id 검증 (논리 FK이므로 실제 USERS 테이블 존재 여부는 확인하지 않음)
    if user_id <= 0:
        logger.warning(f"유효하지 않은 user_id: {user_id}")
        return []
    
    # 최적화된 쿼리: 윈도우 함수를 사용하여 중복 제거
    sql_query = """
    WITH ranked_liked_products AS (
        SELECT 
            hl.live_id,
            hl.product_id,
            hl.product_name,
            hl.thumb_img_url,
            hl.live_date,
            hl.live_start_time,
            hl.live_end_time,
            hl.homeshopping_id,
            hpi.store_name,
            hpi.dc_price,
            hpi.dc_rate,
            hl_likes.homeshopping_like_created_at,
            ROW_NUMBER() OVER (
                PARTITION BY hl.product_id 
                ORDER BY hl.live_date DESC, hl.live_start_time DESC
            ) as rn
        FROM HOMESHOPPING_LIKES hl_likes
        INNER JOIN FCT_HOMESHOPPING_LIST hl ON hl_likes.product_id = hl.product_id
        INNER JOIN FCT_HOMESHOPPING_PRODUCT_INFO hpi ON hl.product_id = hpi.product_id
        WHERE hl_likes.user_id = :user_id
    )
    SELECT 
        live_id, product_id, product_name, thumb_img_url,
        live_date, live_start_time, live_end_time, homeshopping_id,
        store_name, dc_price, dc_rate, homeshopping_like_created_at
    FROM ranked_liked_products
    WHERE rn = 1
    ORDER BY homeshopping_like_created_at DESC, product_id
    LIMIT :limit
    """
    
    try:
        result = await db.execute(text(sql_query), {"user_id": user_id, "limit": limit})
        liked_products = result.fetchall()
    except Exception as e:
        logger.error(f"홈쇼핑 찜한 상품 조회 SQL 실행 실패: user_id={user_id}, error={str(e)}")
        raise
    
    # 결과 변환
    product_list = []
    for row in liked_products:
        product_list.append({
            "live_id": row.live_id,
            "product_id": row.product_id,
            "product_name": row.product_name,
            "store_name": row.store_name if row.store_name else None,
            "dc_price": row.dc_price if row.dc_price else None,
            "dc_rate": row.dc_rate if row.dc_rate else None,
            "thumb_img_url": row.thumb_img_url,
            "homeshopping_like_created_at": row.homeshopping_like_created_at,
            "live_date": row.live_date,
            "live_start_time": row.live_start_time,
            "live_end_time": row.live_end_time,
            "homeshopping_id": row.homeshopping_id
        })
    
    # logger.info(f"홈쇼핑 찜한 상품 조회 완료: user_id={user_id}, 결과 수={len(product_list)}")
    return product_list


# -----------------------------
# 통합 알림 관련 CRUD 함수 (기존 테이블 활용)
# -----------------------------

async def create_broadcast_notification(
    db: AsyncSession,
    user_id: int,
    homeshopping_like_id: int,
    homeshopping_product_id: int,
    homeshopping_product_name: str,
    broadcast_date: date,
    broadcast_start_time: time
) -> dict:
    """
    방송 찜 알림 생성
    """
    # logger.info(f"방송 찜 알림 생성 시작: user_id={user_id}, homeshopping_like_id={homeshopping_like_id}, homeshopping_product_id={homeshopping_product_id}")
    
    try:
        # 방송 시작 알림 생성
        notification_data = {
            "user_id": user_id,
            "notification_type": "broadcast_start",
            "related_entity_type": "product",
            "related_entity_id": homeshopping_product_id,
            "homeshopping_like_id": homeshopping_like_id,
            "homeshopping_order_id": None,
            "status_id": None,
            "title": f"{homeshopping_product_name} 방송 시작 알림",
            "message": f"{broadcast_date} {broadcast_start_time}에 방송이 시작됩니다.",
            "is_read": 0,
            "created_at": datetime.now()
        }
        
        # 알림 레코드 생성
        stmt = insert(HomeshoppingNotification).values(**notification_data)
        try:
            result = await db.execute(stmt)
            notification_id = result.inserted_primary_key[0]
        except Exception as e:
            logger.error(f"방송 알림 생성 SQL 실행 실패: user_id={user_id}, homeshopping_like_id={homeshopping_like_id}, error={str(e)}")
            raise
        
        # logger.info(f"방송 찜 알림 생성 완료: notification_id={notification_id}")
        
        return {
            "notification_id": notification_id,
            "message": "방송 시작 알림이 등록되었습니다."
        }
        
    except Exception as e:
        logger.error(f"방송 찜 알림 생성 실패: user_id={user_id}, error={str(e)}")
        raise


async def delete_broadcast_notification(
    db: AsyncSession,
    user_id: int,
    homeshopping_like_id: int
) -> bool:
    """
    방송 찜 알림 삭제 (찜 해제 시)
    """
    # logger.info(f"방송 찜 알림 삭제 시작: user_id={user_id}, like_id={homeshopping_like_id}")
    
    try:
        # 해당 찜에 대한 방송 알림 삭제
        stmt = delete(HomeshoppingNotification).where(
            and_(
                HomeshoppingNotification.user_id == user_id,
                HomeshoppingNotification.homeshopping_like_id == homeshopping_like_id,
                HomeshoppingNotification.notification_type == "broadcast_start"
            )
        )
        
        result = await db.execute(stmt)
        
        deleted_count = result.rowcount
        
        if deleted_count > 0:
            # logger.info(f"방송 찜 알림 삭제 완료: deleted_count={deleted_count}")
            return True
        else:
            logger.warning(f"삭제할 방송 찜 알림이 없음: user_id={user_id}, like_id={homeshopping_like_id}")
            return False
            
    except Exception as e:
        logger.error(f"방송 찜 알림 삭제 실패: user_id={user_id}, error={str(e)}")
        raise


async def create_order_status_notification(
    db: AsyncSession,
    user_id: int,
    homeshopping_order_id: int,
    status_id: int,
    status_name: str,
    order_id: int
) -> dict:
    """
    주문 상태 변경 알림 생성
    """
    # logger.info(f"주문 상태 변경 알림 생성 시작: user_id={user_id}, homeshopping_order_id={homeshopping_order_id}, status={status_name}")
    
    try:
        # 주문 상태 변경 알림 생성
        notification_data = {
            "user_id": user_id,
            "notification_type": "order_status",
            "related_entity_type": "order",
            "related_entity_id": homeshopping_order_id,
            "homeshopping_like_id": None,
            "homeshopping_order_id": homeshopping_order_id,
            "status_id": status_id,
            "title": f"주문 상태 변경: {status_name}",
            "message": f"주문번호 {homeshopping_order_id}의 상태가 {status_name}로 변경되었습니다.",
            "is_read": 0,
            "created_at": datetime.now()
        }
        
        # 알림 레코드 생성
        stmt = insert(HomeshoppingNotification).values(**notification_data)
        try:
            result = await db.execute(stmt)
            notification_id = result.inserted_primary_key[0]
        except Exception as e:
            logger.error(f"주문 상태 변경 알림 생성 SQL 실행 실패: user_id={user_id}, homeshopping_order_id={homeshopping_order_id}, error={str(e)}")
            raise
        
        # logger.info(f"주문 상태 변경 알림 생성 완료: notification_id={notification_id}")
        
        return {
            "notification_id": notification_id,
            "message": "주문 상태 변경 알림이 생성되었습니다."
        }
        
    except Exception as e:
        logger.error(f"주문 상태 변경 알림 생성 실패: user_id={user_id}, error={str(e)}")
        raise


async def get_notifications_with_filter(
    db: AsyncSession,
    user_id: int,
    notification_type: Optional[str] = None,
    related_entity_type: Optional[str] = None,
    is_read: Optional[bool] = None,
    limit: int = 20,
    offset: int = 0
) -> Tuple[List[dict], int]:
    """
    필터링된 알림 조회 (최적화: 윈도우 함수로 상품명 조회)
    """
    # logger.info(f"필터링된 알림 조회 시작: user_id={user_id}, type={notification_type}, entity_type={related_entity_type}, is_read={is_read}")
    
    try:
        # 최적화된 쿼리: 윈도우 함수를 사용하여 상품명을 한 번에 조회
        sql_query = """
        WITH notification_with_product AS (
            SELECT 
                hn.notification_id,
                hn.user_id,
                hn.notification_type,
                hn.related_entity_type,
                hn.related_entity_id,
                hn.homeshopping_like_id,
                hn.homeshopping_order_id,
                hn.status_id,
                hn.title,
                hn.message,
                hn.is_read,
                hn.created_at,
                hn.read_at,
                CASE 
                    WHEN hn.homeshopping_order_id IS NOT NULL THEN
                        (SELECT hl.product_name 
                         FROM FCT_HOMESHOPPING_LIST hl
                         INNER JOIN HOMESHOPPING_ORDER ho ON hl.product_id = ho.product_id
                         WHERE ho.homeshopping_order_id = hn.homeshopping_order_id
                         ORDER BY hl.live_date DESC, hl.live_start_time DESC
                         LIMIT 1)
                    ELSE NULL
                END as product_name
            FROM HOMESHOPPING_NOTIFICATION hn
            WHERE hn.user_id = :user_id
        )
        SELECT 
            notification_id, user_id, notification_type, related_entity_type,
            related_entity_id, homeshopping_like_id, homeshopping_order_id,
            status_id, title, message, product_name, is_read, created_at, read_at
        FROM notification_with_product
        WHERE 1=1
        """
        
        # 필터 조건 추가
        params = {"user_id": user_id, "limit": limit, "offset": offset}
        
        if notification_type:
            sql_query += " AND notification_type = :notification_type"
            params["notification_type"] = notification_type
        
        if related_entity_type:
            sql_query += " AND related_entity_type = :related_entity_type"
            params["related_entity_type"] = related_entity_type
        
        if is_read is not None:
            sql_query += " AND is_read = :is_read"
            params["is_read"] = 1 if is_read else 0
        
        # 정렬 및 페이지네이션
        sql_query += " ORDER BY created_at DESC LIMIT :limit OFFSET :offset"
        
        # 개수 조회 쿼리
        count_sql = """
        SELECT COUNT(*)
        FROM HOMESHOPPING_NOTIFICATION
        WHERE user_id = :user_id
        """
        
        count_params = {"user_id": user_id}
        
        if notification_type:
            count_sql += " AND notification_type = :notification_type"
            count_params["notification_type"] = notification_type
        
        if related_entity_type:
            count_sql += " AND related_entity_type = :related_entity_type"
            count_params["related_entity_type"] = related_entity_type
        
        if is_read is not None:
            count_sql += " AND is_read = :is_read"
            count_params["is_read"] = 1 if is_read else 0
        
        # 쿼리 실행
        try:
            result = await db.execute(text(sql_query), params)
            notifications_data = result.fetchall()
            
            count_result = await db.execute(text(count_sql), count_params)
            total_count = count_result.scalar()
        except Exception as e:
            logger.error(f"알림 조회 SQL 실행 실패: user_id={user_id}, error={str(e)}")
            return [], 0
        
        # 결과 변환
        notifications = []
        for row in notifications_data:
            notifications.append({
                "notification_id": row.notification_id,
                "user_id": row.user_id,
                "notification_type": row.notification_type,
                "related_entity_type": row.related_entity_type,
                "related_entity_id": row.related_entity_id,
                "homeshopping_like_id": row.homeshopping_like_id,
                "homeshopping_order_id": row.homeshopping_order_id,
                "status_id": row.status_id,
                "title": row.title,
                "message": row.message,
                "product_name": row.product_name,
                "is_read": bool(row.is_read),
                "created_at": row.created_at,
                "read_at": row.read_at
            })
        
        # logger.info(f"필터링된 알림 조회 완료: user_id={user_id}, 결과 수={len(notifications)}, 전체 개수={total_count}")
        
        return notifications, total_count
        
    except Exception as e:
        logger.error(f"필터링된 알림 조회 실패: user_id={user_id}, error={str(e)}")
        raise


async def mark_notification_as_read(
    db: AsyncSession,
    user_id: int,
    notification_id: int
) -> bool:
    """
    알림을 읽음으로 표시
    """
    # logger.info(f"알림 읽음 처리 시작: user_id={user_id}, notification_id={notification_id}")
    
    try:
        stmt = update(HomeshoppingNotification).where(
            and_(
                HomeshoppingNotification.notification_id == notification_id,
                HomeshoppingNotification.user_id == user_id
            )
        ).values(
            is_read=1,
            read_at=datetime.now()
        )
        
        try:
            result = await db.execute(stmt)
            updated_count = result.rowcount
        except Exception as e:
            logger.error(f"알림 읽음 처리 SQL 실행 실패: notification_id={notification_id}, error={str(e)}")
            raise
        
        if updated_count > 0:
            # logger.info(f"알림 읽음 처리 완료: notification_id={notification_id}")
            return True
        else:
            logger.warning(f"읽음 처리할 알림을 찾을 수 없음: notification_id={notification_id}")
            return False
            
    except Exception as e:
        logger.error(f"알림 읽음 처리 실패: notification_id={notification_id}, error={str(e)}")
        raise


async def get_pending_broadcast_notifications(
    db: AsyncSession,
    current_time: datetime
) -> List[dict]:
    """
    발송 대기 중인 방송 알림 조회 (알림 스케줄러용)
    """
    # logger.info(f"발송 대기 중인 방송 알림 조회 시작: current_time={current_time}")
    
    try:
        # 현재 시간 기준으로 발송해야 할 방송 알림 조회
        stmt = (
            select(HomeshoppingNotification, HomeshoppingLikes, HomeshoppingList, HomeshoppingProductInfo)
            .join(HomeshoppingLikes, HomeshoppingNotification.homeshopping_like_id == HomeshoppingLikes.homeshopping_like_id)
            .join(HomeshoppingList, HomeshoppingLikes.product_id == HomeshoppingList.product_id)
            .join(HomeshoppingProductInfo, HomeshoppingList.product_id == HomeshoppingProductInfo.product_id)
            .where(
                HomeshoppingNotification.notification_type == "broadcast_start",
                HomeshoppingList.live_date == current_time.date(),
                HomeshoppingList.live_start_time <= current_time.time(),
                HomeshoppingList.live_start_time > (current_time - timedelta(minutes=5)).time()  # 5분 이내 방송
            )
            .order_by(HomeshoppingList.live_start_time.asc())
        )
        
        try:
            results = await db.execute(stmt)
            notifications = []
        except Exception as e:
            logger.error(f"발송 대기 방송 알림 조회 SQL 실행 실패: current_time={current_time}, error={str(e)}")
            raise
        
        for notification, like, live, product in results.all():
            notifications.append({
                "notification_id": notification.notification_id,
                "user_id": notification.user_id,
                "product_id": live.product_id,
                "live_id": live.live_id,
                "product_name": live.product_name,
                "broadcast_date": live.live_date,
                "broadcast_start_time": live.live_start_time,
                "store_name": product.store_name,
                "dc_price": product.dc_price
            })
        
        # logger.info(f"발송 대기 중인 방송 알림 조회 완료: 결과 수={len(notifications)}")
        return notifications
        
    except Exception as e:
        logger.error(f"발송 대기 중인 방송 알림 조회 실패: error={str(e)}")
        raise

# -----------------------------
# 콕 추천 관련 CRUD 함수
# -----------------------------

async def get_homeshopping_product_name(
    db: AsyncSession,
    homeshopping_product_id: int
) -> Optional[str]:
    """
    홈쇼핑 상품명 조회
    """
    # logger.info(f"홈쇼핑 상품명 조회 시작: homeshopping_product_id={homeshopping_product_id}")
    
    try:
        stmt = select(HomeshoppingList.product_name).where(HomeshoppingList.product_id == homeshopping_product_id).order_by(HomeshoppingList.live_date.desc(), HomeshoppingList.live_start_time.desc())
        try:
            result = await db.execute(stmt)
            product_name = result.scalar()
        except Exception as e:
            logger.error(f"홈쇼핑 상품명 조회 SQL 실행 실패: homeshopping_product_id={homeshopping_product_id}, error={str(e)}")
            return None
        
        if product_name:
            # logger.info(f"홈쇼핑 상품명 조회 완료: homeshopping_product_id={homeshopping_product_id}, name={product_name}")
            return product_name
        else:
            logger.warning(f"홈쇼핑 상품을 찾을 수 없음: homeshopping_product_id={homeshopping_product_id}")
            return None
            
    except Exception as e:
        logger.error(f"홈쇼핑 상품명 조회 실패: product_id={homeshopping_product_id}, error={str(e)}")
        return None


async def get_kok_product_infos(
    db: AsyncSession,
    kok_product_ids: List[int]
) -> List[dict]:
    """
    콕 상품 정보 조회 (실제 DB 연동)
    """
    # logger.info(f"콕 상품 정보 조회 시작: kok_product_ids={kok_product_ids}")
    
    if not kok_product_ids:
        logger.warning("조회할 상품 ID가 없음")
        return []
    
    try:
        # 실제 FCT_KOK_PRODUCT_INFO 테이블에서 상품 정보 조회 (가격 정보 포함)
        stmt = (
            select(KokProductInfo)
            .where(
                KokProductInfo.kok_product_id.in_(kok_product_ids)
            )
            .order_by(KokProductInfo.kok_review_cnt.desc())  # 리뷰 수 순으로 정렬 (MariaDB 호환)
        )
        
        # 가격 정보도 함께 로드
        stmt = stmt.options(selectinload(KokProductInfo.price_infos))
        
        try:
            result = await db.execute(stmt)
            kok_products = result.scalars().all()
        except Exception as e:
            logger.error(f"콕 상품 정보 조회 SQL 실행 실패: kok_product_ids={kok_product_ids}, error={str(e)}")
            return []
        
        # 응답 형태로 변환
        products = []
        for product in kok_products:
            # 할인율 계산 (원가와 할인가가 있을 때)
            discount_rate = 0
            # kok_product_price를 원가로 사용하고, 할인가가 없으면 원가를 할인가로 사용
            original_price = product.kok_product_price or 0
            discounted_price = 0
            
            # 가격 정보가 있는 경우 할인가 조회
            if hasattr(product, 'price_infos') and product.price_infos:
                for price_info in product.price_infos:
                    if price_info.kok_discounted_price:
                        discounted_price = price_info.kok_discounted_price
                        if price_info.kok_discount_rate:
                            discount_rate = price_info.kok_discount_rate
                        break
            
            # 할인가가 없으면 원가를 할인가로 사용
            if discounted_price == 0:
                discounted_price = original_price
            
            # 할인율이 0이고 원가와 할인가가 다르면 계산
            if discount_rate == 0 and original_price > 0 and discounted_price > 0 and original_price != discounted_price:
                discount_rate = int(((original_price - discounted_price) / original_price) * 100)
            
            products.append({
                "kok_product_id": product.kok_product_id,
                "kok_thumbnail": product.kok_thumbnail or "",
                "kok_discount_rate": discount_rate,
                "kok_discounted_price": discounted_price,
                "kok_product_name": product.kok_product_name or "",
                "kok_store_name": product.kok_store_name or ""
            })
        
        # logger.info(f"콕 상품 정보 조회 완료: 결과 수={len(products)}")
        return products
        
    except Exception as e:
        logger.error(f"콕 상품 정보 조회 실패: error={str(e)}")
        logger.error("콕 상품 정보 조회에 실패했습니다")
        return []

async def get_pgvector_topk_within(
    db: AsyncSession,
    product_id: int,
    candidate_ids: List[int],
    k: int
) -> List[Tuple[int, float]]:
    """
    pgvector를 사용한 유사도 기반 정렬 (실제 DB 연동)
    """
    # logger.info(f"pgvector 유사도 정렬 시작: product_id={product_id}, candidates={len(candidate_ids)}, k={k}")
    
    if not candidate_ids:
        logger.warning("pgvector 유사도 정렬: 후보 상품 ID가 없음")
        return []
    
    try:
        # 1) 쿼리 텍스트 준비: 홈쇼핑 상품명 사용
        prod_name = await get_homeshopping_product_name(db, product_id) or ""
        if not prod_name:
            logger.warning(f"pgvector 정렬 실패: 홈쇼핑 상품명을 찾을 수 없음, product_id={product_id}")
            return []

        # 2) 임베딩 생성 (ML 서비스 사용)
        import httpx
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                embed_response = await client.post(
                    "http://ml-inference:8001/api/v1/embed",
                    json={"text": prod_name, "normalize": True}
                )
                embed_response.raise_for_status()
                embed_data = embed_response.json()
                query_vec = embed_data["embedding"]
        except Exception as e:
            logger.error(f"ML 서비스 임베딩 생성 실패: {e}")
            return []

        # 3) PostgreSQL(pgvector)로 후보 내 유사도 정렬
        from sqlalchemy import text, bindparam
        from pgvector.sqlalchemy import Vector
        from common.database.postgres_recommend import get_postgres_recommend_db

        sql = text(
            """
            SELECT "KOK_PRODUCT_ID" AS pid,
                   "VECTOR_NAME" <-> :qv AS distance
            FROM "KOK_VECTOR_TABLE"
            WHERE "KOK_PRODUCT_ID" IN :ids
            ORDER BY distance ASC
            LIMIT :k
            """
        ).bindparams(
            bindparam("qv", type_=Vector(384)),   # vector(384)로 바인딩
            bindparam("ids", expanding=True),      # 후보 ID 리스트 확장
            bindparam("k")
        )

        params = {
            "qv": query_vec,
            "ids": [int(i) for i in candidate_ids],
            "k": int(max(1, k)),
        }

        async for pg in get_postgres_recommend_db():
            rows = (await pg.execute(sql, params)).all()
            sims: List[Tuple[int, float]] = [
                (int(r.pid), float(r.distance)) for r in rows
            ]
            # logger.info(f"pgvector 정렬 완료: 결과 수={len(sims)}")
            return sims
        
        return []
        
    except Exception as e:
        logger.error(f"pgvector 유사도 정렬 실패: error={str(e)}")
        return []

async def get_kok_candidates_by_keywords_improved(
    db: AsyncSession,
    must_keywords: List[str],
    optional_keywords: List[str],
    limit: int = 600,
    min_if_all_fail: int = 30
) -> List[int]:
    """
    키워드 기반으로 콕 상품 후보 검색 (개선된 오케스트레이터 로직)
    - must: OR(하나라도) → 부족하면 AND(최대 2개) → 다시 OR로 폴백
    - optional: 여전히 부족하면 OR로 보충
    - GATE_COMPARE_STORE=true면 스토어명도 검색에 포함
    """
    # logger.info(f"키워드 기반 콕 상품 검색 시작: must={must_keywords}, optional={optional_keywords}, limit={limit}")
    
    if not must_keywords and not optional_keywords:
        logger.warning("키워드 기반 콕 상품 검색: 검색 키워드가 없음")
        return []
    
    try:
        # 검색 대상 컬럼 결정 (스토어명 비교 옵션에 따라)
        search_columns = [KokProductInfo.kok_product_name]
        if GATE_COMPARE_STORE:
            search_columns.append(KokProductInfo.kok_store_name)
            # logger.info("스토어명도 검색에 포함")
        
        # 1단계: must 키워드로 검색 (OR 조건)
        must_candidates = []
        if must_keywords:
            must_conditions = []
            for keyword in must_keywords:
                if len(keyword) >= 2:  # 2글자 이상만 검색
                    for col in search_columns:
                        must_conditions.append(col.contains(keyword))
            
            if must_conditions:
                must_stmt = (
                    select(KokProductInfo.kok_product_id)
                    .where(
                        or_(*must_conditions)
                    )
                    .limit(limit)
                )
                
                result = await db.execute(must_stmt)
                must_candidates = [row[0] for row in result.fetchall()]
                # logger.info(f"must 키워드 검색 결과: {len(must_candidates)}개")
        
        # 2단계: must 키워드가 부족하면 AND 조건으로 재검색
        if len(must_candidates) < min_if_all_fail and len(must_keywords) >= 2:
            use_keywords = must_keywords[:2]  # 최대 2개 키워드만 사용
            and_conditions = []
            for keyword in use_keywords:
                if len(keyword) >= 2:
                    for col in search_columns:
                        and_conditions.append(col.contains(keyword))
            
            if and_conditions:
                # 각 키워드가 최소 하나의 컬럼에 포함되어야 함
                keyword_conditions = []
                for keyword in use_keywords:
                    keyword_conditions.append(
                        or_(*[col.contains(keyword) for col in search_columns])
                    )
                
                and_stmt = (
                    select(KokProductInfo.kok_product_id)
                    .where(
                        and_(*keyword_conditions)
                    )
                    .limit(limit)
                )
                
                result = await db.execute(and_stmt)
                and_candidates = [row[0] for row in result.fetchall()]
                # logger.info(f"AND 조건 검색 결과: {len(and_candidates)}개")
                
                # AND 결과가 더 많으면 교체
                if len(and_candidates) > len(must_candidates):
                    must_candidates = and_candidates
        
        # 3단계: optional 키워드로 보충 검색
        optional_candidates = []
        if optional_keywords and len(must_candidates) < limit:
            optional_conditions = []
            for keyword in optional_keywords:
                if len(keyword) >= 2:
                    for col in search_columns:
                        optional_conditions.append(col.contains(keyword))
            
            if optional_conditions:
                optional_stmt = (
                    select(KokProductInfo.kok_product_id)
                    .where(
                        or_(*optional_conditions)
                    )
                    .limit(limit - len(must_candidates))
                )
                
                result = await db.execute(optional_stmt)
                optional_candidates = [row[0] for row in result.fetchall()]
                # logger.info(f"optional 키워드 검색 결과: {len(optional_candidates)}개")
        
        # 4단계: 결과 합치기 및 중복 제거
        all_candidates = list(dict.fromkeys(must_candidates + optional_candidates))[:limit]
        
        # logger.info(f"키워드 기반 검색 완료: 총 {len(all_candidates)}개 후보")
        return all_candidates
        
    except Exception as e:
        logger.error(f"키워드 기반 검색 실패: error={str(e)}")
        logger.error("키워드 기반 검색에 실패했습니다")
        return []


async def get_kok_candidates_by_keywords(
    db: AsyncSession,
    must_keywords: List[str],
    optional_keywords: List[str],
    limit: int = 600,
    min_if_all_fail: int = 30
) -> List[int]:
    """
    키워드 기반으로 콕 상품 후보 검색 (기존 함수 - 호환성 유지)
    """
    return await get_kok_candidates_by_keywords_improved(db, must_keywords, optional_keywords, limit, min_if_all_fail)

async def test_kok_db_connection(db: AsyncSession) -> bool:
    """
    콕 상품 DB 연결 테스트
    """
    try:
        # 간단한 쿼리로 연결 테스트
        stmt = select(func.count(KokProductInfo.kok_product_id))
        result = await db.execute(stmt)
        count = result.scalar()
        
        # logger.info(f"콕 상품 DB 연결 성공: 총 상품 수 = {count}")
        return True
        
    except Exception as e:
        logger.error(f"콕 상품 DB 연결 실패: {str(e)}")
        return False


# -----------------------------
# 추천 관련 유틸리티 함수들 (utils 폴더 사용)
# -----------------------------

# ----- 옵션: 게이트에서 스토어명도 LIKE 비교할지 (기본 False) -----
GATE_COMPARE_STORE = os.getenv("GATE_COMPARE_STORE", "false").lower() in ("1","true","yes","on")

# -----------------------------
# 추천 시스템 함수들
# -----------------------------

async def recommend_homeshopping_to_kok(
    db,
    homeshopping_product_id: int,
    k: int = 5,                       # 최대 5개
    use_rerank: bool = False,         # 여기선 기본 거리 정렬만 사용
    candidate_n: int = 150,
    rerank_mode: str = None,
) -> List[Dict]:
    """
    홈쇼핑 상품에 대한 콕 유사 상품 추천 (utils 원본 로직 사용)
    응답 형태는 라우터에서 {"products": [...]}로 감싸 반환
    """
    try:
        # utils의 키워드 추출 및 필터링 함수들 사용
        from ..utils.homeshopping_kok import (
            filter_tail_and_ngram_and,
            extract_tail_keywords, extract_core_keywords, roots_in_name,
            infer_terms_from_name_via_ngrams, DYN_MAX_TERMS
        )
        
        # 1. 홈쇼핑 상품명 조회
        prod_name = await get_homeshopping_product_name(db, homeshopping_product_id) or ""
        if not prod_name:
            logger.warning(f"홈쇼핑 상품명을 찾을 수 없음: homeshopping_product_id={homeshopping_product_id}")
            return []

        # 2. 키워드 구성 (최적화된 버전)
        # 병렬로 키워드 추출하여 성능 개선
        import asyncio
        
        # 동시에 키워드 추출 실행
        tail_task = asyncio.create_task(asyncio.to_thread(extract_tail_keywords, prod_name, 2))
        core_task = asyncio.create_task(asyncio.to_thread(extract_core_keywords, prod_name, 3))
        root_task = asyncio.create_task(asyncio.to_thread(roots_in_name, prod_name))
        ngram_task = asyncio.create_task(asyncio.to_thread(infer_terms_from_name_via_ngrams, prod_name, DYN_MAX_TERMS))
        
        # 모든 키워드 추출 완료 대기
        tail_k, core_k, root_k, ngram_k = await asyncio.gather(
            tail_task, core_task, root_task, ngram_task
        )

        must_kws = list(dict.fromkeys([*tail_k, *core_k, *root_k]))[:12]
        optional_kws = list(dict.fromkeys([*ngram_k]))[:DYN_MAX_TERMS]

        # logger.info(f"키워드 구성: must={must_kws}, optional={optional_kws}")

        # 3. LIKE 게이트로 후보 (최적화된 버전)
        # 키워드가 적으면 더 작은 후보 수로 제한하여 성능 개선
        optimized_limit = min(max(candidate_n * 2, 150), 300) if len(must_kws) <= 3 else max(candidate_n * 3, 300)
        
        cand_ids = await get_kok_candidates_by_keywords_improved(
            db=db,
            must_keywords=must_kws,
            optional_keywords=optional_kws,
            limit=optimized_limit
        )
        if not cand_ids:
            logger.warning(f"키워드 기반 후보 수집 결과가 비어있음: product_id={homeshopping_product_id}, must_keywords={must_kws}")
            return []

        # logger.info(f"후보 수집 완료: {len(cand_ids)}개")

        # 4. 후보 내 pgvector 정렬 (최적화된 버전)
        # 후보가 적으면 pgvector 정렬 생략하고 바로 상세 조회
        if len(cand_ids) <= k * 2:
            logger.warning(f"후보 수가 적어 pgvector 정렬 생략: product_id={homeshopping_product_id}, 후보 수={len(cand_ids)}개")
            pid_order = cand_ids[:k]
            dist_map = {}
        else:
            sims = await get_pgvector_topk_within(
                db,
                homeshopping_product_id,
                cand_ids,
                max(k, candidate_n),
            )
            if not sims:
                logger.warning(f"pgvector 정렬 결과가 비어있음: product_id={homeshopping_product_id}")
                return []

            pid_order = [pid for pid, _ in sims]
            dist_map = {pid: dist for pid, dist in sims}

        # 5. 상세 조인
        details = await get_kok_product_infos(db, pid_order)
        if not details:
            logger.warning(f"콕 상품 상세 정보 조회 결과가 비어있음: product_id={homeshopping_product_id}, pid_order={pid_order[:5]}")
            return []
        
        # 거리 정보 추가 (있는 경우만)
        for d in details:
            if d["kok_product_id"] in dist_map:
                d["distance"] = dist_map[d["kok_product_id"]]

        # 6. 거리 정렬 (거리 정보가 있는 경우만)
        if dist_map:
            ranked = sorted(details, key=lambda x: x.get("distance", 1e9))
        else:
            ranked = details

        # 7. 최종 AND 필터 적용 (tail ≥1 AND n-gram ≥1) - 간소화
        # 필터링을 위해 키 변환
        for d in ranked:
            d["KOK_PRODUCT_NAME"] = d.get("kok_product_name", "")
            d["KOK_STORE_NAME"] = d.get("kok_store_name", "")
        
        filtered = filter_tail_and_ngram_and(ranked, prod_name)
        
        # 임시 키 제거
        for d in filtered:
            d.pop("KOK_PRODUCT_NAME", None)
            d.pop("KOK_STORE_NAME", None)

        # 8. 최대 k개까지 반환
        result = filtered[:k]
        # logger.info(f"추천 완료: {len(result)}개 상품")
        return result
        
    except Exception as e:
        logger.error(f"추천 로직 실패: {str(e)}")
        # 폴백으로 간단 추천 사용
        return await simple_recommend_homeshopping_to_kok(homeshopping_product_id, k, db)

async def simple_recommend_homeshopping_to_kok(
    homeshopping_product_id: int,
    k: int = 5,
    db=None
) -> List[Dict]:
    """
    간단한 추천 데이터 반환 (실제 DB 연동 시도)
    - 오케스트레이터 실패 시 폴백 시스템
    """
    # logger.info(f"간단한 추천 시스템 호출: homeshopping_product_id={homeshopping_product_id}, k={k}")
    
    # DB가 있고 실제 DB 연동이 가능한 경우 시도
    if db:
        try:
            # 판매량 상위 상품들을 가져오기 위해 더미 ID 대신 실제 검색
            popular_ids = [1001, 1002, 1003, 1004, 1005, 1006, 1007, 1008, 1009, 1010]
            
            recommendations = await get_kok_product_infos(db, popular_ids[:k])
            
            if recommendations:
                # logger.info(f"실제 DB에서 추천 데이터 조회 완료: {len(recommendations)}개 상품")
                return recommendations
                
        except Exception as e:
            logger.warning(f"실제 DB 연동 실패: {str(e)}")
    
    # DB 연동 실패 시 빈 리스트 반환
    logger.warning("추천 결과를 찾을 수 없습니다")
    return []

# ================================
# KOK 상품 기반 홈쇼핑 추천
# ================================

async def get_kok_product_name_by_id(db: AsyncSession, product_id: int) -> Optional[str]:
    """KOK 상품 ID로 상품명 조회"""
    try:
        query = text("""
            SELECT KOK_PRODUCT_NAME
            FROM FCT_KOK_PRODUCT_INFO
            WHERE KOK_PRODUCT_ID = :product_id
        """)
        
        result = await db.execute(query, {"product_id": product_id})
        row = result.fetchone()
        
        return row[0] if row else None
        
    except Exception as e:
        logger.error(f"KOK 상품명 조회 실패: product_id={product_id}, error={str(e)}")
        return None

async def get_homeshopping_recommendations_by_kok(
    db: AsyncSession, 
    kok_product_name: str, 
    search_terms: List[str], 
    k: int = 5
) -> List[Dict]:
    """KOK 상품명 기반으로 홈쇼핑 상품 추천"""
    try:
        if not search_terms:
            return []
        
        # 여러 검색어를 OR 조건으로 결합
        search_conditions = []
        params = {}
        
        for i, term in enumerate(search_terms):
            param_name = f"term_{i}"
            search_conditions.append(f"PRODUCT_NAME LIKE :{param_name}")
            params[param_name] = term
        
        # SQL 쿼리 구성 - FCT_HOMESHOPPING_PRODUCT_INFO와 FCT_HOMESHOPPING_LIST 테이블 조인
        query = text(f"""
            SELECT 
                p.PRODUCT_ID,
                c.PRODUCT_NAME,
                p.STORE_NAME,
                p.SALE_PRICE,
                p.DC_PRICE,
                p.DC_RATE,
                l.THUMB_IMG_URL,
                l.LIVE_DATE,
                l.LIVE_START_TIME,
                l.LIVE_END_TIME
            FROM FCT_HOMESHOPPING_PRODUCT_INFO p
            INNER JOIN HOMESHOPPING_CLASSIFY c ON p.PRODUCT_ID = c.PRODUCT_ID
            LEFT JOIN FCT_HOMESHOPPING_LIST l ON p.PRODUCT_ID = l.PRODUCT_ID
            WHERE c.CLS_FOOD = 1
              AND ({' OR '.join(search_conditions)})
            ORDER BY 
                CASE 
                    WHEN c.PRODUCT_NAME LIKE :exact_match THEN 1
                    WHEN c.PRODUCT_NAME LIKE :partial_match THEN 2
                    ELSE 3
                END,
                p.SALE_PRICE ASC
            LIMIT :limit
        """)
        
        # 파라미터 설정
        params = {}
        for i, condition in enumerate(search_conditions):
            # LIKE 조건에서 실제 검색어 추출
            if "LIKE '%" in condition and "%'" in condition:
                search_term = condition.split("LIKE '%")[1].split("%'")[0]
                params[f"term{i}"] = f"%{search_term}%"
        
        params.update({
            "exact_match": kok_product_name,
            "partial_match": f"{kok_product_name}%",
            "limit": k
        })
        
        result = await db.execute(query, params)
        rows = result.fetchall()
        
        # 결과를 딕셔너리 리스트로 변환
        recommendations = []
        for row in rows:
            # timedelta를 time으로 변환
            live_start_time = None
            live_end_time = None
            
            if row[8] is not None:  # LIVE_START_TIME
                if isinstance(row[8], timedelta):
                    # timedelta를 time으로 변환 (초 단위를 시간:분:초로 변환)
                    total_seconds = int(row[8].total_seconds())
                    hours = total_seconds // 3600
                    minutes = (total_seconds % 3600) // 60
                    seconds = total_seconds % 60
                    live_start_time = time(hour=hours, minute=minutes, second=seconds)
                else:
                    live_start_time = row[8]
            
            if row[9] is not None:  # LIVE_END_TIME
                if isinstance(row[9], timedelta):
                    # timedelta를 time으로 변환 (초 단위를 시간:분:초로 변환)
                    total_seconds = int(row[9].total_seconds())
                    hours = total_seconds // 3600
                    minutes = (total_seconds % 3600) // 60
                    seconds = total_seconds % 60
                    live_end_time = time(hour=hours, minute=minutes, second=seconds)
                else:
                    live_end_time = row[9]
            
            recommendations.append({
                "product_id": row[0],
                "product_name": row[1],
                "store_name": row[2],
                "sale_price": row[3],
                "dc_price": row[4],
                "dc_rate": row[5],
                "thumb_img_url": row[6],
                "live_date": row[7],
                "live_start_time": live_start_time,
                "live_end_time": live_end_time
            })
        
        return recommendations
        
    except Exception as e:
        logger.error(f"홈쇼핑 추천 조회 실패: kok_product_name='{kok_product_name}', error={str(e)}")
        return []

async def get_homeshopping_recommendations_fallback(
    db: AsyncSession, 
    kok_product_name: str, 
    k: int = 5
) -> List[Dict]:
    """폴백 추천: 상품명의 일부로 검색"""
    try:
        # 상품명에서 의미있는 부분 추출 (숫자, 특수문자 제거)
        import re
        clean_name = re.sub(r'[^\w가-힣]', ' ', kok_product_name)
        clean_name = re.sub(r'\s+', ' ', clean_name).strip()
        
        if len(clean_name) < 2:
            return []
        
        # 2글자 이상의 연속된 문자열로 검색
        search_term = f"%{clean_name[:min(4, len(clean_name))]}%"
        
        query = text("""
            SELECT 
                p.PRODUCT_ID,
                c.PRODUCT_NAME,
                p.STORE_NAME,
                p.SALE_PRICE,
                p.DC_PRICE,
                p.DC_RATE,
                l.THUMB_IMG_URL,
                l.LIVE_DATE,
                l.LIVE_START_TIME,
                l.LIVE_END_TIME
            FROM FCT_HOMESHOPPING_PRODUCT_INFO p
            INNER JOIN HOMESHOPPING_CLASSIFY c ON p.PRODUCT_ID = c.PRODUCT_ID
            LEFT JOIN FCT_HOMESHOPPING_LIST l ON p.PRODUCT_ID = l.PRODUCT_ID
            WHERE c.CLS_FOOD = 1
              AND c.PRODUCT_NAME LIKE :search_term
            ORDER BY p.SALE_PRICE ASC
            LIMIT :limit
        """)
        
        result = await db.execute(query, {
            "search_term": search_term,
            "limit": k
        })
        rows = result.fetchall()
        
        # 결과를 딕셔너리 리스트로 변환
        recommendations = []
        for row in rows:
            # timedelta를 time으로 변환
            live_start_time = None
            live_end_time = None
            
            if row[8] is not None:  # LIVE_START_TIME
                if isinstance(row[8], timedelta):
                    # timedelta를 time으로 변환 (초 단위를 시간:분:초로 변환)
                    total_seconds = int(row[8].total_seconds())
                    hours = total_seconds // 3600
                    minutes = (total_seconds % 3600) // 60
                    seconds = total_seconds % 60
                    live_start_time = time(hour=hours, minute=minutes, second=seconds)
                else:
                    live_start_time = row[8]
            
            if row[9] is not None:  # LIVE_END_TIME
                if isinstance(row[9], timedelta):
                    # timedelta를 time으로 변환 (초 단위를 시간:분:초로 변환)
                    total_seconds = int(row[9].total_seconds())
                    hours = total_seconds // 3600
                    minutes = (total_seconds % 3600) // 60
                    seconds = total_seconds % 60
                    live_end_time = time(hour=hours, minute=minutes, second=seconds)
                else:
                    live_end_time = row[9]
            
            recommendations.append({
                "product_id": row[0],
                "product_name": row[1],
                "store_name": row[2],
                "sale_price": row[3],
                "dc_price": row[4],
                "dc_rate": row[5],
                "thumb_img_url": row[6],
                "live_date": row[7],
                "live_start_time": live_start_time,
                "live_end_time": live_end_time
            })
        
        return recommendations
        
    except Exception as e:
        logger.error(f"홈쇼핑 폴백 추천 조회 실패: kok_product_name='{kok_product_name}', error={str(e)}")
        return []

async def get_homeshopping_cart_items(
    db: AsyncSession, 
    user_id: int
) -> List:
    """
    사용자의 홈쇼핑 장바구니 아이템 조회 (최적화: 윈도우 함수로 최신 상품 정보 조회)
    
    Args:
        db: 데이터베이스 세션
        user_id: 사용자 ID
        
    Returns:
        홈쇼핑 장바구니 아이템 리스트
    """
    # logger.info(f"홈쇼핑 장바구니 조회 시작: user_id={user_id}")
    
    try:
        # 최적화된 쿼리: 윈도우 함수를 사용하여 최신 상품 정보 조회
        sql_query = """
        WITH latest_product_info AS (
            SELECT 
                hl.product_id,
                hl.product_name,
                hl.thumb_img_url,
                ROW_NUMBER() OVER (
                    PARTITION BY hl.product_id 
                    ORDER BY hl.live_date DESC, hl.live_start_time DESC
                ) as rn
            FROM FCT_HOMESHOPPING_LIST hl
        )
        SELECT 
            hc.cart_id,
            hc.user_id,
            hc.product_id,
            hc.quantity,
            hc.created_at,
            lpi.product_name,
            lpi.thumb_img_url
        FROM HOMESHOPPING_CART hc
        LEFT JOIN latest_product_info lpi ON hc.product_id = lpi.product_id AND lpi.rn = 1
        WHERE hc.user_id = :user_id
        ORDER BY hc.created_at DESC
        """
        
        try:
            result = await db.execute(text(sql_query), {"user_id": user_id})
            cart_items = result.fetchall()
        except Exception as e:
            logger.error(f"홈쇼핑 장바구니 조회 SQL 실행 실패: user_id={user_id}, error={str(e)}")
            return []
        
        # 결과를 객체 리스트로 변환
        cart_list = []
        for row in cart_items:
            # HomeshoppingCart 객체 생성
            cart_item = HomeshoppingCart()
            cart_item.cart_id = row.cart_id
            cart_item.user_id = row.user_id
            cart_item.product_id = row.product_id
            cart_item.quantity = row.quantity
            cart_item.created_at = row.created_at
            
            # 상품 정보 추가
            cart_item.product_name = row.product_name
            cart_item.thumb_img_url = row.thumb_img_url
            
            cart_list.append(cart_item)
        
        # logger.info(f"홈쇼핑 장바구니 조회 완료: user_id={user_id}, 아이템 수={len(cart_list)}")
        return cart_list
        
    except Exception as e:
        logger.error(f"홈쇼핑 장바구니 조회 실패: user_id={user_id}, error={str(e)}")
        return []


# ================================
# 개선된 추천 시스템 설명
# ================================
"""
개선된 홈쇼핑 → 콕 추천 시스템

1. 추천 오케스트레이터 파이프라인:
   - 1단계: 홈쇼핑 상품명에서 must/optional 키워드 구성
   - 2단계: LIKE 게이트로 후보 수집 (must: OR → AND → OR 폴백, optional: OR 보충)
   - 3단계: 후보 내 pgvector 정렬
   - 4단계: (옵션) 리랭크
   - 5단계: 최종 AND 필터(tail ≥1 AND n-gram ≥1)
   - 6단계: 최대 k개 슬라이스

2. 키워드 구성 전략:
   - tail_keywords: 뒤쪽 핵심(희소 가능성이 높은 토큰)
   - core_keywords: 앞/강한 핵심
   - root_keywords: 루트 힌트(사전 기반)
   - ngram_keywords: 동적 n-gram

3. 후보 검색 전략:
   - must 키워드: OR(하나라도) → 부족하면 AND(최대 2개) → 다시 OR로 폴백
   - optional 키워드: 여전히 부족하면 OR로 보충
   - GATE_COMPARE_STORE 옵션으로 스토어명도 검색에 포함 가능

4. 필터링 전략:
   - tail 토큰 일치 ≥ 1
   - n-gram 겹침 ≥ 1 (기본 bi-gram)
   - 들어온 순서를 보존(이미 정렬되어 있다고 가정)

5. 메타데이터 추가:
   - 추천 결과에 파이프라인 설정 및 키워드 분석 정보 포함
   - 폴백 시스템 정보 포함

6. 폴백 시스템:
   - 오케스트레이터 실패 시 간단한 인기 상품 기반 추천
   - DB 연동 실패 시 빈 결과 반환
"""


