"""Order cancel management CRUD functions."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.logger import get_logger
from services.order.models.order_base_model import Order, StatusMaster
from services.order.models.homeshopping.hs_order_model import (
    HomeShoppingOrder,
    HomeShoppingOrderStatusHistory,
)
from services.order.models.kok.kok_order_model import KokOrder, KokOrderStatusHistory

logger = get_logger("order_crud")

async def cancel_order(db: AsyncSession, order_id: int, reason: str):
    """
    주문을 취소하는 함수
    
    Args:
        db: 데이터베이스 세션
        order_id: 취소할 주문 ID
        reason: 취소 사유 (기본값: "결제 시간 초과")
    
    Returns:
        dict: 취소 결과 정보 (order_id, cancel_time, reason, cancelled_kok_orders, cancelled_hs_orders)
        
    Note:
        - CRUD 계층: DB 상태 변경 담당
        - 주문의 cancel_time을 현재 시간으로 설정
        - 모든 하위 주문(콕/홈쇼핑)의 상태를 CANCELLED로 변경
        - 상태 변경 이력을 StatusHistory 테이블에 기록
    """
    try:
        # 주문 조회
        try:
            order_result = await db.execute(
                select(Order)
                .where(Order.order_id == order_id)
            )
            order = order_result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"주문 취소 조회 SQL 실행 실패: order_id={order_id}, error={str(e)}")
            raise
        
        if not order:
            logger.warning(f"취소할 주문을 찾을 수 없음: order_id={order_id}")
            raise ValueError(f"주문을 찾을 수 없습니다: {order_id}")
        
        # 취소 시간 설정
        current_time = datetime.utcnow()
        
        # cancel_time 업데이트
        order.cancel_time = current_time
        
        # 하위 주문들 조회
        try:
            kok_orders_result = await db.execute(
                select(KokOrder)
                .where(KokOrder.order_id == order_id)
            )
            kok_orders = kok_orders_result.scalars().all()
        except Exception as e:
            logger.warning(f"콕 주문 취소 조회 실패: order_id={order_id}, error={str(e)}")
            kok_orders = []
        
        try:
            hs_orders_result = await db.execute(
                select(HomeShoppingOrder)
                .where(HomeShoppingOrder.order_id == order_id)
            )
            hs_orders = hs_orders_result.scalars().all()
        except Exception as e:
            logger.warning(f"홈쇼핑 주문 취소 조회 실패: order_id={order_id}, error={str(e)}")
            hs_orders = []
        
        # 콕 주문 상태를 CANCELLED로 업데이트
        for kok_order in kok_orders:
            # 상태 히스토리에 CANCELLED 기록 추가
            new_status_history = KokOrderStatusHistory(
                kok_order_id=kok_order.kok_order_id,
                status_id=await _get_status_id_by_code(db, "CANCELLED"),
                changed_at=current_time,
                changed_by=1  # 시스템 자동 취소
            )
            db.add(new_status_history)
        
        # 홈쇼핑 주문 상태를 CANCELLED로 업데이트
        for hs_order in hs_orders:
            # 상태 히스토리에 CANCELLED 기록 추가
            new_status_history = HomeShoppingOrderStatusHistory(
                homeshopping_order_id=hs_order.homeshopping_order_id,
                status_id=await _get_status_id_by_code(db, "CANCELLED"),
                changed_at=current_time,
                changed_by=1  # 시스템 자동 취소
            )
            db.add(new_status_history)
        
        await db.commit()
        
    # logger.info(f"주문 취소 완료: order_id={order_id}, cancel_time={current_time}, reason={reason}")
        
        return {
            "order_id": order_id,
            "cancel_time": current_time,
            "reason": reason,
            "cancelled_kok_orders": len(kok_orders),
            "cancelled_hs_orders": len(hs_orders)
        }
        
    except Exception as e:
        logger.error(f"주문 취소 실패: order_id={order_id}, error={str(e)}")
        raise

async def _get_status_id_by_code(db: AsyncSession, status_code: str) -> int:
    """
    상태 코드로 status_id를 조회하는 헬퍼 함수
    
    Args:
        db: 데이터베이스 세션
        status_code: 조회할 상태 코드 (예: "CANCELLED", "PAYMENT_COMPLETED")
    
    Returns:
        int: 해당 상태 코드의 status_id
        
    Raises:
        ValueError: 상태 코드를 찾을 수 없는 경우
        
    Note:
        - StatusMaster 테이블에서 status_code로 status_id 조회
        - 주문 취소 시 CANCELLED 상태 ID 조회에 사용
    """
    try:
        status_result = await db.execute(
            select(StatusMaster.status_id)
            .where(StatusMaster.status_code == status_code)
        )
        status_id = status_result.scalar_one_or_none()
    except Exception as e:
        logger.error(f"상태 코드 ID 조회 SQL 실행 실패: status_code={status_code}, error={str(e)}")
        raise
    
    if not status_id:
        logger.warning(f"상태 코드를 찾을 수 없음: status_code={status_code}")
        raise ValueError(f"상태 코드를 찾을 수 없습니다: {status_code}")
    return status_id

