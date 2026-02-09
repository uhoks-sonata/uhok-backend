"""Payment v2 webhook flow CRUD functions."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import httpx
from dotenv import load_dotenv
from fastapi import BackgroundTasks, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from common.config import get_settings
from common.log_utils import send_user_log
from common.logger import get_logger
from services.order.schemas.payment_schema import PaymentConfirmV2Response
from services.order.crud.common.order_access_management_crud import _ensure_order_access
from services.order.crud.common.order_cancel_management_crud import cancel_order
from services.order.crud.common.order_payment_state_management_crud import (
    _mark_all_children_payment_completed,
    _mark_all_children_payment_requested,
)
from services.order.crud.common.order_price_management_crud import calculate_order_total_price
from services.order.crud.payment_v1_crud import _verify_order_status_for_payment

logger = get_logger("payment_crud")

load_dotenv()

SERVICE_AUTH_TOKEN = os.getenv("SERVICE_AUTH_TOKEN")
PAYMENT_SERVER_URL2 = os.getenv("PAYMENT_SERVER_URL2")
PAYMENT_WEBHOOK_SECRET = os.getenv("PAYMENT_WEBHOOK_SECRET")

class WaiterRegistry:
    """
    키(예: tx_id)별로 비동기 구독자를 관리한다.
    - subscribe(key): Future를 만들고 대기열에 등록, 완료 시 결과를 받음
    - notify(key, payload): 해당 key의 모든 구독자 Future를 set_result로 깨움 (브로드캐스트)
    - resolve(key, payload): notify와 동일하나, '최종 상태'를 저장해 이후 구독자도 즉시 받게 함 (옵션)
    - cleanup(): 오래된 대기자 청소
    """

    def __init__(self) -> None:
        # waiters[key] = [(future, created_at_ts), ...]
        self.waiters: Dict[str, List[Tuple[asyncio.Future, float]]] = {}
        # resolved[key] = payload (이미 해결된 최종 결과; 이후 구독 시 바로 리턴)
        self.resolved: Dict[str, Any] = {}
        # 락: 동시 접근 안전
        self._lock = asyncio.Lock()

    async def subscribe(self, key: str, check_resolved_first: bool = True) -> asyncio.Future:
        async with self._lock:
            if check_resolved_first and key in self.resolved:
                # 이미 최종 결과가 있다면 즉시 완료된 Future를 반환
                fut = asyncio.get_running_loop().create_future()
                fut.set_result(self.resolved[key])
                return fut

            fut: asyncio.Future = asyncio.get_running_loop().create_future()
            self.waiters.setdefault(key, []).append((fut, time.time()))
            return fut

    async def notify(self, key: str, payload: Any) -> int:
        """
        현재 대기 중인 구독자들을 모두 깨움. (최종 상태 저장은 하지 않음)
        반환값: 깨운 구독자 수
        """
        async with self._lock:
            entries = self.waiters.pop(key, [])
        for fut, _ in entries:
            if not fut.done():
                fut.set_result(payload)
        return len(entries)

    async def resolve(self, key: str, payload: Any) -> int:
        """
        최종 상태를 저장(resolved)하고 현재 대기자도 모두 깨움.
        이후 새 구독자는 subscribe 즉시 결과를 받는다.
        """
        async with self._lock:
            self.resolved[key] = payload
            entries = self.waiters.pop(key, [])
        for fut, _ in entries:
            if not fut.done():
                fut.set_result(payload)
        return len(entries)

    async def cleanup(self, max_age_sec: float = 120.0) -> None:
        """
        오래된 미해결 대기자 정리 (예: 네트워크 끊김으로 타임아웃 콜백이 못 탄 경우).
        """
        now = time.time()
        async with self._lock:
            for key, entries in list(self.waiters.items()):
                alive: List[Tuple[asyncio.Future, float]] = []
                for fut, ts in entries:
                    if (now - ts) > max_age_sec:
                        if not fut.done():
                            fut.set_exception(asyncio.TimeoutError())
                    else:
                        alive.append((fut, ts))
                if alive:
                    self.waiters[key] = alive
                else:
                    self.waiters.pop(key, None)

# 전역 웹훅 대기자 레지스트리
webhook_waiters = WaiterRegistry()

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
    timeout_sec: int = 60,  # 웹훅 대기 타임아웃 (초) - 30초에서 60초로 증가
) -> dict:
    """
    v2(웹훅) 결제 확인 시작:
    - 접근검증/총액계산은 v1과 동일
    - 결제서버로 callback_url을 포함해 '시작 요청'만 보냄
    - 웹훅 결과를 기다렸다가 최종 응답 반환
    - 완료/실패 업데이트는 웹훅 수신 핸들러에서 처리
    """

    # logger.info(f"[v2] 결제 확인 시작: order_id={order_id}, user_id={user_id}")

    # (1) 접근 검증
    order_data = await _ensure_order_access(db, order_id, user_id)

    # (1-1) 주문 상태 확인 (ORDER_RECEIVED 상태만 결제 가능)
    # logger.info(f"[v2] 주문 상태 확인 시작: order_id={order_id}")
    await _verify_order_status_for_payment(db, order_data)
    # logger.info(f"[v2] 주문 상태 확인 완료: order_id={order_id}")

    # (2) 총액 계산
    total_order_price = await calculate_order_total_price(db, order_id)

    # (3) tx & callback_url 준비
    tx_id = f"tx_{order_id}_{secrets.token_urlsafe(8)}"
    cb_token = secrets.token_urlsafe(16)
    
    # 절대 URL 생성 (payment-server에서 접근 가능하도록)
    settings = get_settings()
    base_url = settings.webhook_base_url.rstrip('/')
    callback_url = f"{base_url}/api/orders/payment/webhook/v2/{tx_id}?t={cb_token}"
    
    # 디버깅을 위한 로그
    logger.info(f"[v2] 웹훅 URL 생성: base_url={base_url}, tx_id={tx_id}, callback_url={callback_url}")

    payload = {
        "version": "v2",
        "tx_id": tx_id,
        "order_id": order_id,
        "user_id": user_id,
        "amount": float(total_order_price),  # Decimal을 float로 변환하여 JSON 직렬화 가능하게 함
        "callback_url": callback_url,
    }
    headers = {}
    if SERVICE_AUTH_TOKEN:
        headers["Authorization"] = f"Bearer {SERVICE_AUTH_TOKEN}"

    # (4) 결제 요청 상태로 변경
    # logger.info(f"[v2] 주문 상태를 PAYMENT_REQUESTED로 변경 시작: order_id={order_id}")
    try:
        await _mark_all_children_payment_requested(
            db,
            kok_orders=order_data.get("kok_orders", []),
            hs_orders=order_data.get("homeshopping_orders", []),
            user_id=user_id,
        )
    # logger.info(f"[v2] 주문 상태를 PAYMENT_REQUESTED로 변경 완료: order_id={order_id}")
    except Exception as e:
        logger.error(f"[v2] 주문 상태 변경 실패: order_id={order_id}, error={str(e)}")
        # 상태 변경 실패 시에도 결제 진행은 계속 (로깅만 기록)

    # (5) 결제서버에 시작 요청
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(f"{PAYMENT_SERVER_URL2}/api/v2/payments", json=payload, headers=headers)
        r.raise_for_status()
        init_ack = r.json()
    # logger.info(f"[v2] 결제서버 시작 요청 성공: order_id={order_id}, tx_id={tx_id}")
    except httpx.RequestError as e:
        logger.error(f"[v2] 결제서버 연결 실패: {e}")
        raise HTTPException(status_code=503, detail="외부 결제 서비스에 연결할 수 없습니다.")
    except Exception as e:
        logger.error(f"[v2] 결제서버 오류: {e}")
        raise HTTPException(status_code=400, detail="결제 시작 요청 실패")

    # (6) 웹훅 결과 대기
    # logger.info(f"[v2] 웹훅 결과 대기 시작: order_id={order_id}, tx_id={tx_id}, timeout={timeout_sec}초")
    
    try:
        # 웹훅 결과를 기다림
        webhook_future = await webhook_waiters.subscribe(tx_id, check_resolved_first=True)
        webhook_result = await asyncio.wait_for(webhook_future, timeout=timeout_sec)
        
    # logger.info(f"[v2] 웹훅 결과 수신: order_id={order_id}, tx_id={tx_id}, result={webhook_result}")
        
        # 웹훅 결과에 따라 최종 응답 구성
        if webhook_result.get("event") == "payment.completed":
            # 결제 성공
            final_status = "PAYMENT_COMPLETED"
            payment_id = webhook_result.get("payment_id", f"completed_{tx_id}")
        elif webhook_result.get("event") in ("payment.failed", "payment.cancelled"):
            # 결제 실패/취소
            final_status = "PAYMENT_FAILED"
            payment_id = webhook_result.get("payment_id", f"failed_{tx_id}")
            failure_reason = webhook_result.get("reason", "결제 실패")
            logger.error(f"[v2] 결제 실패: order_id={order_id}, reason={failure_reason}")
            raise HTTPException(status_code=400, detail=f"결제가 실패했습니다: {failure_reason}")
        else:
            # 알 수 없는 이벤트
            logger.error(f"[v2] 알 수 없는 웹훅 이벤트: order_id={order_id}, event={webhook_result.get('event')}")
            raise HTTPException(status_code=500, detail="알 수 없는 결제 결과입니다.")
            
    except asyncio.TimeoutError:
        logger.error(f"[v2] 웹훅 대기 시간 초과: order_id={order_id}, tx_id={tx_id}, timeout={timeout_sec}초")
        
        # 웹훅 대기자 정리
        try:
            await webhook_waiters.cleanup(max_age_sec=timeout_sec)
        except Exception as e:
            logger.warning(f"[v2] 웹훅 대기자 정리 실패: {e}")
        
        # 타임아웃 시 주문 취소
        try:
            await cancel_order(db, order_id, "결제 시간 초과")
            logger.info(f"[v2] 결제 시간 초과로 인한 주문 취소 완료: order_id={order_id}")
        except Exception as e:
            logger.error(f"[v2] 주문 취소 실패: order_id={order_id}, error={str(e)}")
        raise HTTPException(status_code=408, detail="결제 처리 시간 초과")
    except HTTPException:
        # 이미 HTTPException이 발생한 경우 (결제 실패 등) 그대로 재발생
        raise
    except Exception as e:
        logger.error(f"[v2] 웹훅 대기 중 예외 발생: order_id={order_id}, error={str(e)}")
        raise HTTPException(status_code=500, detail="결제 처리 중 오류가 발생했습니다.")

    # (7) 로그
    if background_tasks:
        background_tasks.add_task(
            send_user_log,
            user_id=user_id,
            event_type="order_payment_confirm_v2_complete",
            event_data={
                "order_id": order_id,
                "tx_id": tx_id,
                "callback_url": callback_url,
                "payment_init_ack": init_ack,
                "webhook_result": webhook_result,
                "final_status": final_status,
            },
        )

    # kok_order_ids와 hs_order_id 추출
    kok_order_ids = [kok_order.kok_order_id for kok_order in order_data.get("kok_orders", [])]
    hs_order_id = None
    if order_data.get("homeshopping_orders"):
        hs_order_id = order_data["homeshopping_orders"][0].homeshopping_order_id  # 홈쇼핑 주문은 단개
    
    # PaymentConfirmV2Response 스키마에 맞는 응답 구성
    response = PaymentConfirmV2Response(
        payment_id=payment_id,
        order_id=order_id,
        kok_order_ids=kok_order_ids,
        hs_order_id=hs_order_id,
        status=final_status,
        payment_amount=total_order_price,
        method="WEBHOOK_V2",
        confirmed_at=datetime.now(),
        order_id_internal=order_id,
        tx_id=tx_id,
    )
    
    # logger.info(f"[v2] 결제 확인 완료: order_id={order_id}, tx_id={tx_id}, status={final_status}")
    return response


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
    if SERVICE_AUTH_TOKEN and authorization:
        expected = f"Bearer {SERVICE_AUTH_TOKEN}"
    # logger.info(f"[v2] 서비스 토큰 검증: expected='{expected}', received='{authorization}'")
        if authorization != expected:
            logger.warning(f"[v2] 서비스 토큰 불일치: expected='{expected}', received='{authorization}'")
            return {"ok": False, "reason": "invalid_service_token"}
    # logger.info("[v2] 서비스 토큰 검증 성공")
    elif not SERVICE_AUTH_TOKEN:
        logger.info("[v2] SERVICE_AUTH_TOKEN이 설정되지 않아 서비스 토큰 검증 생략")
    elif not authorization:
        logger.info("[v2] Authorization 헤더가 없어 서비스 토큰 검증 생략")
        # 개발/테스트 환경에서는 헤더가 없어도 계속 진행

    # (1) 서명 검증
    if not PAYMENT_WEBHOOK_SECRET:
        logger.error("[v2] PAYMENT_WEBHOOK_SECRET 환경변수가 설정되지 않음")
        return {"ok": False, "reason": "webhook_secret_not_configured"}
    
    # 개발용 시그니처 우회 (테스트용)
    if signature_b64 == "dev_signature_skip":
        logger.warning("[v2] 개발용 시그니처 우회 (테스트 환경)")
    elif not _verify_webhook_signature(raw_body, signature_b64, PAYMENT_WEBHOOK_SECRET):
        logger.warning(f"[v2] 웹훅 시그니처 검증 실패: secret_length={len(PAYMENT_WEBHOOK_SECRET) if PAYMENT_WEBHOOK_SECRET else 0}, signature={signature_b64[:20]}...")
        return {"ok": False, "reason": "invalid_signature"}

    # (2) 페이로드 파싱
    try:
        payload = json.loads(raw_body.decode("utf-8"))
        # logger.info(f"[v2] 웹훅 페이로드 파싱 성공: {payload}")
    except Exception as e:
        logger.error(f"[v2] 웹훅 바디 파싱 실패: {e}, raw_body={raw_body}")
        return {"ok": False, "reason": "invalid_body"}

    order_id = payload.get("order_id")
    payment_id = payload.get("payment_id")
    completed_at = payload.get("completed_at") or payload.get("confirmed_at")  # confirmed_at도 지원
    failure_reason = payload.get("failure_reason")
    payload_user_id = payload.get("user_id")

    # 경로 tx_id 와 바디 tx_id 일치 여부 점검 (보안/정합성)
    body_tx_id = payload.get("tx_id")
    if body_tx_id and body_tx_id != tx_id:
        logger.warning(f"[v2] tx_id 불일치: path={tx_id}, body={body_tx_id}")
 
    if not order_id:
        logger.warning(f"[v2] 웹훅 페이로드에 order_id 없음: tx_id={tx_id}, payload={payload}")
        return {"ok": False, "reason": "missing_order_id"}

    # (3) event 처리
    if event == "payment.completed":
        # 주문 접근 확인
        # 서명 검증 통과시, 페이로드 user_id를 신뢰하여 접근 검증에 사용
        try:
            order_data = await _ensure_order_access(db, order_id, payload_user_id)
        except HTTPException as e:
            logger.error(f"[v2] 주문 접근 검증 실패: order_id={order_id}, payload_user_id={payload_user_id}, status={e.status_code}, detail={e.detail}")
            return {"ok": False, "reason": "order_access_denied"}
 
        kok_orders = order_data.get("kok_orders", [])
        hs_orders = order_data.get("homeshopping_orders", [])

        # 하위 주문 상태 일괄 갱신 (v1과 동일한 헬퍼)
        await _mark_all_children_payment_completed(
            db,
            kok_orders=kok_orders,
            hs_orders=hs_orders,
            user_id=None,  # 시스템 처리면 None/0 등 정책에 맞게
        )
        await db.commit()

        # (선택) 상태이력/알림 로깅
        # background task가 라우터에 없다면 여기서 바로 적재하거나 생략
        # logger.info(f"[v2] 결제완료 반영: order_id={order_id}, payment_id={payment_id}")

        # kok_order_ids와 hs_order_id 추출하여 응답에 포함
        kok_order_ids = [kok_order.kok_order_id for kok_order in kok_orders]
        hs_order_id = None
        if hs_orders:
            hs_order_id = hs_orders[0].homeshopping_order_id  # 홈쇼핑 주문은 단개

        # 웹훅 결과를 대기자들에게 알림 (최종 상태이므로 resolve 사용)
        webhook_result = {
            "ok": True, 
            "order_id": order_id, 
            "event": event, 
            "payment_id": payment_id,
            "kok_order_ids": kok_order_ids,
            "hs_order_id": hs_order_id,
            "completed_at": completed_at
        }
        awakened_count = await webhook_waiters.resolve(tx_id, webhook_result)
        # logger.info(f"[v2] 웹훅 결과 알림 완료: tx_id={tx_id}, awakened_count={awakened_count}")

        return webhook_result

    elif event in ("payment.failed", "payment.cancelled"):
        # 결제 실패/취소 시 주문 취소
        try:
            reason = failure_reason if failure_reason else "결제 실패"
            await cancel_order(db, order_id, reason)
            # logger.info(f"[v2] 결제실패/취소로 인한 주문 취소 완료: order_id={order_id}, reason={reason}")
        except Exception as e:
            logger.error(f"[v2] 주문 취소 실패: order_id={order_id}, error={str(e)}")
        
        await db.commit()
        # logger.info(f"[v2] 결제실패/취소 반영: order_id={order_id}, reason={failure_reason}")
        
        # 웹훅 결과를 대기자들에게 알림 (최종 상태이므로 resolve 사용)
        webhook_result = {
            "ok": True, 
            "order_id": order_id, 
            "event": event, 
            "reason": failure_reason,
            "payment_id": payment_id
        }
        awakened_count = await webhook_waiters.resolve(tx_id, webhook_result)
        # logger.info(f"[v2] 웹훅 실패 결과 알림 완료: tx_id={tx_id}, awakened_count={awakened_count}")
        
        return webhook_result

    else:
        logger.warning(f"[v2] 알 수 없는 이벤트: {event}")
        return {"ok": False, "reason": "unknown_event"}

