"""
주문 결제 관련 API 라우터
Router 계층: HTTP 요청/응답 처리, 파라미터 검증, 의존성 주입만 담당
비즈니스 로직은 CRUD 계층에 위임, 직접 DB 처리(트랜잭션)는 하지 않음
"""
from fastapi import APIRouter, Depends, BackgroundTasks, status
from sqlalchemy.ext.asyncio import AsyncSession

from services.order.schemas.payment_schema import PaymentConfirmV1Request, PaymentConfirmV1Response
from services.order.crud.payment_crud import confirm_payment_and_update_status_v1

from common.database.mariadb_service import get_maria_service_db
from common.dependencies import get_current_user

from common.logger import get_logger
logger = get_logger("payment_router")


router = APIRouter(prefix="/api/orders/payment", tags=["Orders/Payment"])

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
