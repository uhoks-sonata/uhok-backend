from __future__ import annotations
import os
import asyncio
import httpx
import json
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

# === [v1: Polling-based payment flow] =======================================
PAYMENT_SERVER_URL = os.getenv("PAYMENT_SERVER_URL")

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
            logger.info(f"결제 상태 확인 요청 시작: payment_id={payment_id}, url={PAYMENT_SERVER_URL}/payment-status/{payment_id}")
            resp = await _get_json(f"{PAYMENT_SERVER_URL}/payment-status/{payment_id}", timeout=15.0)
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
    logger.info(f"외부 결제 API 호출 시작: order_id={order_id}, url={PAYMENT_SERVER_URL}")
    pay_req = {
        "order_id": order_id,  # 숫자 그대로 사용
        "payment_amount": total_order_price,
        "idempotency_key": f"order-{order_id}",  # 외부서버가 지원한다는 가정
        "method": getattr(payment_data, "method", "EXTERNAL_API"),
    }
    logger.info(f"결제 요청 데이터: {pay_req}")
    
    try:
        create_resp = await _post_json(f"{PAYMENT_SERVER_URL}/pay", json=pay_req, timeout=20.0)
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

SERVICE_AUTH_TOKEN = os.getenv("SERVICE_AUTH_TOKEN")
PAYMENT_SERVER_URL2 = os.getenv("PAYMENT_SERVER_URL2")
PAYMENT_WEBHOOK_SECRET = os.getenv("PAYMENT_WEBHOOK_SECRET")
# 운영서버로 콜백 받을 때 서명을 검증
def _verify_webhook_signature(body_bytes: bytes, signature_b64: str, secret: str) -> bool:
    mac = hmac.new(secret.encode("utf-8"), body_bytes, hashlib.sha256).digest()
    expected = base64.b64encode(mac).decode("ascii")
    # 타이밍 공격 방지 비교
    return hmac.compare_digest(expected, signature_b64)

async def confirm_payment_and_update_status_v2(
    *,
    db: AsyncSession,
    order_id: int,
    user_id: int,
    request: Request,
    background_tasks: Optional[BackgroundTasks] = None,
) -> dict:
    """
    v2(웹훅) 결제 확인 시작:
    - 접근검증/총액계산은 v1과 동일
    - 결제서버로 callback_url을 포함해 '시작 요청'만 보냄
    - 완료/실패 업데이트는 웹훅 수신 핸들러에서 처리
    """

    logger.info(f"[v2] 결제 확인 시작: order_id={order_id}, user_id={user_id}")

    # (1) 접근 검증
    order_data = await _ensure_order_access(db, order_id, user_id)

    # (2) 총액 계산
    total_order_price = await calculate_order_total_price(db, order_id)

    # (선택) 여기서 'PAYMENT_REQUESTED'로 상태 선반영을 원하면 이 지점에서 반영하세요.
    # 예: await _set_status_payment_requested(db, order_id, user_id); await db.commit()

    # (3) tx & callback_url 준비
    tx_id = f"tx_{order_id}_{secrets.token_urlsafe(8)}"
    cb_token = secrets.token_urlsafe(16)
    callback_url = str(request.url_for("payment_webhook_handler_v2", tx_id=tx_id)) + f"?t={cb_token}"

    payload = {
        "version": "v2",
        "tx_id": tx_id,
        "order_id": order_id,
        "user_id": user_id,
        "amount": total_order_price,
        "callback_url": callback_url,
    }
    headers = {}
    if SERVICE_AUTH_TOKEN:
        headers["Authorization"] = f"Bearer {SERVICE_AUTH_TOKEN}"

    # (4) 결제서버에 시작 요청
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(f"{PAYMENT_SERVER_URL2}/api/v2/payments", json=payload, headers=headers)
        r.raise_for_status()
        init_ack = r.json()
    except httpx.RequestError as e:
        logger.error(f"[v2] 결제서버 연결 실패: {e}")
        raise HTTPException(status_code=503, detail="외부 결제 서비스에 연결할 수 없습니다.")
    except Exception as e:
        logger.error(f"[v2] 결제서버 오류: {e}")
        raise HTTPException(status_code=400, detail="결제 시작 요청 실패")

    # (5) (옵션) tx 메타 저장이 필요하면 별도 테이블/메타 컬럼에 저장
    # await save_payment_tx(db, order_id, tx_id, cb_token); await db.commit()

    # (6) 로그
    if background_tasks:
        background_tasks.add_task(
            send_user_log,
            user_id=user_id,
            event_type="order_payment_confirm_v2_init",
            event_data={
                "order_id": order_id,
                "tx_id": tx_id,
                "callback_url": callback_url,
                "payment_init_ack": init_ack,
            },
        )

    return {
        "status": "PENDING",
        "tx_id": tx_id,
        "order_id": order_id,
        "payment_amount": total_order_price,
        "payment_server_ack": init_ack,
    }


async def apply_payment_webhook_v2(
    *,
    db: AsyncSession,
    tx_id: str,
    raw_body: bytes,
    signature_b64: str,
    event: str,  # "payment.completed" | "payment.failed" | "payment.cancelled"
    authorization: Optional[str] = None,  # (옵션) 서비스 토큰 검증용
) -> dict:
    """
    결제서버 → 운영서버 웹훅 수신
    - HMAC 서명 검증 필수
    - (옵션) Authorization: Bearer <SERVICE_AUTH_TOKEN> 검증
    - event별로 상태 업데이트 트리거
    """
    # (0) (옵션) 서비스 토큰 검증
    if SERVICE_AUTH_TOKEN:
        expected = f"Bearer {SERVICE_AUTH_TOKEN}"
        if authorization != expected:
            logger.warning("[v2] 서비스 토큰 불일치")
            return {"ok": False, "reason": "invalid_service_token"}

    # (1) 서명 검증
    if not _verify_webhook_signature(raw_body, signature_b64, PAYMENT_WEBHOOK_SECRET):
        logger.warning("[v2] 웹훅 시그니처 검증 실패")
        return {"ok": False, "reason": "invalid_signature"}

    # (2) 페이로드 파싱
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except Exception as e:
        logger.error(f"[v2] 웹훅 바디 파싱 실패: {e}")
        return {"ok": False, "reason": "invalid_body"}

    order_id = payload.get("order_id")
    payment_id = payload.get("payment_id")
    completed_at = payload.get("completed_at")
    failure_reason = payload.get("failure_reason")

    if not order_id:
        return {"ok": False, "reason": "missing_order_id"}

    # (3) event 처리
    if event == "payment.completed":
        # 주문 접근 확인 (로그/검증 용도)
        order_data = await _ensure_order_access(db, order_id, None)  # 내부 호출이면 user_id 검증 생략 가능
        kok_orders = order_data.get("kok_orders", [])
        hs_orders = order_data.get("homeshopping_orders", [])

        # 하위 주문 상태 일괄 갱신 (v1과 동일한 헬퍼)
        await _mark_all_children_paid(
            db,
            kok_orders=kok_orders,
            hs_orders=hs_orders,
            user_id=None,  # 시스템 처리면 None/0 등 정책에 맞게
        )
        await db.commit()

        # (선택) 상태이력/알림 로깅
        # background task가 라우터에 없다면 여기서 바로 적재하거나 생략
        logger.info(f"[v2] 결제완료 반영: order_id={order_id}, payment_id={payment_id}")

        return {"ok": True, "order_id": order_id, "event": event, "payment_id": payment_id}

    elif event in ("payment.failed", "payment.cancelled"):
        # 실패/취소 반영 로직이 따로 있다면 호출 (예: _mark_payment_failed)
        # await _mark_payment_failed(db, order_id, reason=failure_reason)
        await db.commit()
        logger.info(f"[v2] 결제실패/취소 반영: order_id={order_id}, reason={failure_reason}")
        return {"ok": True, "order_id": order_id, "event": event, "reason": failure_reason}

    else:
        logger.warning(f"[v2] 알 수 없는 이벤트: {event}")
        return {"ok": False, "reason": "unknown_event"}

# ===========================================================================
