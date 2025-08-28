from __future__ import annotations
import os
import asyncio
import httpx
from fastapi import HTTPException, BackgroundTasks
from typing import Dict, Any, Optional, Tuple
from datetime import datetime
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession

from common.log_utils import send_user_log
from common.logger import get_logger

from services.order.schemas.payment_schema import PaymentConfirmV1Request, PaymentConfirmV1Response
from services.order.crud.order_crud import (
    _ensure_order_access, 
    calculate_order_total_price, 
    _mark_all_children_paid, 
    _post_json, 
    _get_json
)

logger = get_logger("payment_crud")

load_dotenv()
pay_api_base = os.getenv("PAY_API_BASE")

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
    logger.info(f"결제 확인 v1 시작: order_id={order_id}, user_id={user_id}")
    
    # (1) 접근 검증
    logger.info(f"주문 접근 검증 시작: order_id={order_id}")
    order_data = await _ensure_order_access(db, order_id, user_id)
    logger.info(f"주문 접근 검증 완료: order_id={order_id}, user_id={order_data['user_id']}")

    # (2) 총액 계산
    logger.info(f"주문 총액 계산 시작: order_id={order_id}")
    total_order_price = await calculate_order_total_price(db, order_id)
    logger.info(f"주문 총액 계산 완료: order_id={order_id}, total_price={total_order_price}")

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
        raise HTTPException(status_code=400, detail="결제가 실패했습니다.")
    if final_status == "TIMEOUT":
        logger.error(f"결제 상태 확인 시간 초과: order_id={order_id}, payment_id={payment_id}")
        raise HTTPException(status_code=408, detail="결제 상태 확인 시간 초과")

    # (5) 완료 → 하위 주문 상태 갱신
    logger.info(f"하위 주문 상태 갱신 시작: order_id={order_id}")
    kok_orders = order_data.get("kok_orders", [])
    hs_orders = order_data.get("homeshopping_orders", [])
    logger.info(f"하위 주문 정보: order_id={order_id}, kok_count={len(kok_orders)}, hs_count={len(hs_orders)}")
    
    await _mark_all_children_paid(
        db,
        kok_orders=kok_orders,
        hs_orders=hs_orders,
        user_id=user_id,
    )
    logger.info(f"하위 주문 상태 갱신 완료: order_id={order_id}")

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
# ===========================================================================

# === [v2: Webhook-based payment flow] =======================================
import hmac, hashlib, base64, secrets
from typing import Literal, Optional
from fastapi import Request

PAYMENT_SERVER_URL = os.getenv("PAYMENT_SERVER_URL")
PAYMENT_WEBHOOK_SECRET = os.getenv("PAYMENT_WEBHOOK_SECRET")

# 운영서버로 콜백 받을 때 서명을 검증
def verify_webhook_signature(body_bytes: bytes, signature_b64: str, secret: str) -> bool:
    mac = hmac.new(secret.encode("utf-8"), body_bytes, hashlib.sha256).digest()
    expected = base64.b64encode(mac).decode("ascii")
    # 타이밍 공격 방지 비교
    return hmac.compare_digest(expected, signature_b64)

async def confirm_payment_and_update_status_v2(
    db,
    homeshopping_order_id: int,
    user_id: int,
    request: Request,
) -> dict:
    """
    v2(웹훅) 결제 확인 요청 시작:
    - 주문 상태를 PAYMENT_REQUESTED 로 변경 (v1과 동일)
    - 결제서버에 '콜백 URL'을 포함해 결제요청 전송
    - 즉시 응답(PENDING) 반환, 실제 완료는 웹훅 수신 시 최종 반영
    """
    # 1) (예) 주문/결제 금액 조회 (기존 v1과 동일하게 필요한 정보 수집)
    # amount = await get_order_amount(db, homeshopping_order_id)  # 이미 있는 헬퍼 가정
    amount = 1000  # 예시

    # 2) 상태 → PAYMENT_REQUESTED (기존 v1과 동일)
    # await set_status_payment_requested(db, homeshopping_order_id, user_id)
    # await db.commit()

    # 트랜잭션 식별자/토큰 생성
    tx_id = f"tx_{homeshopping_order_id}_{secrets.token_urlsafe(8)}"
    token = secrets.token_urlsafe(32)  # 콜백 URL 보호용 토큰 (선택)

    # 3) 웹훅 콜백 URL 생성 (라우터에서 name="payment_webhook_handler_v2" 로 등록 가정)
    callback_url = str(
        request.url_for("payment_webhook_handler_v2", tx_id=tx_id)
    ) + f"?t={token}"

    # 4) 결제서버로 "콜백 URL"을 포함하여 결제요청
    payload = {
        "version": "v2",
        "tx_id": tx_id,
        "order_id": homeshopping_order_id,
        "user_id": user_id,
        "amount": amount,
        "callback_url": callback_url,
    }

    # 요청
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.post(
            f"{PAYMENT_SERVER_URL}/api/v2/payments",
            json=payload,
        )
        r.raise_for_status()
        init_result = r.json()

    # 5) 로컬에 tx_id, token 등을 저장(필요 시). 예: PAYMENT_TRANSACTIONS 테이블 or ORDERS 메타
    # await save_tx_metadata(db, homeshopping_order_id, tx_id, token)
    # await db.commit()

    return {
        "status": "PENDING",
        "tx_id": tx_id,
        "payment_server_ack": init_result,
    }

async def apply_payment_webhook_v2(
    db,
    tx_id: str,
    raw_body: bytes,
    signature_b64: str,
    event: Literal["payment.completed","payment.failed","payment.cancelled"],
) -> dict:
    """
    결제서버 → 운영서버 웹훅 수신 처리
    - HMAC 서명 검증
    - event에 따라 주문 상태 최종 업데이트 (PAYMENT_COMPLETED / FAILED 등)
    """
    # 1) 서명 검증
    if not verify_webhook_signature(raw_body, signature_b64, PAYMENT_WEBHOOK_SECRET):
        return {"ok": False, "reason": "invalid_signature"}

    # 2) 본문 파싱
    import json
    payload = json.loads(raw_body.decode("utf-8"))

    order_id = payload.get("order_id")
    payment_id = payload.get("payment_id")
    completed_at = payload.get("completed_at")
    failure_reason = payload.get("failure_reason")

    # 3) 상태 업데이트
    if event == "payment.completed":
        # await set_status_payment_completed(db, order_id, payment_id, completed_at)
        # await add_status_history(...)
        pass
    elif event in ("payment.failed", "payment.cancelled"):
        # await set_status_payment_failed(db, order_id, reason=failure_reason)
        # await add_status_history(...)
        pass

    # await db.commit()

    return {"ok": True, "order_id": order_id, "event": event}
# ===========================================================================
