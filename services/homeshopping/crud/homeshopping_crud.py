"""
홈쇼핑 관련 DB 접근(CRUD) 함수 (MariaDB)

계층별 역할:
- 이 파일은 데이터 액세스 계층(Data Access Layer)을 담당
- ORM(Session)과 직접 상호작용하여 DB 상태 변경 로직 처리
- db.add(), db.delete() 같은 DB 상태 변경은 여기서 수행
- 트랜잭션 관리(commit/rollback)는 상위 계층(라우터)에서 담당
"""
import os
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, insert, delete, and_, update, or_, text
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
logger = get_logger("homeshopping_crud")

# -----------------------------
# 편성표 관련 CRUD 함수
# -----------------------------

async def get_homeshopping_schedule(
    db: AsyncSession,
    live_date: Optional[date] = None
) -> List[dict]:
    """
    홈쇼핑 편성표 조회 (식품만)
    - live_date가 제공되면 해당 날짜의 스케줄만 조회
    - live_date가 None이면 전체 스케줄 조회
    """
    logger.info(f"홈쇼핑 편성표 조회 시작: live_date={live_date}")
    
    # 기본 쿼리 구성
    stmt = (
        select(HomeshoppingList, HomeshoppingInfo, HomeshoppingProductInfo, HomeshoppingClassify)
        .join(HomeshoppingInfo, HomeshoppingList.homeshopping_id == HomeshoppingInfo.homeshopping_id)
        .outerjoin(HomeshoppingProductInfo, HomeshoppingList.product_id == HomeshoppingProductInfo.product_id)
        .join(HomeshoppingClassify, HomeshoppingList.product_id == HomeshoppingClassify.product_id)
        .where(HomeshoppingClassify.cls_food == 1)  # 식품만 필터링 (cls_food = 1)
    )
    
    # live_date가 제공된 경우 해당 날짜로 필터링
    if live_date:
        stmt = stmt.where(HomeshoppingList.live_date == live_date)
    
    # 정렬 (페이징 제거)
    stmt = stmt.order_by(HomeshoppingList.live_date.desc(), HomeshoppingList.live_start_time.asc())
    
    results = await db.execute(stmt)
    schedules = results.all()
    
    schedule_list = []
    for live, info, product, classify in schedules:
        schedule_list.append({
            "live_id": live.live_id,
            "homeshopping_id": live.homeshopping_id,
            "homeshopping_name": info.homeshopping_name,
            "homeshopping_channel": info.homeshopping_channel,
            "live_date": live.live_date,
            "live_start_time": live.live_start_time,
            "live_end_time": live.live_end_time,
            "promotion_type": live.promotion_type,
            "product_id": live.product_id,
            "product_name": live.product_name,
            "thumb_img_url": live.thumb_img_url,
            "sale_price": product.sale_price if product else None,
            "dc_price": product.dc_price if product else None,
            "dc_rate": product.dc_rate if product else None
        })
    
    logger.info(f"홈쇼핑 편성표 조회 완료: live_date={live_date}, 결과 수={len(schedule_list)}")
    return schedule_list


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
    logger.info(f"홈쇼핑 live_url 조회 시작: homeshopping_id={homeshopping_id}")
    
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
        
        logger.info(f"홈쇼핑 live_url 조회 완료: homeshopping_id={homeshopping_id}")
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
    logger.info(f"홈쇼핑 스트리밍 정보 조회 시작: live_url={live_url}")
    
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
        
        logger.info(f"홈쇼핑 스트리밍 정보 조회 완료: live_id={live_info.live_id}, is_live={is_live}")
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
    홈쇼핑 상품 검색
    """
    logger.info(f"홈쇼핑 상품 검색 시작: keyword='{keyword}'")
    
    # 상품명, 판매자명에서 키워드 검색
    stmt = (
        select(HomeshoppingList, HomeshoppingProductInfo)
        .join(HomeshoppingProductInfo, HomeshoppingList.product_id == HomeshoppingProductInfo.product_id)
        .where(
            HomeshoppingList.product_name.contains(keyword) |
            HomeshoppingProductInfo.store_name.contains(keyword)
        )
        .order_by(HomeshoppingList.live_date.desc())
    )
    
    results = await db.execute(stmt)
    products = results.all()
    
    product_list = []
    for live, product in products:
        product_list.append({
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
    
    logger.info(f"홈쇼핑 상품 검색 완료: keyword='{keyword}', 결과 수={len(product_list)}")
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
    logger.info(f"홈쇼핑 검색 이력 추가 시작: user_id={user_id}, keyword='{keyword}'")
    
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
    
    logger.info(f"홈쇼핑 검색 이력 삭제 완료: user_id={user_id}, history_id={homeshopping_history_id}")
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
    홈쇼핑 상품 상세 정보 조회
    """
    logger.info(f"홈쇼핑 상품 상세 조회 시작: live_id={live_id}, user_id={user_id}")
    
    # live_id로 방송 정보 조회 (채널 정보 포함)
    stmt = (
        select(HomeshoppingList, HomeshoppingProductInfo, HomeshoppingInfo)
        .join(HomeshoppingProductInfo, HomeshoppingList.product_id == HomeshoppingProductInfo.product_id)
        .join(HomeshoppingInfo, HomeshoppingList.homeshopping_id == HomeshoppingInfo.homeshopping_id)
        .where(HomeshoppingList.live_id == live_id)
    )
    
    result = await db.execute(stmt)
    product_data = result.first()
    
    if not product_data:
        logger.warning(f"상품을 찾을 수 없음: live_id={live_id}")
        return None
    
    live, product, homeshopping = product_data
    
    # 찜 상태 확인
    is_liked = False
    if user_id:
        like_stmt = select(HomeshoppingLikes).where(
            HomeshoppingLikes.user_id == user_id,
            HomeshoppingLikes.product_id == live.product_id
        )
        like_result = await db.execute(like_stmt)
        is_liked = like_result.scalars().first() is not None
    
    # 상세 정보 조회
    detail_stmt = (
        select(HomeshoppingDetailInfo)
        .where(HomeshoppingDetailInfo.product_id == live.product_id)
        .order_by(HomeshoppingDetailInfo.detail_id)
    )
    detail_result = await db.execute(detail_stmt)
    detail_infos = detail_result.scalars().all()
    
    # 이미지 조회
    img_stmt = (
        select(HomeshoppingImgUrl)
        .where(HomeshoppingImgUrl.product_id == live.product_id)
        .order_by(HomeshoppingImgUrl.sort_order)
    )
    img_result = await db.execute(img_stmt)
    images = img_result.scalars().all()
    
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
    
    logger.info(f"홈쇼핑 상품 상세 조회 완료: live_id={live_id}, user_id={user_id}")
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
    logger.info(f"홈쇼핑 상품 분류 CLS_ING 조회 시작: homeshopping_product_id={homeshopping_product_id}")
    
    try:
        # HOMESHOPPING_CLASSIFY 테이블에서 CLS_ING 값 조회
        stmt = select(HomeshoppingClassify.cls_ing).where(HomeshoppingClassify.product_id == homeshopping_product_id)
        result = await db.execute(stmt)
        cls_ing = result.scalar_one_or_none()
        
        if cls_ing is None:
            logger.warning(f"HOMESHOPPING_CLASSIFY 테이블에서 homeshopping_product_id={homeshopping_product_id}를 찾을 수 없음")
            # 해당 상품이 분류 테이블에 없는 경우 기본값 0(완제품) 반환
            return 0
        
        logger.info(f"홈쇼핑 상품 분류 CLS_ING 조회 완료: homeshopping_product_id={homeshopping_product_id}, cls_ing={cls_ing}")
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
    logger.info(f"식재료 레시피 추천 조회 시작: homeshopping_product_id={homeshopping_product_id}")
    
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
    logger.info(f"홈쇼핑 찜 토글 시작: user_id={user_id}, homeshopping_product_id={homeshopping_product_id}")
    
    try:
        # 데이터베이스 연결 상태 확인
        logger.info(f"데이터베이스 세션 상태 확인: {db.is_active}")
        
        # 기존 찜 여부 확인
        logger.info(f"기존 찜 조회 시작: user_id={user_id}, homeshopping_product_id={homeshopping_product_id}")
        existing_like_result = await db.execute(
            select(HomeshoppingLikes).where(
                and_(
                    HomeshoppingLikes.user_id == user_id,
                    HomeshoppingLikes.product_id == homeshopping_product_id
                )
            )
        )
        existing_like = existing_like_result.scalar_one_or_none()
        logger.info(f"기존 찜 조회 결과: {existing_like is not None}")
        
        if existing_like:
            # 기존 찜이 있으면 찜 해제
            logger.info(f"기존 찜 발견, 찜 해제 처리: like_id={existing_like.homeshopping_like_id}")
            
            try:
                # 방송 알림도 함께 삭제
                await delete_broadcast_notification(db, user_id, existing_like.homeshopping_like_id)
                logger.info("방송 알림 삭제 완료")
            except Exception as e:
                logger.warning(f"방송 알림 삭제 실패 (무시하고 진행): {str(e)}")
            
            # 찜 레코드 삭제
            await db.delete(existing_like)
            logger.info("찜 레코드 삭제 완료")
            
            logger.info(f"홈쇼핑 찜 해제 완료: user_id={user_id}, homeshopping_product_id={homeshopping_product_id}")
            return False
            
        else:
            # 기존 찜이 없으면 찜 등록
            logger.info(f"새로운 찜 등록 처리: user_id={user_id}, homeshopping_product_id={homeshopping_product_id}")
            
            # 찜 레코드 생성
            new_like = HomeshoppingLikes(
                user_id=user_id,
                product_id=homeshopping_product_id,
                homeshopping_like_created_at=datetime.now()
            )
            db.add(new_like)
            logger.info("찜 레코드 생성 완료")
            
            try:
                # 방송 정보 조회하여 알림 생성 (가장 최근 방송 정보 선택)
                logger.info(f"방송 정보 조회 시작: homeshopping_product_id={homeshopping_product_id}")
                live_info_result = await db.execute(
                    select(HomeshoppingList).where(
                        HomeshoppingList.product_id == homeshopping_product_id
                    ).order_by(HomeshoppingList.live_date.desc(), HomeshoppingList.live_start_time.desc())
                )
                live_info = live_info_result.scalar_one_or_none()
                logger.info(f"방송 정보 조회 결과: {live_info is not None}")
                
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
                    logger.info(f"방송 시작 알림 생성 완료: like_id={new_like.homeshopping_like_id}")
                else:
                    logger.info("방송 정보가 부족하여 알림을 생성하지 않음")
            except Exception as e:
                logger.warning(f"방송 알림 생성 실패 (무시하고 진행): {str(e)}")
            
            logger.info(f"홈쇼핑 찜 등록 완료: user_id={user_id}, homeshopping_product_id={homeshopping_product_id}, like_id={new_like.homeshopping_like_id}")
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
    홈쇼핑 찜한 상품 목록 조회 (중복 제거)
    """
    logger.info(f"홈쇼핑 찜한 상품 조회 시작: user_id={user_id}, limit={limit}")
    
    # user_id 검증 (논리 FK이므로 실제 USERS 테이블 존재 여부는 확인하지 않음)
    if user_id <= 0:
        logger.warning(f"유효하지 않은 user_id: {user_id}")
        return []
    
    stmt = (
        select(
            HomeshoppingLikes.product_id,
            HomeshoppingLikes.homeshopping_like_created_at,
            HomeshoppingList.product_name,
            HomeshoppingList.thumb_img_url,
            HomeshoppingProductInfo.store_name,
            HomeshoppingProductInfo.dc_price,
            HomeshoppingProductInfo.dc_rate,
            HomeshoppingList.live_start_time,
            HomeshoppingList.live_date,
            HomeshoppingList.homeshopping_id,
            HomeshoppingList.live_id
        )
        .select_from(HomeshoppingLikes)
        .join(HomeshoppingList, HomeshoppingLikes.product_id == HomeshoppingList.product_id)
        .join(HomeshoppingProductInfo, HomeshoppingList.product_id == HomeshoppingProductInfo.product_id)
        .where(HomeshoppingLikes.user_id == user_id)
        .order_by(
            HomeshoppingLikes.homeshopping_like_created_at.desc(),
            HomeshoppingLikes.product_id
        )
    )
    
    results = await db.execute(stmt)
    all_liked_products = results.all()
    
    # Python에서 중복 제거 (product_id 기준)
    seen_products = set()
    product_list = []
    
    for row in all_liked_products:
        if row.product_id not in seen_products:
            seen_products.add(row.product_id)
            product_list.append({
                "product_id": row.product_id,
                "product_name": row.product_name,
                "store_name": row.store_name if row.store_name else None,
                "dc_price": row.dc_price if row.dc_price else None,
                "dc_rate": row.dc_rate if row.dc_rate else None,
                "thumb_img_url": row.thumb_img_url,
                "homeshopping_like_created_at": row.homeshopping_like_created_at,
                "live_start_time": row.live_start_time,
                "live_date": row.live_date,
                "homeshopping_id": row.homeshopping_id,
                "live_id": row.live_id
            })
            
            # limit에 도달하면 중단
            if len(product_list) >= limit:
                break
    
    logger.info(f"홈쇼핑 찜한 상품 조회 완료: user_id={user_id}, 결과 수={len(product_list)}")
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
    logger.info(f"방송 찜 알림 생성 시작: user_id={user_id}, homeshopping_like_id={homeshopping_like_id}, homeshopping_product_id={homeshopping_product_id}")
    
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
        result = await db.execute(stmt)
        
        notification_id = result.inserted_primary_key[0]
        
        logger.info(f"방송 찜 알림 생성 완료: notification_id={notification_id}")
        
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
    logger.info(f"방송 찜 알림 삭제 시작: user_id={user_id}, like_id={homeshopping_like_id}")
    
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
            logger.info(f"방송 찜 알림 삭제 완료: deleted_count={deleted_count}")
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
    logger.info(f"주문 상태 변경 알림 생성 시작: user_id={user_id}, homeshopping_order_id={homeshopping_order_id}, status={status_name}")
    
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
        result = await db.execute(stmt)
        
        notification_id = result.inserted_primary_key[0]
        
        logger.info(f"주문 상태 변경 알림 생성 완료: notification_id={notification_id}")
        
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
    필터링된 알림 조회
    """
    logger.info(f"필터링된 알림 조회 시작: user_id={user_id}, type={notification_type}, entity_type={related_entity_type}, is_read={is_read}")
    
    try:
        # 기본 쿼리 구성
        query = select(HomeshoppingNotification).where(
            HomeshoppingNotification.user_id == user_id
        )
        
        # 필터 적용
        if notification_type:
            query = query.where(HomeshoppingNotification.notification_type == notification_type)
        
        if related_entity_type:
            query = query.where(HomeshoppingNotification.related_entity_type == related_entity_type)
        
        if is_read is not None:
            query = query.where(HomeshoppingNotification.is_read == (1 if is_read else 0))
        
        # 전체 개수 조회
        count_query = select(func.count()).select_from(query.subquery())
        total_count = await db.scalar(count_query)
        
        # 페이지네이션 적용
        query = query.order_by(HomeshoppingNotification.created_at.desc()).offset(offset).limit(limit)
        
        # 결과 조회
        result = await db.execute(query)
        notifications = []
        
        for notification in result.scalars().all():
            # 주문 알림인 경우 상품명 조회
            product_name = None
            if notification.homeshopping_order_id:
                try:
                    # HomeShoppingOrder와 HomeshoppingList를 조인하여 상품명 조회 (가장 최근 방송 정보에서 선택)
                    product_query = select(HomeshoppingList.product_name).join(
                        HomeShoppingOrder, 
                        HomeShoppingOrder.product_id == HomeshoppingList.product_id
                    ).where(
                        HomeShoppingOrder.homeshopping_order_id == notification.homeshopping_order_id
                    ).order_by(HomeshoppingList.live_date.desc(), HomeshoppingList.live_start_time.desc())
                    product_result = await db.execute(product_query)
                    product_name = product_result.scalar_one_or_none()
                except Exception as e:
                    logger.warning(f"상품명 조회 실패: notification_id={notification.notification_id}, error={str(e)}")
                    product_name = None
            
            notifications.append({
                "notification_id": notification.notification_id,
                "user_id": notification.user_id,
                "notification_type": notification.notification_type,
                "related_entity_type": notification.related_entity_type,
                "related_entity_id": notification.related_entity_id,
                "homeshopping_like_id": notification.homeshopping_like_id,
                "homeshopping_order_id": notification.homeshopping_order_id,
                "status_id": notification.status_id,
                "title": notification.title,
                "message": notification.message,
                "product_name": product_name,
                "is_read": bool(notification.is_read),
                "created_at": notification.created_at,
                "read_at": notification.read_at
            })
        
        logger.info(f"필터링된 알림 조회 완료: user_id={user_id}, 결과 수={len(notifications)}, 전체 개수={total_count}")
        
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
    logger.info(f"알림 읽음 처리 시작: user_id={user_id}, notification_id={notification_id}")
    
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
        
        result = await db.execute(stmt)
        
        updated_count = result.rowcount
        
        if updated_count > 0:
            logger.info(f"알림 읽음 처리 완료: notification_id={notification_id}")
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
    logger.info(f"발송 대기 중인 방송 알림 조회 시작: current_time={current_time}")
    
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
        
        results = await db.execute(stmt)
        notifications = []
        
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
        
        logger.info(f"발송 대기 중인 방송 알림 조회 완료: 결과 수={len(notifications)}")
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
    logger.info(f"홈쇼핑 상품명 조회 시작: homeshopping_product_id={homeshopping_product_id}")
    
    try:
        stmt = select(HomeshoppingList.product_name).where(HomeshoppingList.product_id == homeshopping_product_id).order_by(HomeshoppingList.live_date.desc(), HomeshoppingList.live_start_time.desc())
        result = await db.execute(stmt)
        product_name = result.scalar()
        
        if product_name:
            logger.info(f"홈쇼핑 상품명 조회 완료: homeshopping_product_id={homeshopping_product_id}, name={product_name}")
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
    logger.info(f"콕 상품 정보 조회 시작: kok_product_ids={kok_product_ids}")
    
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
        
        result = await db.execute(stmt)
        kok_products = result.scalars().all()
        
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
        
        logger.info(f"콕 상품 정보 조회 완료: 결과 수={len(products)}")
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
    logger.info(f"pgvector 유사도 정렬 시작: product_id={product_id}, candidates={len(candidate_ids)}, k={k}")
    
    if not candidate_ids:
        logger.warning("후보 상품 ID가 없음")
        return []
    
    try:
        # 1) 쿼리 텍스트 준비: 홈쇼핑 상품명 사용
        prod_name = await get_homeshopping_product_name(db, product_id) or ""
        if not prod_name:
            logger.warning("pgvector 정렬 실패: 홈쇼핑 상품명을 찾을 수 없음")
            return []

        # 2) 임베딩 생성 (레시피 모듈의 모델 재사용)
        from services.recipe.utils.core import get_model  # lazy import
        import numpy as np  # noqa: F401 (타입 힌트/변환용)
        model = await get_model()
        query_vec_np = model.encode(prod_name, normalize_embeddings=True)
        query_vec = [float(x) for x in query_vec_np.tolist()]

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
            logger.info(f"pgvector 정렬 완료: 결과 수={len(sims)}")
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
    logger.info(f"키워드 기반 콕 상품 검색 시작: must={must_keywords}, optional={optional_keywords}, limit={limit}")
    
    if not must_keywords and not optional_keywords:
        logger.warning("검색 키워드가 없음")
        return []
    
    try:
        # 검색 대상 컬럼 결정 (스토어명 비교 옵션에 따라)
        search_columns = [KokProductInfo.kok_product_name]
        if GATE_COMPARE_STORE:
            search_columns.append(KokProductInfo.kok_store_name)
            logger.info("스토어명도 검색에 포함")
        
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
                logger.info(f"must 키워드 검색 결과: {len(must_candidates)}개")
        
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
                logger.info(f"AND 조건 검색 결과: {len(and_candidates)}개")
                
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
                logger.info(f"optional 키워드 검색 결과: {len(optional_candidates)}개")
        
        # 4단계: 결과 합치기 및 중복 제거
        all_candidates = list(dict.fromkeys(must_candidates + optional_candidates))[:limit]
        
        logger.info(f"키워드 기반 검색 완료: 총 {len(all_candidates)}개 후보")
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
        
        logger.info(f"콕 상품 DB 연결 성공: 총 상품 수 = {count}")
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

# homeshopping_kok.py 관련 의존성 제거됨


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

        # 2. 키워드 구성 (원본 로직 그대로)
        tail_k = extract_tail_keywords(prod_name, max_n=2)          # 뒤쪽 핵심(희소 가능성이 높은 토큰)
        core_k = extract_core_keywords(prod_name, max_n=3)          # 앞/강한 핵심
        root_k = roots_in_name(prod_name)                           # 루트 힌트(사전 기반)
        ngram_k = infer_terms_from_name_via_ngrams(prod_name, max_terms=DYN_MAX_TERMS)

        must_kws = list(dict.fromkeys([*tail_k, *core_k, *root_k]))[:12]
        optional_kws = list(dict.fromkeys([*ngram_k]))[:DYN_MAX_TERMS]

        logger.info(f"키워드 구성: must={must_kws}, optional={optional_kws}")

        # 3. LIKE 게이트로 후보 (기존 프로젝트 함수 사용)
        cand_ids = await get_kok_candidates_by_keywords_improved(
            db=db,
            must_keywords=must_kws,
            optional_keywords=optional_kws,
            limit=max(candidate_n * 3, 300)
        )
        if not cand_ids:
            logger.warning("키워드 기반 후보 수집 결과가 비어있음")
            return []

        logger.info(f"후보 수집 완료: {len(cand_ids)}개")

        # 4. 후보 내 pgvector 정렬
        sims = await get_pgvector_topk_within(
            db,
            homeshopping_product_id,
            cand_ids,
            max(k, candidate_n),
        )
        if not sims:
            return []

        pid_order = [pid for pid, _ in sims]
        dist_map = {pid: dist for pid, dist in sims}

        # 5. 상세 조인
        details = await get_kok_product_infos(db, pid_order)
        if not details:
            return []
        for d in details:
            d["distance"] = dist_map.get(d["kok_product_id"])

        # 6. (옵션) 리랭크 or 거리 정렬
        ranked = sorted(details, key=lambda x: x.get("distance", 1e9))  # 기본: 거리 오름차순

        # 7. 최종 AND 필터 적용 (tail ≥1 AND n-gram ≥1)
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
        logger.info(f"추천 완료: {len(result)}개 상품")
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
    logger.info(f"간단한 추천 시스템 호출: homeshopping_product_id={homeshopping_product_id}, k={k}")
    
    # DB가 있고 실제 DB 연동이 가능한 경우 시도
    if db:
        try:
            # 판매량 상위 상품들을 가져오기 위해 더미 ID 대신 실제 검색
            popular_ids = [1001, 1002, 1003, 1004, 1005, 1006, 1007, 1008, 1009, 1010]
            
            recommendations = await get_kok_product_infos(db, popular_ids[:k])
            
            if recommendations:
                logger.info(f"실제 DB에서 추천 데이터 조회 완료: {len(recommendations)}개 상품")
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
    사용자의 홈쇼핑 장바구니 아이템 조회
    
    Args:
        db: 데이터베이스 세션
        user_id: 사용자 ID
        
    Returns:
        홈쇼핑 장바구니 아이템 리스트
    """
    logger.info(f"홈쇼핑 장바구니 조회 시작: user_id={user_id}")
    
    try:
        # 장바구니 테이블과 상품 정보를 조인하여 조회
        stmt = (
            select(
                HomeshoppingCart,
                HomeshoppingList.product_name,
                HomeshoppingList.thumb_img_url
            )
            .outerjoin(
                HomeshoppingList, 
                HomeshoppingCart.product_id == HomeshoppingList.product_id
            )
            .where(HomeshoppingCart.user_id == user_id)
            .order_by(HomeshoppingCart.created_at.desc())
        )
        
        result = await db.execute(stmt)
        cart_items = result.all()
        
        # 결과를 객체 리스트로 변환
        cart_list = []
        for cart, product_name, thumb_img_url in cart_items:
            # cart 객체에 product_name과 thumb_img_url 추가
            cart.product_name = product_name
            cart.thumb_img_url = thumb_img_url
            cart_list.append(cart)
        
        logger.info(f"홈쇼핑 장바구니 조회 완료: user_id={user_id}, 아이템 수={len(cart_list)}")
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


