"""Order payment v1 API routes."""

from fastapi import APIRouter, Depends, BackgroundTasks, status, Request, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from common.database.mariadb_service import get_maria_service_db
from common.dependencies import get_current_user
from common.log_utils import send_user_log
from common.http_dependencies import extract_http_info
from common.logger import get_logger
from services.order.schemas.payment_schema import PaymentConfirmV1Request, PaymentConfirmV1Response
from services.order.crud.payment_v1_crud import confirm_payment_and_update_status_v1

logger = get_logger("payment_router")
router = APIRouter()

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
    logger.debug(f"결제 확인 v1 시작: user_id={current_user.user_id}, order_id={order_id}")
    logger.info(f"결제 확인 v1 요청: user_id={current_user.user_id}, order_id={order_id}, payment_method={payment_data.method}")
    
    # CRUD 계층에 결제 확인 및 상태 업데이트 위임
    try:
        result = await confirm_payment_and_update_status_v1(
            db=db,
            order_id=order_id,
            user_id=current_user.user_id,
            payment_data=payment_data,
            background_tasks=background_tasks,
        )
        logger.debug(f"결제 확인 v1 성공: user_id={current_user.user_id}, order_id={order_id}, result={result}")
    except Exception as e:
        logger.error(f"결제 확인 v1 실패: user_id={current_user.user_id}, order_id={order_id}, error={str(e)}")
        raise HTTPException(status_code=500, detail="결제 확인 중 오류가 발생했습니다.")
    
    # 결제 확인 v1 로그 기록
    if background_tasks:
        http_info = extract_http_info(request, response_code=200)
        background_tasks.add_task(
            send_user_log,
            user_id=current_user.user_id,
            event_type="payment_confirm_v1",
            event_data={
                "order_id": order_id,
                "payment_method": payment_data.method
            },
            **http_info  # HTTP 정보를 키워드 인자로 전달
        )
    
    return result
