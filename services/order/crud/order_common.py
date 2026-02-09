"""
주문 관련 공통 상수와 함수들
CRUD 계층: 모든 DB 트랜잭션 처리 담당
순환 import 방지를 위해 별도 파일로 분리
"""
from datetime import datetime, timedelta
from typing import Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from common.database.mariadb_auth import get_maria_auth_db

from services.order.models.order_base_model import StatusMaster

# 상태 정보 캐시 (메모리 캐시)
_status_cache: Dict[str, StatusMaster] = {}
_cache_expiry: Dict[str, datetime] = {}
CACHE_TTL = 300  # 5분 캐시 유지

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

async def get_status_by_code(db: AsyncSession, status_code: str) -> Optional[StatusMaster]:
    """
    상태 코드로 상태 정보 조회 (최적화: 캐싱 + Raw SQL 사용)
    
    Args:
        db: 데이터베이스 세션
        status_code: 조회할 상태 코드
    
    Returns:
        StatusMaster: 상태 정보 객체 (없으면 None)
        
    Note:
        - CRUD 계층: DB 조회만 담당, 트랜잭션 변경 없음
        - 메모리 캐싱을 사용하여 성능 최적화
        - Raw SQL을 사용하여 쿼리 성능 최적화
        - StatusMaster 테이블에서 status_code로 조회
        - 주문 상태 변경 시 상태 정보 조회에 사용
    """
    from sqlalchemy import text
    from common.logger import get_logger
    logger = get_logger("order_common")
    
    # 캐시 확인
    now = datetime.now()
    if (status_code in _status_cache and 
        status_code in _cache_expiry and 
        now < _cache_expiry[status_code]):
        return _status_cache[status_code]
    
    # 최적화된 쿼리: Raw SQL 사용
    sql_query = """
    SELECT 
        status_id,
        status_code,
        status_name
    FROM STATUS_MASTER
    WHERE status_code = :status_code
    LIMIT 1
    """
    
    try:
        result = await db.execute(text(sql_query), {"status_code": status_code})
        status_data = result.fetchone()
    except Exception as e:
        logger.error(f"상태 코드 조회 SQL 실행 실패: status_code={status_code}, error={str(e)}")
        return None
    
    if not status_data:
        return None
    
    # StatusMaster 객체 생성
    status = StatusMaster()
    status.status_id = status_data.status_id
    status.status_code = status_data.status_code
    status.status_name = status_data.status_name
    
    # 캐시에 저장
    _status_cache[status_code] = status
    _cache_expiry[status_code] = now + timedelta(seconds=CACHE_TTL)
    
    return status

async def initialize_status_master(db: AsyncSession):
    """
    STATUS_MASTER 테이블에 기본 상태 코드들을 초기화 (최적화: 배치 INSERT 사용)
    
    Args:
        db: 데이터베이스 세션
    
    Returns:
        None
        
    Note:
        - CRUD 계층: DB 상태 변경 담당, 트랜잭션 단위 책임
        - 배치 INSERT를 사용하여 성능 최적화
        - 기존 상태 코드가 있는 경우 중복 추가하지 않음
        - 시스템 초기화 시 사용
    """
    from sqlalchemy import text
    from common.logger import get_logger
    logger = get_logger("order_common")
    
    try:
        # 기존 상태 코드들 조회
        existing_codes_sql = """
        SELECT status_code FROM STATUS_MASTER
        """
        result = await db.execute(text(existing_codes_sql))
        existing_codes = {row.status_code for row in result.fetchall()}
        
        # 새로 추가할 상태 코드들 필터링
        new_status_codes = []
        for status_code, status_name in STATUS_CODES.items():
            if status_code not in existing_codes:
                new_status_codes.append((status_code, status_name))
        
        if not new_status_codes:
            logger.info("모든 상태 코드가 이미 존재합니다.")
            return
        
        # 배치 INSERT 실행
        insert_sql = """
        INSERT INTO STATUS_MASTER (status_code, status_name) 
        VALUES (:status_code, :status_name)
        """
        
        # 배치로 INSERT 실행
        await db.execute(text(insert_sql), [
            {"status_code": code, "status_name": name} 
            for code, name in new_status_codes
        ])
        
        await db.commit()
        logger.info(f"상태 마스터 초기화 완료: {len(new_status_codes)}개 상태 코드 추가")
        
    except Exception as e:
        logger.error(f"상태 마스터 초기화 실패: error={str(e)}")
        await db.rollback()
        raise

async def validate_user_exists(user_id: int, db: AsyncSession) -> bool:
    """
    사용자 ID가 유효한지 검증 (AUTH_DB.USERS 테이블 확인) (최적화: Raw SQL 사용)
    
    Args:
        user_id: 검증할 사용자 ID
        db: 데이터베이스 세션 (사용되지 않음, AUTH_DB 사용)
    
    Returns:
        bool: 사용자가 존재하면 True, 없으면 False
        
    Note:
        - CRUD 계층: DB 조회만 담당, 트랜잭션 변경 없음
        - Raw SQL을 사용하여 성능 최적화
        - AUTH_DB.USERS 테이블에서 사용자 존재 여부 확인
        - 주문 생성 시 사용자 유효성 검증에 사용
        - 별도의 AUTH_DB 세션을 사용하여 인증 데이터베이스 접근
    """  
    from sqlalchemy import text
    from common.logger import get_logger
    logger = get_logger("order_common")
    
    try:
        # AUTH_DB에서 사용자 조회
        auth_db = get_maria_auth_db()
        async for auth_session in auth_db:
            try:
                # 최적화된 쿼리: Raw SQL 사용
                sql_query = """
                SELECT 1 FROM USERS 
                WHERE user_id = :user_id 
                LIMIT 1
                """
                
                result = await auth_session.execute(text(sql_query), {"user_id": user_id})
                user_exists = result.fetchone() is not None
                return user_exists
            except Exception as e:
                logger.error(f"사용자 검증 SQL 실행 실패: user_id={user_id}, error={str(e)}")
                return False
        
        return False
    except Exception as e:
        logger.error(f"사용자 검증 실패: user_id={user_id}, error={str(e)}")
        return False


def clear_status_cache():
    """
    상태 정보 캐시 초기화
    
    Returns:
        None
        
    Note:
        - 메모리 캐시를 완전히 초기화
        - 시스템 재시작이나 상태 정보 변경 시 사용
    """
    global _status_cache, _cache_expiry
    _status_cache.clear()
    _cache_expiry.clear()


def get_cache_stats() -> dict:
    """
    캐시 통계 정보 조회
    
    Returns:
        dict: 캐시 통계 정보
        
    Note:
        - 현재 캐시된 상태 코드 개수와 만료 시간 정보 제공
        - 디버깅 및 모니터링 목적으로 사용
    """
    now = datetime.now()
    active_cache = {
        code: expiry.isoformat() 
        for code, expiry in _cache_expiry.items() 
        if now < expiry
    }
    
    return {
        "total_cached": len(_status_cache),
        "active_cached": len(active_cache),
        "cache_ttl_seconds": CACHE_TTL,
        "active_caches": active_cache
    }


async def preload_status_cache(db: AsyncSession):
    """
    모든 상태 코드를 미리 캐시에 로드
    
    Args:
        db: 데이터베이스 세션
    
    Returns:
        None
        
    Note:
        - 시스템 시작 시 모든 상태 코드를 미리 캐시에 로드
        - 첫 번째 조회 시 지연 시간을 방지
    """
    from sqlalchemy import text
    from common.logger import get_logger
    logger = get_logger("order_common")
    
    try:
        # 모든 상태 코드 조회
        sql_query = """
        SELECT 
            status_id,
            status_code,
            status_name
        FROM STATUS_MASTER
        """
        
        result = await db.execute(text(sql_query))
        status_data_list = result.fetchall()
        
        # 캐시에 저장
        now = datetime.now()
        for status_data in status_data_list:
            status = StatusMaster()
            status.status_id = status_data.status_id
            status.status_code = status_data.status_code
            status.status_name = status_data.status_name
            
            _status_cache[status_data.status_code] = status
            _cache_expiry[status_data.status_code] = now + timedelta(seconds=CACHE_TTL)
        
        logger.info(f"상태 코드 캐시 사전 로드 완료: {len(status_data_list)}개 상태 코드")
        
    except Exception as e:
        logger.error(f"상태 코드 캐시 사전 로드 실패: error={str(e)}")
