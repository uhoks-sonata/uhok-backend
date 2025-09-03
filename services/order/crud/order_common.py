"""
주문 관련 공통 상수와 함수들
CRUD 계층: 모든 DB 트랜잭션 처리 담당
순환 import 방지를 위해 별도 파일로 분리
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.database.mariadb_auth import get_maria_auth_db

from services.user.models.user_model import User
from services.order.models.order_model import StatusMaster

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

async def get_status_by_code(db: AsyncSession, status_code: str) -> StatusMaster:
    """
    상태 코드로 상태 정보 조회
    
    Args:
        db: 데이터베이스 세션
        status_code: 조회할 상태 코드
    
    Returns:
        StatusMaster: 상태 정보 객체 (없으면 None)
        
    Note:
        - CRUD 계층: DB 조회만 담당, 트랜잭션 변경 없음
        - StatusMaster 테이블에서 status_code로 조회
        - 주문 상태 변경 시 상태 정보 조회에 사용
    """
    result = await db.execute(
        select(StatusMaster).where(StatusMaster.status_code == status_code)
    )
    return result.scalars().first()

async def initialize_status_master(db: AsyncSession):
    """
    STATUS_MASTER 테이블에 기본 상태 코드들을 초기화
    
    Args:
        db: 데이터베이스 세션
    
    Returns:
        None
        
    Note:
        - CRUD 계층: DB 상태 변경 담당, 트랜잭션 단위 책임
        - STATUS_CODES 상수에 정의된 모든 상태 코드를 테이블에 추가
        - 기존 상태 코드가 있는 경우 중복 추가하지 않음
        - 시스템 초기화 시 사용
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
    
    Args:
        user_id: 검증할 사용자 ID
        db: 데이터베이스 세션 (사용되지 않음, AUTH_DB 사용)
    
    Returns:
        bool: 사용자가 존재하면 True, 없으면 False
        
    Note:
        - CRUD 계층: DB 조회만 담당, 트랜잭션 변경 없음
        - AUTH_DB.USERS 테이블에서 사용자 존재 여부 확인
        - 주문 생성 시 사용자 유효성 검증에 사용
        - 별도의 AUTH_DB 세션을 사용하여 인증 데이터베이스 접근
    """  
    # AUTH_DB에서 사용자 조회
    auth_db = get_maria_auth_db()
    async for auth_session in auth_db:
        result = await auth_session.execute(
            select(User).where(User.user_id == user_id)
        )
        user = result.scalars().first()
        return user is not None
    
    return False
