"""
ORDERS + 서비스별 주문 상세를 트랜잭션으로 한 번에 생성/조회 (HomeShopping 명칭 통일)
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from services.order.models.order_model import (
    Order, KokOrder, HomeShoppingOrder, StatusMaster
)

from common.database.mariadb_auth import get_maria_auth_db
from common.logger import get_logger

logger = get_logger("order_crud")

# 상태 코드 상수 정의
STATUS_CODES = {
    "ORDER_RECEIVED": "주문 생성", 
    "PAYMENT_REQUESTED": "결제 요청",
    "PAYMENT_COMPLETED": "결제완료",
    "PREPARING": "상품준비중",
    "SHIPPING": "배송중",
    "DELIVERED": "배송완료",
    "CANCELLED": "주문취소",
    "REFUND_REQUESTED": "환불요청",
    "REFUND_COMPLETED": "환불완료"
}

# 알림 제목 매핑
NOTIFICATION_TITLES = {
    "ORDER_RECEIVED": "주문 생성",
    "PAYMENT_REQUESTED": "결제 요청",
    "PAYMENT_COMPLETED": "주문 완료",
    "PREPARING": "상품 준비",
    "SHIPPING": "배송 시작",
    "DELIVERED": "배송 완료",
    "CANCELLED": "주문 취소",
    "REFUND_REQUESTED": "환불 요청",
    "REFUND_COMPLETED": "환불 완료"
}

# 알림 메시지 매핑
NOTIFICATION_MESSAGES = {
    "ORDER_RECEIVED": "주문이 생성되었습니다.",
    "PAYMENT_REQUESTED": "결제가 요청되었습니다.",
    "PAYMENT_COMPLETED": "주문이 성공적으로 완료되었습니다.",
    "PREPARING": "상품 준비를 시작합니다.",
    "SHIPPING": "상품이 배송을 시작합니다.",
    "DELIVERED": "상품이 배송 완료되었습니다.",
    "CANCELLED": "주문이 취소되었습니다.",
    "REFUND_REQUESTED": "환불이 요청되었습니다.",
    "REFUND_COMPLETED": "환불이 완료되었습니다."
}

async def initialize_status_master(db: AsyncSession):
    """
    STATUS_MASTER 테이블에 기본 상태 코드들을 초기화
    """
    for status_code, status_name in STATUS_CODES.items():
        # 기존 상태 코드 확인
        existing = await get_status_by_code(db, status_code)
        if not existing:
            # 새 상태 코드 추가
            new_status = StatusMaster(
                status_code=status_code,
                status_name=status_name
            )
            db.add(new_status)
    
    await db.commit()

async def validate_user_exists(user_id: int, db: AsyncSession) -> bool:
    """
    사용자 ID가 유효한지 검증 (AUTH_DB.USERS 테이블 확인)
    """
    from services.user.models.user_model import User
    
    # AUTH_DB에서 사용자 조회
    auth_db = get_maria_auth_db()
    async for auth_session in auth_db:
        result = await auth_session.execute(
            select(User).where(User.user_id == user_id)
        )
        user = result.scalars().first()
        return user is not None
    
    return False

async def get_status_by_code(db: AsyncSession, status_code: str) -> StatusMaster:
    """
    상태 코드로 상태 정보 조회
    """
    result = await db.execute(
        select(StatusMaster).where(StatusMaster.status_code == status_code)
    )
    return result.scalars().first()

async def get_order_by_id(db: AsyncSession, order_id: int) -> dict:
    """
    주문 ID로 통합 주문 조회 (공통 정보 + 서비스별 상세)
    """
    # 주문 기본 정보 조회
    result = await db.execute(
        select(Order).where(Order.order_id == order_id)
    )
    order = result.scalars().first()
    
    if not order:
        return None
    
    # 콕 주문 정보 조회
    kok_result = await db.execute(
        select(KokOrder).where(KokOrder.order_id == order.order_id)
    )
    kok_orders = kok_result.scalars().all()
    
    # 홈쇼핑 주문 정보 조회
    homeshopping_result = await db.execute(
        select(HomeShoppingOrder).where(HomeShoppingOrder.order_id == order.order_id)
    )
    homeshopping_orders = homeshopping_result.scalars().all()
    
    # 딕셔너리 형태로 반환
    return {
        "order_id": order.order_id,
        "user_id": order.user_id,
        "order_time": order.order_time,
        "cancel_time": order.cancel_time,
        "kok_orders": kok_orders,
        "homeshopping_orders": homeshopping_orders
    }


async def get_user_orders(db: AsyncSession, user_id: int, limit: int = 20, offset: int = 0) -> list:
    """
    사용자별 주문 목록 조회 (공통 정보 + 서비스별 상세)
    """
    # 주문 기본 정보 조회
    result = await db.execute(
        select(Order)
        .where(Order.user_id == user_id)
        .order_by(Order.order_time.desc())
        .offset(offset)
        .limit(limit)
    )
    orders = result.scalars().all()
    
    order_list = []
    for order in orders:
        # 콕 주문 정보 조회
        kok_result = await db.execute(
            select(KokOrder).where(KokOrder.order_id == order.order_id)
        )
        kok_orders = kok_result.scalars().all()
        
        # 홈쇼핑 주문 정보 조회
        homeshopping_result = await db.execute(
            select(HomeShoppingOrder).where(HomeShoppingOrder.order_id == order.order_id)
        )
        homeshopping_orders = homeshopping_result.scalars().all()
        
        order_list.append({
            "order_id": order.order_id,
            "user_id": order.user_id,
            "order_time": order.order_time,
            "cancel_time": order.cancel_time,
            "kok_orders": kok_orders,
            "homeshopping_orders": homeshopping_orders
        })
    
    return order_list
