"""
홈쇼핑 관련 DB 접근(CRUD) 함수 (MariaDB)
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional, List, Tuple
from datetime import datetime, date, time
from common.logger import get_logger

from services.homeshopping.models.homeshopping_model import (
    HomeshoppingInfo,
    HomeshoppingList,
    HomeshoppingProductInfo,
    HomeshoppingDetailInfo,
    HomeshoppingImgUrl,
    HomeshoppingSearchHistory,
    HomeshoppingLikes,
    HomeshoppingNotification
)
from services.order.models.order_model import (
    Order,
    HomeShoppingOrder,
    HomeShoppingOrderStatusHistory,
    StatusMaster
)

logger = get_logger("homeshopping_crud")

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
        .order_by(HomeshoppingList.live_date.desc(), HomeshoppingList.live_start_time.asc())
        .offset(offset)
        .limit(size)
    )
    
    results = await db.execute(stmt)
    schedules = results.all()
    
    schedule_list = []
    for live, info in schedules:
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
            "dc_price": product.dc_price,
            "dc_rate": product.dc_rate,
            "thumb_img_url": live.thumb_img_url,
            "live_date": live.live_date,
            "live_start_time": live.live_start_time,
            "live_end_time": live.live_end_time
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
    await db.commit()
    
    logger.info(f"홈쇼핑 검색 이력 삭제 완료: user_id={user_id}, history_id={homeshopping_history_id}")
    return True


# -----------------------------
# 상품 상세 관련 CRUD 함수
# -----------------------------

async def get_homeshopping_product_detail(
    db: AsyncSession,
    product_id: int,
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
            "store_name": product.store_name if product.store_name else None,
            "sale_price": product.sale_price if product.sale_price else None,
            "dc_price": product.dc_price if product.dc_price else None,
            "dc_rate": product.dc_rate if product.dc_rate else None,
            "live_date": live.live_date,
            "live_start_time": live.live_start_time,
            "live_end_time": live.live_end_time,
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
    product_id: int
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
            "product_id": 1001,
            "product_name": "고기 요리용 양념 세트",
            "recommendation_type": "recipe",
            "reason": "이 재료와 어울리는 양념 세트"
        })
    else:
        # 완제품인 경우 -> 관련 식재료 추천
        recommendations.append({
            "product_id": 2001,
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
    product_id: int
) -> bool:
    """
    홈쇼핑 찜 등록/해제 토글
    """
    logger.info(f"홈쇼핑 찜 토글 시작: user_id={user_id}, product_id={product_id}")
    
    # user_id와 product_id 검증
    if user_id <= 0:
        logger.warning(f"유효하지 않은 user_id: {user_id}")
        return False
    
    if product_id <= 0:
        logger.warning(f"유효하지 않은 product_id: {product_id}")
        return False
    
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
            homeshopping_like_created_at=created_at
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
    
    # user_id 검증 (논리 FK이므로 실제 USERS 테이블 존재 여부는 확인하지 않음)
    if user_id <= 0:
        logger.warning(f"유효하지 않은 user_id: {user_id}")
        return []
    
    stmt = (
        select(HomeshoppingLikes, HomeshoppingList, HomeshoppingProductInfo)
        .join(HomeshoppingList, HomeshoppingLikes.product_id == HomeshoppingList.product_id)
        .join(HomeshoppingProductInfo, HomeshoppingList.product_id == HomeshoppingProductInfo.product_id)
        .where(HomeshoppingLikes.user_id == user_id)
        .order_by(HomeshoppingLikes.homeshopping_like_created_at.desc())
        .limit(limit)
    )
    
    results = await db.execute(stmt)
    liked_products = results.all()
    
    product_list = []
    for like, live, product in liked_products:
        product_list.append({
            "product_id": live.product_id,
            "product_name": live.product_name,
            "store_name": product.store_name if product.store_name else None,
            "dc_price": product.dc_price if product.dc_price else None,
            "dc_rate": product.dc_rate if product.dc_rate else None,
            "thumb_img_url": live.thumb_img_url,
            "homeshopping_like_created_at": like.homeshopping_like_created_at
        })
    
    logger.info(f"홈쇼핑 찜한 상품 조회 완료: user_id={user_id}, 결과 수={len(product_list)}")
    return product_list


# -----------------------------
# 주문 관련 CRUD 함수 (기본 구조)
# -----------------------------

async def create_homeshopping_order(
    db: AsyncSession,
    user_id: int,
    product_id: int,
    quantity: int
) -> dict:
    """
    홈쇼핑 주문 생성 (단건 주문)
    """
    logger.info(f"홈쇼핑 주문 생성 시작: user_id={user_id}, product_id={product_id}, quantity={quantity}")
    
    try:
        # 1. 상품 정보 조회 (할인가 확인)
        product_stmt = select(HomeshoppingProductInfo).where(
            HomeshoppingProductInfo.product_id == product_id
        )
        product_result = await db.execute(product_stmt)
        product = product_result.scalar_one_or_none()
        
        if not product:
            logger.error(f"상품을 찾을 수 없음: product_id={product_id}")
            raise ValueError("상품을 찾을 수 없습니다.")
        
        # 2. 상품명 조회
        live_stmt = select(HomeshoppingList).where(
            HomeshoppingList.product_id == product_id
        )
        live_result = await db.execute(live_stmt)
        live = live_result.scalar_one_or_none()
        
        product_name = live.product_name if live else f"상품_{product_id}"
        
        # 3. 주문 금액 계산
        dc_price = product.dc_price or product.sale_price or 0
        order_price = dc_price * quantity
        
        # 4. 주문 생성 (ORDERS 테이블)
        order_time = datetime.now()
        new_order = Order(
            user_id=user_id,
            order_time=order_time
        )
        
        db.add(new_order)
        await db.flush()  # order_id 생성
        
        # 5. 홈쇼핑 주문 상세 생성 (HOMESHOPPING_ORDERS 테이블)
        new_homeshopping_order = HomeShoppingOrder(
            order_id=new_order.order_id,
            product_id=product_id,
            dc_price=dc_price,
            quantity=quantity,
            order_price=order_price
        )
        
        db.add(new_homeshopping_order)
        await db.flush()  # homeshopping_order_id 생성
        
        # 6. 주문 상태 이력 생성 (초기 상태: 주문접수)
        # STATUS_MASTER에서 'ORDER_RECEIVED' 상태 ID 조회
        status_stmt = select(StatusMaster).where(
            StatusMaster.status_code == "ORDER_RECEIVED"
        )
        status_result = await db.execute(status_stmt)
        status = status_result.scalar_one_or_none()
        
        if status:
            new_status_history = HomeShoppingOrderStatusHistory(
                homeshopping_order_id=new_homeshopping_order.homeshopping_order_id,
                status_id=status.status_id,
                changed_at=order_time,
                changed_by=user_id
            )
            db.add(new_status_history)
        
        # 7. 홈쇼핑 알림 생성
        new_notification = HomeshoppingNotification(
            user_id=user_id,
            homeshopping_order_id=new_homeshopping_order.homeshopping_order_id,
            status_id=status.status_id if status else 1,  # 기본값
            title="주문이 접수되었습니다",
            message=f"{product_name} 주문이 성공적으로 접수되었습니다."
        )
        
        db.add(new_notification)
        
        # 8. 모든 변경사항 커밋
        await db.commit()
        
        # 9. 1초 후 PAYMENT_REQUESTED 상태로 변경 (백그라운드 작업)
        import asyncio
        
        async def update_status_to_payment_requested():
            await asyncio.sleep(1)  # 1초 대기
            
            try:
                # PAYMENT_REQUESTED 상태 조회
                payment_status_stmt = select(StatusMaster).where(
                    StatusMaster.status_code == "PAYMENT_REQUESTED"
                )
                payment_status_result = await db.execute(payment_status_stmt)
                payment_status = payment_status_result.scalar_one_or_none()
                
                if payment_status:
                    # 상태 이력 추가
                    new_payment_status_history = HomeShoppingOrderStatusHistory(
                        homeshopping_order_id=new_homeshopping_order.homeshopping_order_id,
                        status_id=payment_status.status_id,
                        changed_at=datetime.now(),
                        changed_by=user_id
                    )
                    
                    # 결제 요청 알림 생성
                    payment_notification = HomeshoppingNotification(
                        user_id=user_id,
                        homeshopping_order_id=new_homeshopping_order.homeshopping_order_id,
                        status_id=payment_status.status_id,
                        title="결제가 요청되었습니다",
                        message=f"{product_name} 주문에 대한 결제가 요청되었습니다."
                    )
                    
                    db.add(new_payment_status_history)
                    db.add(payment_notification)
                    await db.commit()
                    
                    logger.info(f"홈쇼핑 주문 상태 변경 완료: order_id={new_order.order_id}, status=PAYMENT_REQUESTED")
                    
            except Exception as e:
                logger.error(f"홈쇼핑 주문 상태 변경 실패: order_id={new_order.order_id}, error={str(e)}")
        
        # 백그라운드에서 상태 변경 실행
        asyncio.create_task(update_status_to_payment_requested())
        
        logger.info(f"홈쇼핑 주문 생성 완료: user_id={user_id}, order_id={new_order.order_id}, homeshopping_order_id={new_homeshopping_order.homeshopping_order_id}")
        
        return {
            "order_id": new_order.order_id,
            "homeshopping_order_id": new_homeshopping_order.homeshopping_order_id,
            "product_id": product_id,
            "product_name": product_name,
            "quantity": quantity,
            "dc_price": dc_price,
            "order_price": order_price,
            "order_time": order_time,
            "message": "주문이 성공적으로 생성되었습니다."
        }
        
    except Exception as e:
        await db.rollback()
        logger.error(f"홈쇼핑 주문 생성 실패: user_id={user_id}, product_id={product_id}, error={str(e)}")
        raise


# -----------------------------
# 스트리밍 관련 CRUD 함수 (기본 구조)
# -----------------------------

async def get_homeshopping_stream_info(
    db: AsyncSession,
    product_id: int
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
        # date를 datetime으로 변환하여 연산
        live_datetime = datetime.combine(live_date, datetime.min.time())
        time_diff = abs((now - live_datetime).total_seconds())
        is_live = time_diff < 3600  # 1시간 이내면 라이브로 간주
    
    stream_info = {
        "product_id": product_id,
        "stream_url": f"https://stream.example.com/live/{product_id}",  # 임시 URL
        "is_live": is_live,
        "live_start_time": product.live_start_time,
        "live_end_time": product.live_end_time
    }
    
    logger.info(f"홈쇼핑 스트리밍 정보 조회 완료: product_id={product_id}, is_live={is_live}")
    return stream_info

# -----------------------------
# 알림 관련 CRUD 함수
# -----------------------------

async def get_homeshopping_notifications_history(
    db: AsyncSession,
    user_id: int,
    limit: int = 20,
    offset: int = 0
) -> Tuple[List[dict], int]:
    """
    홈쇼핑 알림 내역 조회
    """
    logger.info(f"홈쇼핑 알림 내역 조회 시작: user_id={user_id}, limit={limit}, offset={offset}")
    
    try:
        # 전체 알림 개수 조회
        count_stmt = (
            select(func.count())
            .select_from(HomeshoppingNotification)
            .where(HomeshoppingNotification.user_id == user_id)
        )
        total_count = await db.execute(count_stmt)
        total_count = total_count.scalar()
        
        # 알림 목록 조회
        stmt = (
            select(HomeshoppingNotification)
            .where(HomeshoppingNotification.user_id == user_id)
            .order_by(HomeshoppingNotification.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        
        results = await db.execute(stmt)
        notifications = results.scalars().all()
        
        notification_list = []
        for notification in notifications:
            notification_list.append({
                "notification_id": notification.notification_id,
                "homeshopping_order_id": notification.homeshopping_order_id,
                "status_id": notification.status_id,
                "title": notification.title,
                "message": notification.message,
                "created_at": notification.created_at
            })
        
        logger.info(f"홈쇼핑 알림 내역 조회 완료: user_id={user_id}, 결과 수={len(notification_list)}, 전체 개수={total_count}")
        return notification_list, total_count
        
    except Exception as e:
        logger.error(f"홈쇼핑 알림 내역 조회 실패: user_id={user_id}, error={str(e)}")
        raise
