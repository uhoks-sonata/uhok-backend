"""Payment v1 polling flow CRUD functions."""

from __future__ import annotations

import asyncio
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import httpx
from dotenv import load_dotenv
from fastapi import BackgroundTasks, HTTPException
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from common.log_utils import send_user_log
from common.logger import get_logger
from services.order.models.order_base_model import StatusMaster
from services.order.models.homeshopping.hs_order_model import HomeShoppingOrderStatusHistory
from services.order.models.kok.kok_order_model import KokOrderStatusHistory
from services.order.schemas.payment_schema import PaymentConfirmV1Request, PaymentConfirmV1Response
from services.order.crud.common.order_access_management_crud import _ensure_order_access
from services.order.crud.common.order_cancel_management_crud import cancel_order
from services.order.crud.common.order_http_management_crud import _get_json, _post_json
from services.order.crud.common.order_payment_state_management_crud import (
    _mark_all_children_payment_completed,
    _mark_all_children_payment_requested,
)
from services.order.crud.common.order_price_management_crud import calculate_order_total_price

logger = get_logger("payment_crud")

load_dotenv()
PAYMENT_SERVER_URL = os.getenv("PAYMENT_SERVER_URL")

async def _verify_order_status_for_payment(
    db: AsyncSession,
    order_data: Dict[str, Any]
) -> None:
    """
    결제 생성 전 주문 상태 확인
    - kok_order와 hs_order의 상태가 ORDER_RECEIVED인지 확인
    - ORDER_RECEIVED가 아닌 경우 결제 생성 불가
    """   
    logger.info(f"결제 생성 전 주문 상태 확인 시작")
    
    # ORDER_RECEIVED 상태 ID 조회
    status_result = await db.execute(
        select(StatusMaster).where(StatusMaster.status_code == "ORDER_RECEIVED")
    )
    order_received_status = status_result.scalar_one_or_none()
    
    if not order_received_status:
        logger.error("ORDER_RECEIVED 상태를 찾을 수 없습니다.")
        raise HTTPException(status_code=500, detail="주문 상태 정보를 찾을 수 없습니다.")
    
    order_received_status_id = order_received_status.status_id
    logger.info(f"ORDER_RECEIVED 상태 ID: {order_received_status_id}")
    
    # kok_orders 상태 확인
    kok_orders = order_data.get("kok_orders", [])
    for kok_order in kok_orders:
        # 최신 상태 이력 조회
        status_history_result = await db.execute(
            select(KokOrderStatusHistory)
            .where(KokOrderStatusHistory.kok_order_id == kok_order.kok_order_id)
            .order_by(desc(KokOrderStatusHistory.changed_at))
            .limit(1)
        )
        latest_status = status_history_result.scalar_one_or_none()
        
        if not latest_status or latest_status.status_id != order_received_status_id:
            logger.error(f"콕 주문 상태가 ORDER_RECEIVED가 아닙니다: kok_order_id={kok_order.kok_order_id}, current_status_id={latest_status.status_id if latest_status else 'None'}")
            raise HTTPException(status_code=400, detail=f"주문 ID {kok_order.kok_order_id}의 상태가 결제 가능한 상태가 아닙니다.")
        
        logger.info(f"콕 주문 상태 확인 완료: kok_order_id={kok_order.kok_order_id}, status=ORDER_RECEIVED")
    
    # hs_orders 상태 확인
    hs_orders = order_data.get("homeshopping_orders", [])
    for hs_order in hs_orders:
        # 최신 상태 이력 조회
        status_history_result = await db.execute(
            select(HomeShoppingOrderStatusHistory)
            .where(HomeShoppingOrderStatusHistory.homeshopping_order_id == hs_order.homeshopping_order_id)
            .order_by(desc(HomeShoppingOrderStatusHistory.changed_at))
            .limit(1)
        )
        latest_status = status_history_result.scalar_one_or_none()
        
        if not latest_status or latest_status.status_id != order_received_status_id:
            logger.error(f"홈쇼핑 주문 상태가 ORDER_RECEIVED가 아닙니다: hs_order_id={hs_order.homeshopping_order_id}, current_status_id={latest_status.status_id if latest_status else 'None'}")
            raise HTTPException(status_code=400, detail=f"주문 ID {hs_order.homeshopping_order_id}의 상태가 결제 가능한 상태가 아닙니다.")
        
        logger.info(f"홈쇼핑 주문 상태 확인 완료: hs_order_id={hs_order.homeshopping_order_id}, status=ORDER_RECEIVED")
    
    logger.info(f"모든 주문 상태 확인 완료: ORDER_RECEIVED 상태로 결제 가능")
    
    # logger.info(f"모든 주문 상태 확인 완료: ORDER_RECEIVED 상태로 결제 가능")

# === [v1: Polling-based payment flow] =======================================

async def _poll_payment_status(
    payment_id: str,
    *,
    max_attempts: int = 30,
    initial_sleep: float = 5.0,
    step: float = 0.0,  # 5초 고정 간격으로 변경
    max_sleep: float = 5.0,  # 최대 대기 시간도 5초로 고정
) -> Tuple[str, Dict[str, Any]]:
    """
    외부 결제 상태를 폴링하는 비동기 함수
    - 5초 고정 간격으로 상태 확인
    - 반환: (최종상태 문자열, 상태 응답 JSON)
      * 최종상태: "PAYMENT_COMPLETED" | "PAYMENT_FAILED" | "TIMEOUT"
    """
    # logger.info(f"결제 상태 폴링 시작: payment_id={payment_id}, max_attempts={max_attempts}, interval=5초")
    sleep = initial_sleep
    last_payload: Dict[str, Any] = {}

    for attempt in range(max_attempts):
    # logger.info(f"결제 상태 확인 시도 {attempt + 1}/{max_attempts}: payment_id={payment_id}, sleep={sleep}초")
        
        try:
    # logger.info(f"결제 상태 확인 요청 시작: payment_id={payment_id}, url={PAYMENT_SERVER_URL}/payment-status/{payment_id}")
            resp = await _get_json(f"{PAYMENT_SERVER_URL}/payment-status/{payment_id}", timeout=15.0)
    # logger.info(f"결제 상태 응답: payment_id={payment_id}, status_code={resp.status_code}")
            
        except httpx.RequestError as e:
            logger.error(f"결제 상태 확인 실패 (RequestError): payment_id={payment_id}, attempt={attempt + 1}, error={str(e)}, error_type={type(e).__name__}")
            last_payload = {"error": str(e), "error_type": type(e).__name__}
            await asyncio.sleep(sleep)  # 고정 5초 대기
            continue

        except Exception as e:
            logger.error(f"결제 상태 확인 실패 (기타 오류): payment_id={payment_id}, attempt={attempt + 1}, error={str(e)}, error_type={type(e).__name__}")
            last_payload = {"error": str(e), "error_type": type(e).__name__}
            await asyncio.sleep(sleep)  # 고정 5초 대기
            continue

        if resp.status_code != 200:
            logger.warning(f"결제 상태 확인 실패: payment_id={payment_id}, attempt={attempt + 1}, status_code={resp.status_code}")
            last_payload = {"error": f"status_code={resp.status_code}", "text": resp.text[:300]}
            await asyncio.sleep(sleep)  # 고정 5초 대기
            continue

        data = resp.json()
        status_val = data.get("status", "PENDING")
        last_payload = data
    # logger.info(f"결제 상태 확인 결과: payment_id={payment_id}, status={status_val}, attempt={attempt + 1}")

        if status_val in ("PAYMENT_COMPLETED", "PAYMENT_FAILED"):
    # logger.info(f"결제 상태 최종 확인: payment_id={payment_id}, status={status_val}")
            return status_val, data

        await asyncio.sleep(sleep)  # 고정 5초 대기

    logger.error(f"결제 상태 확인 시간 초과: payment_id={payment_id}, max_attempts={max_attempts}")
    return "TIMEOUT", last_payload


async def confirm_payment_and_update_status_v1(
    *,
    db: AsyncSession,
    order_id: int,
    user_id: int,
    payment_data: PaymentConfirmV1Request,
    background_tasks: Optional[BackgroundTasks],
) -> PaymentConfirmV1Response:
    """
    결제 확인 v1 메인 로직 (CRUD 계층)
    1) 주문 확인/권한 확인
    2) 총액 계산
    3) 외부 결제 생성 호출 (idempotency key 포함 권장)
    4) payment_id로 상태 폴링
    5) 완료 시 하위 주문 일괄 상태 갱신 (트랜잭션)
    6) 백그라운드 로그 적재
    7) 응답 스키마 구성 후 반환
    """
    # logger.info(f"결제 확인 v1 시작: order_id={order_id}, user_id={user_id}")
    
    # (1) 접근 검증
    # logger.info(f"주문 접근 검증 시작: order_id={order_id}")
    order_data = await _ensure_order_access(db, order_id, user_id)
    # logger.info(f"주문 접근 검증 완료: order_id={order_id}, user_id={order_data['user_id']}")

    # (2) 총액 계산
    # logger.info(f"주문 총액 계산 시작: order_id={order_id}")
    total_order_price = await calculate_order_total_price(db, order_id)
    # logger.info(f"주문 총액 계산 완료: order_id={order_id}, total_price={total_order_price}")

    # (3) 결제 생성
    # logger.info(f"외부 결제 API 호출 시작: order_id={order_id}, url={PAYMENT_SERVER_URL}")
    pay_req = {
        "order_id": order_id,  # 숫자 그대로 사용
        "payment_amount": float(total_order_price),  # Decimal을 float로 변환하여 JSON 직렬화 가능하게 함
        "idempotency_key": f"order-{order_id}",  # 외부서버가 지원한다는 가정
        "method": getattr(payment_data, "method", "EXTERNAL_API"),
    }
    # logger.info(f"결제 요청 데이터: {pay_req}")
    
    try:
        create_resp = await _post_json(f"{PAYMENT_SERVER_URL}/pay", json=pay_req, timeout=20.0)
    # logger.info(f"외부 결제 API 응답: status_code={create_resp.status_code}, response={create_resp.text[:200]}")
    except httpx.RequestError as e:
        logger.error(f"외부 결제 API 연결 실패: order_id={order_id}, error={str(e)}")
        raise HTTPException(status_code=503, detail="외부 결제 서비스에 연결할 수 없습니다.")

    if create_resp.status_code != 200:
        logger.error(f"외부 결제 API 호출 실패: order_id={order_id}, status_code={create_resp.status_code}, response={create_resp.text}")
        raise HTTPException(status_code=400, detail=f"외부 결제 API 호출 실패: {create_resp.status_code}")

    create_payload = create_resp.json()
    payment_id: Optional[str] = create_payload.get("payment_id")
    # logger.info(f"결제 ID 수신: order_id={order_id}, payment_id={payment_id}")
    
    if not payment_id:
        logger.error(f"외부 결제 응답에 payment_id 없음: order_id={order_id}, response={create_payload}")
        raise HTTPException(status_code=502, detail="외부 결제 응답에 payment_id가 없습니다.")

    # (4) 결제 요청 상태로 변경
    # logger.info(f"주문 상태를 PAYMENT_REQUESTED로 변경 시작: order_id={order_id}")
    try:
        await _mark_all_children_payment_requested(
            db,
            kok_orders=order_data.get("kok_orders", []),
            hs_orders=order_data.get("homeshopping_orders", []),
            user_id=user_id,
        )
    # logger.info(f"주문 상태를 PAYMENT_REQUESTED로 변경 완료: order_id={order_id}")
    except Exception as e:
        logger.error(f"주문 상태 변경 실패: order_id={order_id}, error={str(e)}")
        # 상태 변경 실패 시에도 결제 진행은 계속 (로깅만 기록)
    
    # (5) 상태 폴링
    # logger.info(f"결제 상태 폴링 시작: order_id={order_id}, payment_id={payment_id}")
    final_status, status_payload = await _poll_payment_status(payment_id)
    # logger.info(f"결제 상태 폴링 완료: order_id={order_id}, final_status={final_status}")

    if final_status == "PAYMENT_FAILED":
        logger.error(f"결제 실패: order_id={order_id}, payment_id={payment_id}")
        # 결제 실패 시 주문 취소
        try:
            await cancel_order(db, order_id, "결제 실패")
    # logger.info(f"결제 실패로 인한 주문 취소 완료: order_id={order_id}")
        except Exception as e:
            logger.error(f"주문 취소 실패: order_id={order_id}, error={str(e)}")
        raise HTTPException(status_code=400, detail="결제가 실패했습니다.")
    
    if final_status == "TIMEOUT":
        logger.error(f"결제 상태 확인 시간 초과: order_id={order_id}, payment_id={payment_id}")
        # 결제 시간 초과 시 주문 취소
        try:
            await cancel_order(db, order_id, "결제 시간 초과")
    # logger.info(f"결제 시간 초과로 인한 주문 취소 완료: order_id={order_id}")
        except Exception as e:
            logger.error(f"주문 취소 실패: order_id={order_id}, error={str(e)}")
        raise HTTPException(status_code=408, detail="결제 상태 확인 시간 초과")

    # (6) 완료 → 하위 주문 상태 갱신
    # logger.info(f"하위 주문 상태 갱신 시작: order_id={order_id}")
    kok_orders = order_data.get("kok_orders", [])
    hs_orders = order_data.get("homeshopping_orders", [])
    # logger.info(f"하위 주문 정보: order_id={order_id}, kok_count={len(kok_orders)}, hs_count={len(hs_orders)}")
    
    await _mark_all_children_payment_completed(
        db,
        kok_orders=kok_orders,
        hs_orders=hs_orders,
        user_id=user_id,
    )
    # logger.info(f"하위 주문 상태 갱신 완료: order_id={order_id}")

    # (7) 로그 적재
    if background_tasks:
        background_tasks.add_task(
            send_user_log,
            user_id=user_id,
            event_type="order_payment_confirm_v1",
            event_data={
                "order_id": order_id,
                "external_payment_id": payment_id,
                "create_payload": create_payload,
                "final_status_payload": status_payload,
            },
        )
    # logger.info(f"백그라운드 로그 적재 예약: order_id={order_id}")

    # (8) 응답 구성
    # kok_order_ids와 hs_order_id 추출
    kok_order_ids = [kok_order.kok_order_id for kok_order in order_data.get("kok_orders", [])]
    hs_order_id = None
    if order_data.get("homeshopping_orders"):
        hs_order_id = order_data["homeshopping_orders"][0].homeshopping_order_id  # 홈쇼핑 주문은 단개
    
    response = PaymentConfirmV1Response(
        payment_id=payment_id,
        order_id=order_id,  # 숫자 그대로 사용
        kok_order_ids=kok_order_ids,
        hs_order_id=hs_order_id,
        status="PAYMENT_COMPLETED",
        payment_amount=total_order_price,
        method=create_payload.get("method", "EXTERNAL_API"),
        confirmed_at=datetime.now(),
        order_id_internal=order_id,
    )
    
    # logger.info(f"결제 확인 v1 완료: order_id={order_id}, payment_id={payment_id}")
    return response
