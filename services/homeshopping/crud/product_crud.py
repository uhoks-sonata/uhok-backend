from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from services.homeshopping.models.core_model import (
    HomeshoppingDetailInfo,
    HomeshoppingImgUrl,
    HomeshoppingInfo,
    HomeshoppingList,
    HomeshoppingProductInfo,
)
from services.homeshopping.models.interaction_model import HomeshoppingLikes
from .shared import logger

async def get_homeshopping_product_detail(
    db: AsyncSession,
    live_id: int,
    user_id: Optional[int] = None
) -> Optional[dict]:
    """
    홈쇼핑 상품 상세 정보 조회
    """
    # logger.info(f"홈쇼핑 상품 상세 조회 시작: live_id={live_id}, user_id={user_id}")
    
    # live_id로 방송 정보 조회 (채널 정보 포함)
    stmt = (
        select(HomeshoppingList, HomeshoppingProductInfo, HomeshoppingInfo)
        .join(HomeshoppingProductInfo, HomeshoppingList.product_id == HomeshoppingProductInfo.product_id)
        .join(HomeshoppingInfo, HomeshoppingList.homeshopping_id == HomeshoppingInfo.homeshopping_id)
        .where(HomeshoppingList.live_id == live_id)
    )
    
    try:
        result = await db.execute(stmt)
        product_data = result.first()
    except Exception as e:
        logger.error(f"홈쇼핑 상품 상세 조회 SQL 실행 실패: live_id={live_id}, error={str(e)}")
        raise
    
    if not product_data:
        logger.warning(f"상품을 찾을 수 없음: live_id={live_id}")
        return None
    
    live, product, homeshopping = product_data
    
    # 찜 상태 확인
    is_liked = False
    if user_id:
        like_stmt = select(HomeshoppingLikes).where(
            HomeshoppingLikes.user_id == user_id,
            HomeshoppingLikes.live_id == live_id
        )
        like_result = await db.execute(like_stmt)
        is_liked = like_result.scalars().first() is not None
    
    # 상세 정보 조회
    detail_stmt = (
        select(HomeshoppingDetailInfo)
        .where(HomeshoppingDetailInfo.product_id == live.product_id)
        .order_by(HomeshoppingDetailInfo.detail_id)
    )
    try:
        detail_result = await db.execute(detail_stmt)
        detail_infos = detail_result.scalars().all()
    except Exception as e:
        logger.warning(f"상품 상세 정보 조회 실패: product_id={live.product_id}, error={str(e)}")
        detail_infos = []
    
    # 이미지 조회
    img_stmt = (
        select(HomeshoppingImgUrl)
        .where(HomeshoppingImgUrl.product_id == live.product_id)
        .order_by(HomeshoppingImgUrl.sort_order)
    )
    try:
        img_result = await db.execute(img_stmt)
        images = img_result.scalars().all()
    except Exception as e:
        logger.warning(f"상품 이미지 조회 실패: product_id={live.product_id}, error={str(e)}")
        images = []
    
    # 응답 데이터 구성 (채널 정보 포함)
    product_detail = {
        "product": {
            "product_id": live.product_id,
            "product_name": live.product_name,
            "store_name": product.store_name if product.store_name else None,
            "sale_price": product.sale_price if product.sale_price else None,
            "dc_price": product.dc_price if product.dc_price else None,
            "dc_rate": product.dc_rate if product.dc_rate else None,
            "live_date": live.live_date,
            "live_start_time": live.live_start_time,
            "live_end_time": live.live_end_time,
            "thumb_img_url": live.thumb_img_url,
            "is_liked": is_liked,
            
            # 채널 정보 추가
            "homeshopping_id": homeshopping.homeshopping_id if homeshopping else None,
            "homeshopping_name": homeshopping.homeshopping_name if homeshopping else None,
            "homeshopping_channel": homeshopping.homeshopping_channel if homeshopping else None,
            "homeshopping_channel_name": f"채널 {homeshopping.homeshopping_channel}" if homeshopping and homeshopping.homeshopping_channel else None,
            "homeshopping_channel_image": f"/images/channels/channel_{homeshopping.homeshopping_channel}.jpg" if homeshopping and homeshopping.homeshopping_channel else None
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
