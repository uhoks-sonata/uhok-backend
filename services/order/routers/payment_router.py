"""
주문 결제 관련 API 라우터
Router 계층: HTTP 요청/응답 처리, 파라미터 검증, 의존성 주입만 담당
비즈니스 로직은 CRUD 계층에 위임, 직접 DB 처리(트랜잭션)는 하지 않음
"""
from fastapi import APIRouter, Depends, BackgroundTasks, status, Request, Header, HTTPException
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from common.database.mariadb_service import get_maria_service_db
from common.dependencies import get_current_user
from common.log_utils import send_user_log
from common.http_dependencies import extract_http_info
from common.logger import get_logger

from services.order.schemas.payment_schema import PaymentConfirmV1Request, PaymentConfirmV1Response, PaymentConfirmV2Response
from services.order.crud.payment_crud import confirm_payment_and_update_status_v1, webhook_waiters

logger = get_logger("payment_router")
router = APIRouter(prefix="/api/orders/payment", tags=["Orders/Payment"])

# === [v1 routes: polling flow] ============================================
@router.post("/{order_id}/confirm/v1", response_model=PaymentConfirmV1Response, status_code=status.HTTP_200_OK)
async def confirm_payment_v1(
    request: Request,
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
    result = await confirm_payment_and_update_status_v1(
        db=db,
        order_id=order_id,
        user_id=current_user.user_id,
        payment_data=payment_data,
        background_tasks=background_tasks,
    )
    
    # 결제 확인 v1 로그 기록
    if background_tasks:
        http_info = extract_http_info(request, response_code=200)
        background_tasks.add_task(
            send_user_log,
            user_id=current_user.user_id,
            event_type="payment_confirm_v1",
            event_data={
                "order_id": order_id,
                "payment_method": payment_data.payment_method,
                "amount": payment_data.amount
            },
            **http_info  # HTTP 정보를 키워드 인자로 전달
        )
    
    return result
# ===========================================================================

# === [v2 routes: webhook flow] ==============================================
from services.order.crud.payment_crud import confirm_payment_and_update_status_v2, apply_payment_webhook_v2

@router.post("/{order_id}/confirm/v2", response_model=PaymentConfirmV2Response, status_code=status.HTTP_200_OK)
async def confirm_payment_v2(
    order_id: int,
    request: Request,
    background_tasks: BackgroundTasks,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_maria_service_db),
):
    """
    v2(롱폴링) 결제확인 API
    - 클라이언트가 결제하기를 누르면 백엔드로 결제처리 요청
    - 백엔드에서 결제서버로 롱폴링 방식으로 결제확인
    - 웹훅으로 결제완료 응답을 받으면 진행사항 반영
    """
    try:
        result = await confirm_payment_and_update_status_v2(
            db=db,
            order_id=order_id,
            user_id=current_user.user_id,
            request=request,
            background_tasks=background_tasks,
        )
        
        # 결제 확인 v2 로그 기록
        if background_tasks:
            http_info = extract_http_info(request, response_code=200)
            background_tasks.add_task(
                send_user_log,
                user_id=current_user.user_id,
                event_type="payment_confirm_v2",
                event_data={
                    "order_id": order_id,
                    "result_status": result.get("status", "unknown")
                },
                **http_info  # HTTP 정보를 키워드 인자로 전달
            )
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"payment v2 long polling failed: {e}")

@router.post("/webhook/v2/{tx_id}", name="payment_webhook_handler_v2")
async def payment_webhook_v2(
    tx_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_maria_service_db),
    authorization: str | None = Header(None),  # (옵션) 서비스 토큰
):
    """
    결제서버 웹훅 수신 엔드포인트
    - 헤더 X-Payment-Signature (base64 HMAC-SHA256)
    - 헤더 X-Payment-Event (payment.completed | payment.failed | payment.cancelled)
    """
    # 모든 헤더 로깅
    all_headers = dict(request.headers)
    logger.info(f"[v2] 웹훅 수신: tx_id={tx_id}")
    logger.info(f"[v2] 모든 헤더: {all_headers}")
    
    # 헤더 직접 추출 (FastAPI Header 파라미터 파싱 문제 해결)
    x_payment_event = request.headers.get("x-payment-event")
    x_payment_signature = request.headers.get("x-payment-signature")
    
    logger.info(f"[v2] 직접 추출한 헤더: event={x_payment_event}, signature={x_payment_signature[:20] if x_payment_signature else 'None'}...")
    
    # 헤더가 없어도 웹훅 처리를 계속 진행 (개발/테스트 환경)
    if not x_payment_event:
        x_payment_event = "payment.completed"
        logger.warning(f"[v2] 이벤트 헤더가 없어 기본값 사용: {x_payment_event}")
    
    if not x_payment_signature:
        logger.warning(f"[v2] 시그니처 헤더가 없어 검증 생략 (개발/테스트용)")
        x_payment_signature = "dev_signature_skip"

    body = await request.body()
    logger.info(f"[v2] 웹훅 바디 수신: size={len(body)} bytes, body={body[:200]}...")
    
    try:
        result = await apply_payment_webhook_v2(
            db=db,
            tx_id=tx_id,
            raw_body=body,
            signature_b64=x_payment_signature,
            event=x_payment_event,
            authorization=authorization,
        )
        logger.info(f"[v2] 웹훅 처리 결과: {result}")
        
        if not result.get("ok"):
            logger.error(f"[v2] 웹훅 처리 실패: {result}")
            raise HTTPException(status_code=400, detail=result.get("reason","webhook handling failed"))
        
        # 웹훅 수신 로그 기록 (익명 사용자)
        if background_tasks:
            http_info = extract_http_info(request, response_code=200)
            background_tasks.add_task(
                send_user_log,
                user_id=0,  # 웹훅은 익명 사용자
                event_type="payment_webhook_v2",
                event_data={
                    "tx_id": tx_id,
                    "event": x_payment_event,
                    "result_ok": result.get("ok", False),
                    "order_id": result.get("order_id")
                },
                **http_info  # HTTP 정보를 키워드 인자로 전달
            )
        
        return {"received": True, **result}
    except Exception as e:
        logger.error(f"[v2] 웹훅 처리 중 예외 발생: {e}")
        raise HTTPException(status_code=500, detail=f"webhook processing error: {str(e)}")

# === [Cleanup Task] =========================================================
async def cleanup_webhook_waiters():
    """
    오래된 웹훅 대기자들을 정리하는 함수
    주기적으로 호출하여 메모리 누수를 방지
    """
    try:
        await webhook_waiters.cleanup(max_age_sec=300)  # 5분 이상 된 대기자 정리
        logger.info("[v2] 웹훅 대기자 클린업 완료")
    except Exception as e:
        logger.error(f"[v2] 웹훅 대기자 클린업 실패: {e}")
# ===========================================================================