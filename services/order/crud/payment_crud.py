"""
주문 결제 관련 CRUD 함수들
CRUD 계층: 모든 DB 트랜잭션 처리 담당
"""
from __future__ import annotations
import os
from typing import Dict, Any, Optional, Tuple
from datetime import datetime
from dotenv import load_dotenv

import asyncio
import httpx
from fastapi import HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from services.order.schemas.payment_schema import PaymentConfirmV1Request, PaymentConfirmV1Response
from services.order.crud.order_crud import _ensure_order_access, calculate_order_total_price, _post_json, _get_json, cancel_order
from services.order.crud.kok_order_crud import update_kok_order_status
from services.order.crud.hs_order_crud import update_hs_order_status

from common.logger import get_logger
from common.log_utils import send_user_log

load_dotenv()
pay_api_base = os.getenv("PAY_API_BASE")

logger = get_logger("payment_crud")

async def _poll_payment_status(
    payment_id: str,
    *,
    max_attempts: int = 5,  # 최대 시도 횟수
    initial_sleep: float = 5.0,
    step: float = 0.0,  # 5초 고정 간격으로 변경
    max_sleep: float = 5.0,  # 최대 대기 시간도 5초로 고정
) -> Tuple[str, Dict[str, Any]]:
    """
    외부 결제 상태를 폴링하는 비동기 함수
    CRUD 계층: 외부 API 호출만 담당, DB 트랜잭션 변경 없음
    - 5초 고정 간격으로 상태 확인
    - 반환: (최종상태 문자열, 상태 응답 JSON)
      * 최종상태: "PAYMENT_COMPLETED" | "PAYMENT_FAILED" | "TIMEOUT"
    """
    logger.info(f"결제 상태 폴링 시작: payment_id={payment_id}, max_attempts={max_attempts}, interval=5초")
    sleep = initial_sleep
    last_payload: Dict[str, Any] = {}

    for attempt in range(max_attempts):
        logger.info(f"결제 상태 확인 시도 {attempt + 1}/{max_attempts}: payment_id={payment_id}, sleep={sleep}초")
        
        try:
            logger.info(f"결제 상태 확인 요청 시작: payment_id={payment_id}, url={pay_api_base}/payment-status/{payment_id}")
            resp = await _get_json(f"{pay_api_base}/payment-status/{payment_id}", timeout=15.0)
            logger.info(f"결제 상태 응답: payment_id={payment_id}, status_code={resp.status_code}")
            
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
        logger.info(f"결제 상태 확인 결과: payment_id={payment_id}, status={status_val}, attempt={attempt + 1}")

        if status_val in ("PAYMENT_COMPLETED", "PAYMENT_FAILED"):
            logger.info(f"결제 상태 최종 확인: payment_id={payment_id}, status={status_val}")
            return status_val, data

        await asyncio.sleep(sleep)  # 고정 5초 대기

    logger.error(f"결제 상태 확인 시간 초과: payment_id={payment_id}, max_attempts={max_attempts}")
    return "TIMEOUT", last_payload

async def _update_kok_order_to_payment_requested(db: AsyncSession, kok_order_id: int, user_id: int):
    """
    콕 주문을 PAYMENT_REQUESTED 상태로 업데이트
    CRUD 계층: DB 상태 변경 담당
    """
    try:
        await update_kok_order_status(
            db=db,
            kok_order_id=kok_order_id,
            new_status_code="PAYMENT_REQUESTED",
            changed_by=user_id
        )
        logger.info(f"콕 주문 결제 요청 상태 업데이트 완료: kok_order_id={kok_order_id}")
    except Exception as e:
        logger.error(f"콕 주문 결제 요청 상태 업데이트 실패: kok_order_id={kok_order_id}, error={str(e)}")
        raise

async def _update_hs_order_to_payment_requested(db: AsyncSession, homeshopping_order_id: int, user_id: int):
    """
    홈쇼핑 주문을 PAYMENT_REQUESTED 상태로 업데이트
    CRUD 계층: DB 상태 변경 담당
    """
    try:
        await update_hs_order_status(
            db=db,
            homeshopping_order_id=homeshopping_order_id,
            new_status_code="PAYMENT_REQUESTED",
            changed_by=user_id
        )
        logger.info(f"홈쇼핑 주문 결제 요청 상태 업데이트 완료: homeshopping_order_id={homeshopping_order_id}")
    except Exception as e:
        logger.error(f"홈쇼핑 주문 결제 요청 상태 업데이트 실패: homeshopping_order_id={homeshopping_order_id}, error={str(e)}")
        raise


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
    CRUD 계층: DB 트랜잭션 처리 담당
    1) 주문 확인/권한 확인
    2) 총액 계산
    3) 외부 결제 생성 호출 (idempotency key 포함 권장)
    4) payment_id로 상태 폴링
    5) 완료 시 하위 주문 일괄 상태 갱신 (트랜잭션)
    6) 백그라운드 로그 적재
    7) 응답 스키마 구성 후 반환
    """
    logger.info(f"결제 확인 v1 시작: order_id={order_id}, user_id={user_id}")
    
    # (1) 접근 검증
    logger.info(f"주문 접근 검증 시작: order_id={order_id}")
    order_data = await _ensure_order_access(db, order_id, user_id)
    logger.info(f"주문 접근 검증 완료: order_id={order_id}, user_id={order_data['user_id']}")

    # (2) 총액 계산
    logger.info(f"주문 총액 계산 시작: order_id={order_id}")
    total_order_price = await calculate_order_total_price(db, order_id)
    logger.info(f"주문 총액 계산 완료: order_id={order_id}, total_price={total_order_price}")

    # (2-1) 결제 요청 상태로 업데이트
    logger.info(f"결제 요청 상태 업데이트 시작: order_id={order_id}")
    kok_orders = order_data.get("kok_orders", [])
    hs_orders = order_data.get("homeshopping_orders", [])
    
    # 콕 주문들을 PAYMENT_REQUESTED 상태로 업데이트
    for kok_order in kok_orders:
        await _update_kok_order_to_payment_requested(db, kok_order.kok_order_id, user_id)
    
    # 홈쇼핑 주문들을 PAYMENT_REQUESTED 상태로 업데이트
    for hs_order in hs_orders:
        await _update_hs_order_to_payment_requested(db, hs_order.homeshopping_order_id, user_id)
    
    # 상태 변경사항 커밋
    await db.commit()
    logger.info(f"결제 요청 상태 업데이트 완료: order_id={order_id}, kok_count={len(kok_orders)}, hs_count={len(hs_orders)}")

    # (3) 결제 생성
    logger.info(f"외부 결제 API 호출 시작: order_id={order_id}, pay_api_base={pay_api_base}")
    pay_req = {
        "order_id": order_id,  # 숫자 그대로 사용
        "payment_amount": total_order_price,
        "idempotency_key": f"order-{order_id}",  # 외부서버가 지원한다는 가정
        "method": getattr(payment_data, "method", "EXTERNAL_API"),
    }
    logger.info(f"결제 요청 데이터: {pay_req}")
    
    try:
        create_resp = await _post_json(f"{pay_api_base}/pay", json=pay_req, timeout=20.0)
        logger.info(f"외부 결제 API 응답: status_code={create_resp.status_code}, response={create_resp.text[:200]}")
    except httpx.RequestError as e:
        logger.error(f"외부 결제 API 연결 실패: order_id={order_id}, error={str(e)}")
        raise HTTPException(status_code=503, detail="외부 결제 서비스에 연결할 수 없습니다.")

    if create_resp.status_code != 200:
        logger.error(f"외부 결제 API 호출 실패: order_id={order_id}, status_code={create_resp.status_code}, response={create_resp.text}")
        raise HTTPException(status_code=400, detail=f"외부 결제 API 호출 실패: {create_resp.status_code}")

    create_payload = create_resp.json()
    payment_id: Optional[str] = create_payload.get("payment_id")
    logger.info(f"결제 ID 수신: order_id={order_id}, payment_id={payment_id}")
    
    if not payment_id:
        logger.error(f"외부 결제 응답에 payment_id 없음: order_id={order_id}, response={create_payload}")
        raise HTTPException(status_code=502, detail="외부 결제 응답에 payment_id가 없습니다.")

    # (4) 상태 폴링
    logger.info(f"결제 상태 폴링 시작: order_id={order_id}, payment_id={payment_id}")
    final_status, status_payload = await _poll_payment_status(payment_id)
    logger.info(f"결제 상태 폴링 완료: order_id={order_id}, final_status={final_status}")

    if final_status == "PAYMENT_FAILED":
        logger.error(f"결제 실패: order_id={order_id}, payment_id={payment_id}")
        # 결제 실패 시 주문 취소 처리
        try:
            await cancel_order(db, order_id, "결제 실패로 인한 자동 취소")
            logger.info(f"결제 실패로 주문 취소 완료: order_id={order_id}")
        except Exception as e:
            logger.error(f"주문 취소 처리 실패: order_id={order_id}, error={str(e)}")
        
        raise HTTPException(status_code=400, detail="결제가 실패하여 주문이 취소되었습니다.")
        
    if final_status == "TIMEOUT":
        logger.error(f"결제 상태 확인 시간 초과: order_id={order_id}, payment_id={payment_id}")
        # 결제 시간 초과 시 주문 취소 처리
        try:
            await cancel_order(db, order_id, "결제 상태 확인 시간 초과")
            logger.info(f"결제 시간 초과로 주문 취소 완료: order_id={order_id}")
        except Exception as e:
            logger.error(f"주문 취소 처리 실패: order_id={order_id}, error={str(e)}")
        
        raise HTTPException(status_code=408, detail="결제 상태 확인 시간 초과로 주문이 취소되었습니다.")

    # (5) 완료 → 하위 주문 상태 갱신 (PAYMENT_COMPLETED)
    logger.info(f"하위 주문 상태 갱신 시작: order_id={order_id}")
    kok_orders = order_data.get("kok_orders", [])
    hs_orders = order_data.get("homeshopping_orders", [])
    logger.info(f"하위 주문 정보: order_id={order_id}, kok_count={len(kok_orders)}, hs_count={len(hs_orders)}")
    
    # 결제 완료 상태로 업데이트
    for kok_order in kok_orders:
        await update_kok_order_status(
            db=db,
            kok_order_id=kok_order.kok_order_id,
            new_status_code="PAYMENT_COMPLETED",
            changed_by=user_id
        )
    for hs_order in hs_orders:
        await update_hs_order_status(
            db=db,
            homeshopping_order_id=hs_order.homeshopping_order_id,
            new_status_code="PAYMENT_COMPLETED",
            changed_by=user_id
        )

    logger.info(f"하위 주문 상태 갱신 완료: order_id={order_id}")

    # 하위 주문 상태 갱신 후 DB에 반영
    await db.commit()
    logger.info(f"하위 주문 상태 갱신 완료 및 DB 반영: order_id={order_id}")

    # (6) 로그 적재
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
        logger.info(f"백그라운드 로그 적재 예약: order_id={order_id}")

    # (7) 응답 구성
    response = PaymentConfirmV1Response(
        payment_id=payment_id,
        order_id=order_id,  # 숫자 그대로 사용
        status="PAYMENT_COMPLETED",
        payment_amount=total_order_price,
        method=create_payload.get("method", "EXTERNAL_API"),
        confirmed_at=datetime.now(),
        order_id_internal=order_id,
    )
    
    logger.info(f"결제 확인 v1 완료: order_id={order_id}, payment_id={payment_id}")
    return response
