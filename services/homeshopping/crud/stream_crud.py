from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from services.homeshopping.models.core_model import HomeshoppingInfo, HomeshoppingList
from .shared import logger

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
