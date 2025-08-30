"""
주문 결제 관련 API 라우터
Router 계층: HTTP 요청/응답 처리, 파라미터 검증, 의존성 주입만 담당
비즈니스 로직은 CRUD 계층에 위임, 직접 DB 처리(트랜잭션)는 하지 않음
"""
from fastapi import APIRouter, Depends, BackgroundTasks, status, Request, Header, HTTPException
from fastapi.responses import JSONResponse
from typing import Optional, Any, Dict, List, Tuple
import asyncio, time, json
from sqlalchemy.ext.asyncio import AsyncSession

from common.database.mariadb_service import get_maria_service_db
from common.dependencies import get_current_user
from common.logger import get_logger

from services.order.schemas.payment_schema import (
    PaymentConfirmV1Request, PaymentConfirmV1Response, LongPollQuery
)
from services.order.crud.payment_crud import confirm_payment_and_update_status_v1

logger = get_logger("payment_router")
router = APIRouter(prefix="/api/orders/payment", tags=["Orders/Payment"])

# === [v1 routes: polling flow] ============================================
@router.post("/{order_id}/confirm/v1", response_model=PaymentConfirmV1Response, status_code=status.HTTP_200_OK)
async def confirm_payment_v1(
    order_id: int,
    payment_data: PaymentConfirmV1Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_maria_service_db),
    current_user=Depends(get_current_user),
):
    """
    주문 결제 확인 v1 (외부 결제 API 응답을 기다리는 방식)
    
    Args:
        order_id: 결제 확인할 주문 ID
        payment_data: 결제 확인 요청 데이터
        background_tasks: 백그라운드 작업 관리자
        db: 데이터베이스 세션 (의존성 주입)
        current_user: 현재 인증된 사용자 (의존성 주입)
    
    Returns:
        PaymentConfirmV1Response: 결제 확인 결과
        
    Note:
        - Router 계층: HTTP 요청/응답 처리, 파라미터 검증, 의존성 주입
        - 비즈니스 로직은 CRUD 계층에 위임
        - 외부 결제 생성 → payment_id 수신 → 결제 상태 폴링(PENDING→완료/실패)
        - 완료 시: 해당 order_id 하위 주문들을 PAYMENT_COMPLETED로 갱신(트랜잭션)
        - 실패/타임아웃 시: 적절한 HTTPException 반환
    """
    # CRUD 계층에 결제 확인 및 상태 업데이트 위임
    return await confirm_payment_and_update_status_v1(
        db=db,
        order_id=order_id,
        user_id=current_user.user_id,
        payment_data=payment_data,
        background_tasks=background_tasks,
    )
# ===========================================================================


# -----------------------------------------------------------------------------
# WaiterRegistry (롱폴링 대기자 레지스트리)
#   - key(여기서는 order_id 문자열)별 Future 구독/깨우기/해결 관리
# -----------------------------------------------------------------------------
class WaiterRegistry:
    def __init__(self) -> None:
        # waiters[key] = [(future, created_at_ts), ...]
        self.waiters: Dict[str, List[Tuple[asyncio.Future, float]]] = {}
        # resolved[key] = payload
        self.resolved: Dict[str, Any] = {}
        self._lock = asyncio.Lock()

    async def subscribe(self, key: str, check_resolved_first: bool = True) -> asyncio.Future:
        async with self._lock:
            if check_resolved_first and key in self.resolved:
                fut = asyncio.get_running_loop().create_future()
                fut.set_result(self.resolved[key])
                return fut
            fut: asyncio.Future = asyncio.get_running_loop().create_future()
            self.waiters.setdefault(key, []).append((fut, time.time()))
            return fut

    async def notify(self, key: str, payload: Any) -> int:
        async with self._lock:
            entries = self.waiters.pop(key, [])
        for fut, _ in entries:
            if not fut.done():
                fut.set_result(payload)
        return len(entries)

    async def resolve(self, key: str, payload: Any) -> int:
        async with self._lock:
            self.resolved[key] = payload
            entries = self.waiters.pop(key, [])
        for fut, _ in entries:
            if not fut.done():
                fut.set_result(payload)
        return len(entries)

    async def cleanup(self, max_age_sec: float = 300.0) -> None:
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

waiters = WaiterRegistry()


# === [v2 routes: webhook flow] ==============================================
from services.order.crud.payment_crud import confirm_payment_and_update_status_v2, apply_payment_webhook_v2

# === [v2 routes: webhook + long-poll wait] ====================================
# confirm/v2 -> '대기' 엔드포인트로 전환
@router.post("/{order_id}/confirm/v2", status_code=status.HTTP_200_OK)
async def confirm_payment_v2_wait(
    order_id: int,
    query: LongPollQuery,
    current_user=Depends(get_current_user),  # 접근 제어를 유지 (필요시 실제 검증은 CRUD에서 수행)
):
    """
    v2(웹훅) 결제확인 '대기' API (롱폴링)
    - 프론트가 결제서버(/api/v2/payments)로 결제를 시작한 다음,
      이 엔드포인트를 호출해 결과를 최대 timeout_sec 동안 기다린다.
    - 웹훅이 먼저 도착하면 즉시 200과 payload를 반환.
    - 타임아웃이면 204 No Content.
    """
    key = str(order_id)
    fut = await waiters.subscribe(key, check_resolved_first=True)
    try:
        payload = await asyncio.wait_for(fut, timeout=query.timeout_sec)
    except asyncio.TimeoutError:
        return JSONResponse(status_code=status.HTTP_204_NO_CONTENT, content=None)

    # payload는 웹훅에서 notify/resolve로 전달된 그대로
    return JSONResponse(status_code=status.HTTP_200_OK, content={"order_id": order_id, "data": payload})


@router.post("/webhook/v2/{tx_id}", name="payment_webhook_handler_v2")
async def payment_webhook_v2(
    tx_id: str,
    request: Request,
    db: AsyncSession = Depends(get_maria_service_db),
    authorization: str | None = Header(None),
):
    """
    결제서버 웹훅 수신 엔드포인트 (v2)
    - 헤더:
        X-Payment-Signature: base64(HMAC-SHA256(body, secret))
        X-Payment-Event: payment.completed | payment.failed | payment.cancelled
    - 본문(JSON): 최소 { order_id, payment_id, tx_id, status, ... }
    """
    # 로깅
    logger.info(f"[v2] 웹훅 수신: tx_id={tx_id}")
    logger.info(f"[v2] 모든 헤더: {dict(request.headers)}")

    x_event = request.headers.get("x-payment-event")
    x_sig = request.headers.get("x-payment-signature")

    if not x_event:
        logger.warning("[v2] X-Payment-Event 누락 → 기본값 payment.completed 사용(개발용)")
        x_event = "payment.completed"
    if not x_sig:
        logger.warning("[v2] X-Payment-Signature 누락 → 검증 생략(개발용)")
        x_sig = "dev_signature_skip"

    body_bytes = await request.body()
    logger.info(f"[v2] 웹훅 바디: size={len(body_bytes)} bytes, preview={body_bytes[:200]!r}")

    # 1) DB 반영/검증은 기존 CRUD에 위임
    try:
        result = await apply_payment_webhook_v2(
            db=db,
            tx_id=tx_id,
            raw_body=body_bytes,
            signature_b64=x_sig,
            event=x_event,
            authorization=authorization,
        )
    except Exception as e:
        logger.error(f"[v2] 웹훅 처리 중 예외: {e}")
        raise HTTPException(status_code=500, detail=f"webhook processing error: {e}")

    if not result.get("ok"):
        logger.error(f"[v2] 웹훅 처리 실패: {result}")
        raise HTTPException(status_code=400, detail=result.get("reason", "webhook handling failed"))

    # 2) 대기자 깨우기 (order_id 기준)
    #    - 최종 상태(완료/실패/취소)는 resolve: 이후 새 구독자도 즉시 결과 획득
    #    - 그 외 중간 이벤트는 notify: 현재 대기자만 깨움
    try:
        payload = json.loads(body_bytes.decode("utf-8"))
    except Exception:
        payload = {"raw": body_bytes[:200].decode("utf-8", errors="ignore")}

    order_id = str(payload.get("order_id") or "")
    if not order_id:
        logger.warning("[v2] payload에 order_id 없음 → 대기자 깨우기 생략")
    else:
        # 이벤트/상태 기준으로 최종 여부 판정
        final_events = {"payment.completed", "payment.failed", "payment.cancelled"}
        final_statuses = {"PAYMENT_COMPLETED", "FAILED", "CANCELED", "CANCELLED", "SUCCESS"}

        status_val = str(payload.get("status", "")).upper()
        is_final = (x_event in final_events) or (status_val in final_statuses)

        if is_final:
            awakened = await waiters.resolve(order_id, payload)
            logger.info(f"[v2] resolve({order_id}) → {awakened} waiters awakened")
        else:
            awakened = await waiters.notify(order_id, payload)
            logger.info(f"[v2] notify({order_id}) → {awakened} waiters awakened")

    return {"received": True, **result}
# ==============================================================================

# @router.post("/{order_id}/confirm/v2", response_model=PaymentConfirmV1Response, status_code=status.HTTP_200_OK)  # 주문 결제 확인 v2 (웹훅 방식)
# async def confirm_payment_v2(
#     order_id: int,
#     request: Request,
#     background_tasks: BackgroundTasks,
#     current_user=Depends(get_current_user),  # 공백 제거
#     db: AsyncSession = Depends(get_maria_service_db),
# ):
#     """
#     v2(웹훅) 결제확인 시작 API
#     - 즉시 PENDING 반환, 실제 완료는 /payment/webhook/v2 로 수신
#     """
#     try:
#         result = await confirm_payment_and_update_status_v2(
#             db=db,
#             order_id=order_id,
#             user_id=current_user.user_id,
#             request=request,
#             background_tasks=background_tasks,
#         )
#         return result
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"payment v2 init failed: {e}")


# @router.post("/webhook/v2/{tx_id}", name="payment_webhook_handler_v2")
# async def payment_webhook_v2(
#     tx_id: str,
#     request: Request,
#     db: AsyncSession = Depends(get_maria_service_db),
#     authorization: str | None = Header(None),  # (옵션) 서비스 토큰
# ):
#     """
#     결제서버 웹훅 수신 엔드포인트
#     - 헤더 X-Payment-Signature (base64 HMAC-SHA256)
#     - 헤더 X-Payment-Event (payment.completed | payment.failed | payment.cancelled)
#     """
#     # 모든 헤더 로깅
#     all_headers = dict(request.headers)
#     logger.info(f"[v2] 웹훅 수신: tx_id={tx_id}")
#     logger.info(f"[v2] 모든 헤더: {all_headers}")
    
#     # 헤더 직접 추출 (FastAPI Header 파라미터 파싱 문제 해결)
#     x_payment_event = request.headers.get("x-payment-event")
#     x_payment_signature = request.headers.get("x-payment-signature")
    
#     logger.info(f"[v2] 직접 추출한 헤더: event={x_payment_event}, signature={x_payment_signature[:20] if x_payment_signature else 'None'}...")
    
#     # 헤더가 없어도 웹훅 처리를 계속 진행 (개발/테스트 환경)
#     if not x_payment_event:
#         x_payment_event = "payment.completed"
#         logger.warning(f"[v2] 이벤트 헤더가 없어 기본값 사용: {x_payment_event}")
    
#     if not x_payment_signature:
#         logger.warning(f"[v2] 시그니처 헤더가 없어 검증 생략 (개발/테스트용)")
#         x_payment_signature = "dev_signature_skip"

#     body = await request.body()
#     logger.info(f"[v2] 웹훅 바디 수신: size={len(body)} bytes, body={body[:200]}...")
    
#     try:
#         result = await apply_payment_webhook_v2(
#             db=db,
#             tx_id=tx_id,
#             raw_body=body,
#             signature_b64=x_payment_signature,
#             event=x_payment_event,
#             authorization=authorization,
#         )
#         logger.info(f"[v2] 웹훅 처리 결과: {result}")
        
#         if not result.get("ok"):
#             logger.error(f"[v2] 웹훅 처리 실패: {result}")
#             raise HTTPException(status_code=400, detail=result.get("reason","webhook handling failed"))
        
#         return {"received": True, **result}
#     except Exception as e:
#         logger.error(f"[v2] 웹훅 처리 중 예외 발생: {e}")
#         raise HTTPException(status_code=500, detail=f"webhook processing error: {str(e)}")
# # ===========================================================================
