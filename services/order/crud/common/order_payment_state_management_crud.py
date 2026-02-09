"""Order payment-state management CRUD functions."""

from __future__ import annotations

from typing import Any, List

from sqlalchemy.ext.asyncio import AsyncSession

from common.logger import get_logger
from services.order.crud.kok.kok_order_status_crud import update_kok_order_status
from services.order.crud.homeshopping.hs_order_status_crud import update_hs_order_status

logger = get_logger("order_crud")

async def _mark_all_children_payment_requested(
    db: AsyncSession,
    *,
    kok_orders: List[Any],
    hs_orders: List[Any],
    user_id: int,
) -> None:
    """
    하위 주문(콕/홈쇼핑)을 PAYMENT_REQUESTED로 일괄 갱신
    
    Args:
        db: 데이터베이스 세션
        kok_orders: 콕 주문 목록
        hs_orders: 홈쇼핑 주문 목록
        user_id: 상태 변경을 수행하는 사용자 ID
    
    Returns:
        None
        
    Note:
        - CRUD 계층: DB 상태 변경 담당, 트랜잭션 단위 책임
        - 기존 트랜잭션 사용 (새로운 트랜잭션 시작하지 않음)
        - 실패 시 상위에서 롤백 처리
        - 모든 하위 주문의 상태를 PAYMENT_REQUESTED로 변경
    """
    # logger.info(f"하위 주문 상태를 PAYMENT_REQUESTED로 갱신 시작: kok_count={len(kok_orders)}, hs_count={len(hs_orders)}")
    
    # 콕 주문 상태 갱신
    for k in kok_orders:
        try:
            await update_kok_order_status(
                db=db,
                kok_order_id=k.kok_order_id,
                new_status_code="PAYMENT_REQUESTED",
                changed_by=user_id,
            )
    # logger.info(f"콕 주문 상태를 PAYMENT_REQUESTED로 갱신 완료: kok_order_id={k.kok_order_id}")
        except Exception as e:
            logger.error(f"콕 주문 상태 갱신 실패: kok_order_id={k.kok_order_id}, error={str(e)}")
            raise
    
    # 홈쇼핑 주문 상태 갱신
    for h in hs_orders:
        try:
            await update_hs_order_status(
                db=db,
                homeshopping_order_id=h.homeshopping_order_id,
                new_status_code="PAYMENT_REQUESTED",
                changed_by=user_id,
            )
    # logger.info(f"홈쇼핑 주문 상태를 PAYMENT_REQUESTED로 갱신 완료: hs_order_id={h.homeshopping_order_id}")
        except Exception as e:
            logger.error(f"홈쇼핑 주문 상태 갱신 실패: homeshopping_order_id={h.homeshopping_order_id}, error={str(e)}")
            raise
    
    # logger.info(f"모든 하위 주문 상태를 PAYMENT_REQUESTED로 갱신 완료")


async def _mark_all_children_payment_completed(
    db: AsyncSession,
    *,
    kok_orders: List[Any],
    hs_orders: List[Any],
    user_id: int,
) -> None:
    """
    하위 주문(콕/홈쇼핑)을 PAYMENT_COMPLETED로 일괄 갱신
    
    Args:
        db: 데이터베이스 세션
        kok_orders: 콕 주문 목록
        hs_orders: 홈쇼핑 주문 목록
        user_id: 상태 변경을 수행하는 사용자 ID
    
    Returns:
        None
        
    Note:
        - CRUD 계층: DB 상태 변경 담당, 트랜잭션 단위 책임
        - 기존 트랜잭션 사용 (새로운 트랜잭션 시작하지 않음)
        - 실패 시 상위에서 롤백 처리
        - 모든 하위 주문의 상태를 PAYMENT_COMPLETED로 변경
    """
    # logger.info(f"하위 주문 상태를 PAYMENT_COMPLETED로 갱신 시작: kok_count={len(kok_orders)}, hs_count={len(hs_orders)}")
    
    # 콕 주문 상태 갱신
    for k in kok_orders:
        try:
            await update_kok_order_status(
                db=db,
                kok_order_id=k.kok_order_id,
                new_status_code="PAYMENT_COMPLETED",
                changed_by=user_id,
            )
    # logger.info(f"콕 주문 상태를 PAYMENT_COMPLETED로 갱신 완료: kok_order_id={k.kok_order_id}")
        except Exception as e:
            logger.error(f"콕 주문 상태 갱신 실패: kok_order_id={k.kok_order_id}, error={str(e)}")
            raise
    
    # 홈쇼핑 주문 상태 갱신
    for h in hs_orders:
        try:
            await update_hs_order_status(
                db=db,
                homeshopping_order_id=h.homeshopping_order_id,
                new_status_code="PAYMENT_COMPLETED",
                changed_by=user_id,
            )
    # logger.info(f"홈쇼핑 주문 상태를 PAYMENT_COMPLETED로 갱신 완료: hs_order_id={h.homeshopping_order_id}")
        except Exception as e:
            logger.error(f"홈쇼핑 주문 상태 갱신 실패: homeshopping_order_id={h.homeshopping_order_id}, error={str(e)}")
            raise
    
    # logger.info(f"모든 하위 주문 상태를 PAYMENT_COMPLETED로 갱신 완료")


