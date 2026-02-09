from datetime import date, datetime, time, timedelta
from typing import List, Optional, Tuple

from sqlalchemy import and_, delete, func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from services.homeshopping.models.core_model import HomeshoppingList, HomeshoppingProductInfo
from services.homeshopping.models.interaction_model import (
    HomeshoppingLikes,
    HomeshoppingNotification,
)
from services.order.models.homeshopping.hs_order_model import HomeShoppingOrder
from .shared import logger

async def create_broadcast_notification(
    db: AsyncSession,
    user_id: int,
    homeshopping_like_id: int,
    live_id: int,
    homeshopping_product_name: str,
    broadcast_date: date,
    broadcast_start_time: time
) -> dict:
    """
    방송 찜 알림 생성
    """
    # logger.info(f"방송 찜 알림 생성 시작: user_id={user_id}, homeshopping_like_id={homeshopping_like_id}, live_id={live_id}")
    
    try:
        # 방송 시작 알림 생성
        notification_data = {
            "user_id": user_id,
            "notification_type": "broadcast_start",
            "related_entity_type": "live",
            "related_entity_id": live_id,
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
    필터링된 알림 조회
    """
    # logger.info(f"필터링된 알림 조회 시작: user_id={user_id}, type={notification_type}, entity_type={related_entity_type}, is_read={is_read}")
    
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
        try:
            total_count = await db.scalar(count_query)
        except Exception as e:
            logger.error(f"알림 개수 조회 실패: user_id={user_id}, error={str(e)}")
            total_count = 0
        
        # 페이지네이션 적용
        query = query.order_by(HomeshoppingNotification.created_at.desc()).offset(offset).limit(limit)
        
        # 결과 조회
        try:
            result = await db.execute(query)
            notifications = []
        except Exception as e:
            logger.error(f"알림 목록 조회 실패: user_id={user_id}, error={str(e)}")
            return [], 0
        
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
                    ).order_by(HomeshoppingList.live_date.asc(), HomeshoppingList.live_start_time.asc(), HomeshoppingList.live_id.asc()).limit(1)
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
            .join(HomeshoppingList, HomeshoppingLikes.live_id == HomeshoppingList.live_id)
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
