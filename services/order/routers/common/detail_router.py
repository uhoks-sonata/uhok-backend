"""Common order detail API routes."""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request
from sqlalchemy.ext.asyncio import AsyncSession

from common.database.mariadb_service import get_maria_service_db
from common.dependencies import get_current_user
from common.log_utils import send_user_log
from common.http_dependencies import extract_http_info
from common.logger import get_logger
from services.order.schemas.order_schema import OrderRead
from services.order.crud.common.order_detail_read_crud import get_order_by_id

logger = get_logger("order_router")
router = APIRouter()

@router.get("/{order_id}", response_model=OrderRead)
async def read_order(
        request: Request,
        order_id: int,
        background_tasks: BackgroundTasks = None,
        db: AsyncSession = Depends(get_maria_service_db),
        user=Depends(get_current_user)
):
    """
    단일 주문 조회 (공통+콕+HomeShopping 상세 포함)
    
    Args:
        order_id: 조회할 주문 ID
        background_tasks: 백그라운드 작업 관리자
        db: 데이터베이스 세션 (의존성 주입)
        user: 현재 인증된 사용자 (의존성 주입)
    
    Returns:
        OrderRead: 주문 상세 정보
        
    Note:
        - Router 계층: HTTP 요청/응답 처리, 파라미터 검증, 의존성 주입
        - 비즈니스 로직은 CRUD 계층에 위임
        - 주문자 본인만 조회 가능 (권한 검증)
        - 공통 주문 정보 + 콕 주문 상세 + 홈쇼핑 주문 상세 포함
        - 사용자 행동 로그 기록
    """
    logger.debug(f"주문 상세 조회 시작: user_id={user.user_id}, order_id={order_id}")
    logger.info(f"주문 상세 조회 요청: user_id={user.user_id}, order_id={order_id}")
    
    # CRUD 계층에 주문 조회 위임
    try:
        order_data = await get_order_by_id(db, order_id)
        if not order_data:
            logger.warning(f"주문을 찾을 수 없음: order_id={order_id}, user_id={user.user_id}")
            raise HTTPException(status_code=404, detail="주문 내역이 없습니다.")
        if order_data["user_id"] != user.user_id:
            logger.warning(f"주문 접근 권한 없음: order_id={order_id}, 요청 user_id={user.user_id}, 주문자 user_id={order_data['user_id']}")
            raise HTTPException(status_code=404, detail="주문 내역이 없습니다.")
        logger.debug(f"주문 상세 조회 성공: order_id={order_id}, user_id={user.user_id}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"주문 상세 조회 실패: order_id={order_id}, user_id={user.user_id}, error={str(e)}")
        raise HTTPException(status_code=500, detail="주문 조회 중 오류가 발생했습니다.")

    # 주문 상세 조회 로그 기록
    if background_tasks:
        http_info = extract_http_info(request, response_code=200)
        background_tasks.add_task(
            send_user_log,
            user_id=user.user_id,
            event_type="order_order_detail_view",
            event_data={"order_id": order_id},
            **http_info  # HTTP 정보를 키워드 인자로 전달
        )

    return order_data
