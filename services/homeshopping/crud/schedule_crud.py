import asyncio
from datetime import date, datetime
from typing import List, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from services.homeshopping.utils.cache_manager import cache_manager
from .shared import logger

async def get_homeshopping_schedule(
    db: AsyncSession,
    live_date: Optional[date] = None
) -> List[dict]:
    """
    홈쇼핑 편성표 조회 (식품만) - 캐싱 최적화 버전
    - live_date가 제공되면 해당 날짜의 스케줄만 조회
    - live_date가 None이면 전체 스케줄 조회
    - Redis 캐싱으로 성능 최적화
    - 제한 없이 모든 결과 반환
    """
    logger.info(f"홈쇼핑 편성표 조회 시작: live_date={live_date}")
    
    # Redis 캐시 활성화
    cached_result = await cache_manager.get_schedule_cache(live_date)
    if cached_result:
        schedules = cached_result
        logger.info(f"캐시에서 스케줄 조회 완료: 결과 수={len(schedules)}")
        return schedules
    
    # DB에서 직접 조회
    logger.info("DB에서 스케줄 조회 (캐시 미스)")
    
    # 극한 최적화: 더 간단한 Raw SQL 사용
    # live_date에 따라 다른 쿼리 사용
    if live_date:
        # 특정 날짜 조회 - 가격 정보 포함
        sql_query = """
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
            COALESCE(hpi.dc_rate, 0) as dc_rate
        FROM FCT_HOMESHOPPING_LIST hl
        INNER JOIN HOMESHOPPING_INFO hi ON hl.homeshopping_id = hi.homeshopping_id
        INNER JOIN HOMESHOPPING_CLASSIFY hc ON hl.product_id = hc.product_id
        LEFT JOIN FCT_HOMESHOPPING_PRODUCT_INFO hpi ON hl.product_id = hpi.product_id
        WHERE hl.live_date = :live_date
        AND hc.cls_food = 1
        ORDER BY hl.live_date ASC, hl.live_start_time ASC, hl.live_id ASC
        """
        params = {"live_date": live_date}
    else:
        # 전체 스케줄 조회 - 가격 정보 포함
        sql_query = """
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
            COALESCE(hpi.dc_rate, 0) as dc_rate
        FROM FCT_HOMESHOPPING_LIST hl
        INNER JOIN HOMESHOPPING_INFO hi ON hl.homeshopping_id = hi.homeshopping_id
        INNER JOIN HOMESHOPPING_CLASSIFY hc ON hl.product_id = hc.product_id
        LEFT JOIN FCT_HOMESHOPPING_PRODUCT_INFO hpi ON hl.product_id = hpi.product_id
        WHERE hc.cls_food = 1
        ORDER BY hl.live_date ASC, hl.live_start_time ASC, hl.live_id ASC
        """
        params = {}
    
    # Raw SQL 실행
    # logger.info("최적화된 Raw SQL로 스케줄 데이터 조회 시작")
    try:
        result = await db.execute(text(sql_query), params)
        schedules = result.fetchall()
    except Exception as e:
        logger.error(f"스케줄 조회 Raw SQL 실행 실패: live_date={live_date}, error={str(e)}")
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
    
    # Redis 캐시 저장 활성화
    asyncio.create_task(
        cache_manager.set_schedule_cache(schedule_list, live_date)
    )
    
    logger.info(f"홈쇼핑 편성표 조회 완료: live_date={live_date}, 결과 수={len(schedule_list)}")
    return schedule_list
