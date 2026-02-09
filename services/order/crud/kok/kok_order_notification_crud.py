"""Kok order notification/history CRUD functions."""

from typing import List

from sqlalchemy.ext.asyncio import AsyncSession

from common.logger import get_logger

logger = get_logger("kok_order_crud")

async def get_kok_order_notifications_history(
    db: AsyncSession, 
    user_id: int, 
    limit: int = 20, 
    offset: int = 0
) -> tuple[List[dict], int]:
    """
    사용자의 콕 상품 주문 내역 현황 알림 조회 (최적화: Raw SQL 사용)
    
    Args:
        db: 데이터베이스 세션
        user_id: 사용자 ID
        limit: 조회할 알림 개수 (기본값: 20)
        offset: 건너뛸 알림 개수 (기본값: 0)
    
    Returns:
        tuple: (알림 목록, 전체 개수)
        
    Note:
        - Raw SQL을 사용하여 성능 최적화
        - 주문완료, 배송출발, 배송완료 알림만 조회
        - 주문상태, 상품이름, 알림 메시지, 알림 날짜 포함
        - created_at 기준으로 내림차순 정렬
        - 페이지네이션 지원 (limit, offset)
    """    
    from sqlalchemy import text
    
    # 주문 현황 관련 상태 코드들
    order_status_codes = ["PAYMENT_COMPLETED", "SHIPPING", "DELIVERED"]
    
    # 최적화된 쿼리: Raw SQL 사용
    sql_query = """
    SELECT 
        kn.notification_id,
        kn.user_id,
        kn.kok_order_id,
        kn.status_id,
        kn.title,
        kn.message,
        kn.created_at,
        sm.status_code,
        sm.status_name,
        kpi.kok_product_name
    FROM KOK_NOTIFICATION kn
    INNER JOIN STATUS_MASTER sm ON kn.status_id = sm.status_id
    INNER JOIN KOK_ORDERS ko ON kn.kok_order_id = ko.kok_order_id
    INNER JOIN FCT_KOK_PRODUCT_INFO kpi ON ko.kok_product_id = kpi.kok_product_id
    WHERE kn.user_id = :user_id
    AND sm.status_code IN :order_status_codes
    ORDER BY kn.created_at DESC
    LIMIT :limit OFFSET :offset
    """
    
    # 전체 개수 조회
    count_sql = """
    SELECT COUNT(*)
    FROM KOK_NOTIFICATION kn
    INNER JOIN STATUS_MASTER sm ON kn.status_id = sm.status_id
    WHERE kn.user_id = :user_id
    AND sm.status_code IN :order_status_codes
    """
    
    try:
        # 전체 개수 조회
        count_result = await db.execute(text(count_sql), {
            "user_id": user_id,
            "order_status_codes": tuple(order_status_codes)
        })
        total_count = count_result.scalar()
        
        # 알림 목록 조회
        result = await db.execute(text(sql_query), {
            "user_id": user_id,
            "order_status_codes": tuple(order_status_codes),
            "limit": limit,
            "offset": offset
        })
        notifications_data = result.fetchall()
    except Exception as e:
        logger.error(f"콕 알림 조회 SQL 실행 실패: user_id={user_id}, limit={limit}, offset={offset}, error={str(e)}")
        return [], 0
    
    # 결과를 딕셔너리로 변환
    notifications = []
    for row in notifications_data:
        notification_dict = {
            "notification_id": row.notification_id,
            "user_id": row.user_id,
            "kok_order_id": row.kok_order_id,
            "status_id": row.status_id,
            "title": row.title,
            "message": row.message,
            "created_at": row.created_at,
            "order_status": row.status_code,
            "order_status_name": row.status_name,
            "product_name": row.kok_product_name
        }
        notifications.append(notification_dict)
    
    return notifications, total_count


# ------------------------------------------------------------------------------------------------
# 콕 주문 생성 함수
# ------------------------------------------------------------------------------------------------  
# async def create_kok_order(
#         db: AsyncSession,
#         user_id: int,
#         kok_price_id: int,
#         kok_product_id: int,
#         quantity: int = 1,
#         recipe_id: int | None = None
# ) -> Order:
#     """
#     콕 상품 주문 생성 및 할인 가격 반영
#     - kok_price_id로 할인 가격 조회 후 quantity 곱해서 order_price 자동계산
#     - 기본 상태는 'PAYMENT_COMPLETED'로 설정
#     - 주문 생성 시 초기 알림도 생성
#     """
#     try:
#         # 0. 사용자 ID 유효성 검증
#         if not await validate_user_exists(user_id, db):
#             raise Exception("유효하지 않은 사용자 ID입니다")
        
#         # 1. 할인 가격 조회
#         result = await db.execute(
#             select(KokPriceInfo.kok_discounted_price)
#             .where(KokPriceInfo.kok_price_id == kok_price_id) # type: ignore
#         )
#         discounted_price = result.scalar_one_or_none()
#         if discounted_price is None:
#             raise Exception(f"해당 kok_price_id({kok_price_id})에 해당하는 할인 가격 없음")

#         # 2. 주문가격 계산
#         order_price = discounted_price * quantity

#         # 3. 주문접수 상태 조회
#         order_received_status = await get_status_by_code(db, "ORDER_RECEIVED")
#         if not order_received_status:
#             raise Exception("주문접수 상태 코드를 찾을 수 없습니다")

#         # 4. 주문 데이터 생성 (트랜잭션)
#         # 4-1. 상위 주문 생성
#         new_order = Order(
#             user_id=user_id,
#             order_time=datetime.now()
#         )
#         db.add(new_order)
#         await db.flush()  # order_id 생성

#         # 4-2. 콕 주문 상세 생성
#         new_kok_order = KokOrder(
#             order_id=new_order.order_id,
#             kok_price_id=kok_price_id,
#             kok_product_id=kok_product_id,
#             quantity=quantity,
#             order_price=order_price,
#             recipe_id=recipe_id
#         )
#         db.add(new_kok_order)
#         await db.flush()  # kok_order_id 생성

#         # 4-3. 상태 변경 이력 생성 (초기 상태: ORDER_RECEIVED)
#         status_history = KokOrderStatusHistory(
#             kok_order_id=new_kok_order.kok_order_id,
#             status_id=order_received_status.status_id,
#             changed_by=user_id
#         )
#         db.add(status_history)

#         # 4-4. 초기 알림 생성 (ORDER_RECEIVED)
#         await create_kok_notification_for_status_change(
#             db=db,
#             kok_order_id=new_kok_order.kok_order_id,
#             status_id=order_received_status.status_id,
#             user_id=user_id
#         )

#         await db.commit()
        
#         # 5. 1초 후 PAYMENT_REQUESTED 상태로 변경 (백그라운드 작업)
#         async def update_status_to_payment_requested():
#             await asyncio.sleep(1)  # 1초 대기
            
#             try:
#                 # PAYMENT_REQUESTED 상태 조회
#                 payment_requested_status = await get_status_by_code(db, "PAYMENT_REQUESTED")
#                 if payment_requested_status:
#                     # 상태 이력 추가
#                     new_status_history = KokOrderStatusHistory(
#                         kok_order_id=new_kok_order.kok_order_id,
#                         status_id=payment_requested_status.status_id,
#                         changed_by=user_id
#                     )
                    
#                     # 결제 요청 알림 생성
#                     await create_kok_notification_for_status_change(
#                         db=db,
#                         kok_order_id=new_kok_order.kok_order_id,
#                         status_id=payment_requested_status.status_id,
#                         user_id=user_id
#                     )
                    
#                     db.add(new_status_history)
#                     await db.commit()
                    
#                     logger.info(f"콕 주문 상태 변경 완료: order_id={new_order.order_id}, status=PAYMENT_REQUESTED")
                    
#             except Exception as e:
#                 logger.error(f"콕 주문 상태 변경 실패: order_id={new_order.order_id}, error={str(e)}")
        
#         # 백그라운드에서 상태 변경 실행
#         asyncio.create_task(update_status_to_payment_requested())
        
#         await db.refresh(new_order)
#         return new_order
        
#     except Exception as e:
#         await db.rollback()
#         logger.error(f"주문 생성 실패: {str(e)}")
#         raise e

