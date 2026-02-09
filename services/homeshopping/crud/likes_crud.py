from datetime import datetime
from typing import List

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from services.homeshopping.models.core_model import HomeshoppingList, HomeshoppingProductInfo
from services.homeshopping.models.interaction_model import HomeshoppingLikes
from services.homeshopping.crud.notification_crud import (
    create_broadcast_notification,
    delete_broadcast_notification,
)
from .shared import logger

async def toggle_homeshopping_likes(
    db: AsyncSession,
    user_id: int,
    homeshopping_live_id: int
) -> bool:
    """
    홈쇼핑 방송 찜 등록/해제
    - live_id를 찜 목록에서 조회한 후 없을 경우 추가
    - live_id를 찜 목록에서 조회했을 때 있는 경우에는 삭제
    """
    # logger.info(f"홈쇼핑 찜 토글 시작: user_id={user_id}, homeshopping_live_id={homeshopping_live_id}")
    
    try:
        # 데이터베이스 연결 상태 확인
        # logger.info(f"데이터베이스 세션 상태 확인: {db.is_active}")
        
        # 기존 찜 여부 확인
        # logger.info(f"기존 찜 조회 시작: user_id={user_id}, homeshopping_live_id={homeshopping_live_id}")
        existing_like_result = await db.execute(
            select(HomeshoppingLikes).where(
                and_(
                    HomeshoppingLikes.user_id == user_id,
                    HomeshoppingLikes.live_id == homeshopping_live_id
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
            
            # logger.info(f"홈쇼핑 찜 해제 완료: user_id={user_id}, homeshopping_live_id={homeshopping_live_id}")
            return False
            
        else:
            # 기존 찜이 없으면 찜 등록
            # logger.info(f"새로운 찜 등록 처리: user_id={user_id}, homeshopping_live_id={homeshopping_live_id}")
            
            # 찜 레코드 생성
            new_like = HomeshoppingLikes(
                user_id=user_id,
                live_id=homeshopping_live_id,
                homeshopping_like_created_at=datetime.now()
            )
            db.add(new_like)
            # logger.info("찜 레코드 생성 완료")
            
            try:
                # 방송 정보 조회하여 알림 생성
                # logger.info(f"방송 정보 조회 시작: homeshopping_live_id={homeshopping_live_id}")
                live_info_result = await db.execute(
                    select(HomeshoppingList).where(
                        HomeshoppingList.live_id == homeshopping_live_id
                    )
                )
                live_info = live_info_result.scalar_one_or_none()
                # logger.info(f"방송 정보 조회 결과: {live_info is not None}")
                
                if live_info and live_info.live_date and live_info.live_start_time:
                    # 방송 시작 알림 생성
                    await create_broadcast_notification(
                        db=db,
                        user_id=user_id,
                        homeshopping_like_id=new_like.homeshopping_like_id,
                        live_id=homeshopping_live_id,
                        homeshopping_product_name=live_info.product_name,
                        broadcast_date=live_info.live_date,
                        broadcast_start_time=live_info.live_start_time
                    )
                    # logger.info(f"방송 시작 알림 생성 완료: like_id={new_like.homeshopping_like_id}")
                else:
                    logger.warning("방송 정보가 부족하여 알림을 생성하지 않음")
            except Exception as e:
                logger.warning(f"방송 알림 생성 실패 (무시하고 진행): {str(e)}")
            
            # logger.info(f"홈쇼핑 찜 등록 완료: user_id={user_id}, homeshopping_live_id={homeshopping_live_id}, like_id={new_like.homeshopping_like_id}")
            return True
            
    except Exception as e:
        logger.error(f"홈쇼핑 찜 토글 실패: user_id={user_id}, homeshopping_live_id={homeshopping_live_id}, error={str(e)}")
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
    홈쇼핑 찜한 상품 목록 조회 (중복 제거)
    """
    # logger.info(f"홈쇼핑 찜한 상품 조회 시작: user_id={user_id}, limit={limit}")
    
    # user_id 검증 (논리 FK이므로 실제 USERS 테이블 존재 여부는 확인하지 않음)
    if user_id <= 0:
        logger.warning(f"유효하지 않은 user_id: {user_id}")
        return []
    
    stmt = (
        select(
            HomeshoppingList.live_id,
            HomeshoppingLikes.live_id,
            HomeshoppingLikes.homeshopping_like_created_at,
            HomeshoppingList.product_id,
            HomeshoppingList.product_name,
            HomeshoppingList.thumb_img_url,
            HomeshoppingProductInfo.store_name,
            HomeshoppingProductInfo.dc_price,
            HomeshoppingProductInfo.dc_rate,
            HomeshoppingList.live_date,
            HomeshoppingList.live_start_time,
            HomeshoppingList.live_end_time,
            HomeshoppingList.homeshopping_id
        )
        .select_from(HomeshoppingLikes)
        .join(HomeshoppingList, HomeshoppingLikes.live_id == HomeshoppingList.live_id)
        .join(HomeshoppingProductInfo, HomeshoppingList.product_id == HomeshoppingProductInfo.product_id)
        .where(HomeshoppingLikes.user_id == user_id)
        .order_by(
            HomeshoppingList.live_date.asc(),
            HomeshoppingList.live_start_time.asc(),
            HomeshoppingList.live_id.asc(),
            HomeshoppingLikes.live_id
        )
    )
    
    try:
        results = await db.execute(stmt)
        all_liked_products = results.all()
    except Exception as e:
        logger.error(f"홈쇼핑 찜한 상품 조회 SQL 실행 실패: user_id={user_id}, error={str(e)}")
        raise
    
    # Python에서 중복 제거 (live_id 기준)
    seen_lives = set()
    product_list = []
    
    for row in all_liked_products:
        if row.live_id not in seen_lives:
            seen_lives.add(row.live_id)
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
            
            # limit에 도달하면 중단
            if len(product_list) >= limit:
                break
    
    # logger.info(f"홈쇼핑 찜한 상품 조회 완료: user_id={user_id}, 결과 수={len(product_list)}")
    return product_list
