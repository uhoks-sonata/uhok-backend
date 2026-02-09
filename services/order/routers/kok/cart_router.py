"""Kok cart-order API routes."""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status, Request
from sqlalchemy.ext.asyncio import AsyncSession

from common.database.mariadb_service import get_maria_service_db
from common.dependencies import get_current_user
from common.log_utils import send_user_log
from common.http_dependencies import extract_http_info
from common.logger import get_logger
from services.user.schemas.profile_schema import UserOut
from services.order.schemas.kok.cart_schema import (
    KokCartOrderRequest,
    KokCartOrderResponse,
)
from services.order.crud.kok.kok_order_create_crud import create_orders_from_selected_carts

logger = get_logger("kok_order_router")
router = APIRouter()

@router.post("/carts/order", response_model=KokCartOrderResponse, status_code=status.HTTP_201_CREATED)
async def order_from_selected_carts(
    http_request: Request,
    request: KokCartOrderRequest,
    current_user: UserOut = Depends(get_current_user),
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_maria_service_db),
):
    """
    장바구니에서 선택된 항목들로 주문 생성
    
    Args:
        request: 장바구니 주문 요청 데이터 (선택된 항목들)
        current_user: 현재 인증된 사용자 (의존성 주입)
        background_tasks: 백그라운드 작업 관리자
        db: 데이터베이스 세션 (의존성 주입)
    
    Returns:
        KokCartOrderResponse: 주문 생성 결과
        
    Note:
        - Router 계층: HTTP 요청/응답 처리, 파라미터 검증, 의존성 주입
        - 비즈니스 로직은 CRUD 계층에 위임
        - 선택된 장바구니 항목들을 기반으로 주문 생성 (kok_cart_id 사용)
        - 주문 생성 후 사용자 행동 로그 기록
        - 단일 상품 주문 대신 멀티 카트 주문 방식 사용
    """
    logger.debug(f"장바구니 주문 시작: user_id={current_user.user_id}, selected_items_count={len(request.selected_items)}")
    logger.info(f"장바구니 주문 요청: user_id={current_user.user_id}, selected_items_count={len(request.selected_items)}")
    
    if not request.selected_items:
        logger.warning(f"선택된 항목이 없음: user_id={current_user.user_id}")
        raise HTTPException(status_code=400, detail="선택된 항목이 없습니다.")

    try:
        # CRUD 계층에 주문 생성 위임
        result = await create_orders_from_selected_carts(
            db, current_user.user_id, [i.model_dump() for i in request.selected_items]
        )
        logger.debug(f"장바구니 주문 생성 성공: user_id={current_user.user_id}, order_id={result['order_id']}")

        logger.info(f"장바구니 주문 생성 완료: user_id={current_user.user_id}, order_id={result['order_id']}, order_count={result['order_count']}")

        if background_tasks:
            http_info = extract_http_info(http_request, response_code=201)
            background_tasks.add_task(
                send_user_log,
                user_id=current_user.user_id,
                event_type="kok_cart_order_create",
                event_data=result,
                **http_info  # HTTP 정보를 키워드 인자로 전달
            )

        return KokCartOrderResponse(
            order_id=result["order_id"],
            total_amount=result["total_amount"],
            order_count=result["order_count"],
            order_details=result["order_details"],
            message=result["message"],
            order_time=result["order_time"],
        )
        
    except ValueError as e:
        logger.warning(f"장바구니 주문 생성 실패 (검증 오류): user_id={current_user.user_id}, error={str(e)}")
        # 사용자에게 더 친화적인 에러 메시지 제공
        error_message = str(e)
        if "선택된 장바구니 항목을 찾을 수 없습니다" in error_message:
            error_message = "선택한 장바구니 항목이 존재하지 않거나 이미 삭제되었습니다. 장바구니를 다시 확인해주세요."
        elif "상품 정보나 가격 정보를 찾을 수 없습니다" in error_message:
            error_message = "선택한 상품의 정보를 찾을 수 없습니다. 상품이 삭제되었거나 가격 정보가 누락되었을 수 있습니다."
        elif "유효한 주문 항목을 생성할 수 없습니다" in error_message:
            error_message = "주문할 수 있는 유효한 상품이 없습니다. 상품 정보를 확인해주세요."
        
        raise HTTPException(status_code=400, detail=error_message)
        
    except Exception as e:
        logger.error(f"장바구니 주문 생성 실패 (시스템 오류): user_id={current_user.user_id}, error={str(e)}")
        raise HTTPException(status_code=500, detail="주문 생성 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.")
