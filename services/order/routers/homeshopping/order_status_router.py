"""HomeShopping order/status API routes."""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.database.mariadb_service import get_maria_service_db
from common.dependencies import get_current_user
from common.log_utils import send_user_log
from common.http_dependencies import extract_http_info
from common.logger import get_logger
from services.user.schemas.profile_schema import UserOut
from services.order.models.order_base_model import StatusMaster
from services.order.schemas.homeshopping.order_schema import (
    HomeshoppingOrderRequest,
    HomeshoppingOrderResponse,
)
from services.order.schemas.homeshopping.status_schema import (
    HomeshoppingOrderStatusResponse,
    HomeshoppingOrderWithStatusResponse,
)
from services.order.crud.homeshopping.hs_order_flow_crud import create_homeshopping_order
from services.order.crud.homeshopping.hs_order_status_crud import (
    get_hs_order_status_history,
    get_hs_order_with_status,
    get_hs_current_status,
)

logger = get_logger("hs_order_router")
router = APIRouter()

@router.post("/order", response_model=HomeshoppingOrderResponse)
async def create_order(
        request: Request,
        order_data: HomeshoppingOrderRequest,
        current_user: UserOut = Depends(get_current_user),
        background_tasks: BackgroundTasks = None,
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    홈쇼핑 주문 생성 (단건 주문)
    
    Args:
        order_data: 홈쇼핑 주문 요청 데이터 (상품 ID, 수량)
        current_user: 현재 인증된 사용자 (의존성 주입)
        background_tasks: 백그라운드 작업 관리자
        db: 데이터베이스 세션 (의존성 주입)
    
    Returns:
        HomeshoppingOrderResponse: 주문 생성 결과
        
    Note:
        - Router 계층: HTTP 요청/응답 처리, 파라미터 검증, 의존성 주입
        - 비즈니스 로직은 CRUD 계층에 위임
        - 단건 주문만 지원 (장바구니 방식 아님)
        - 주문 생성 후 사용자 행동 로그 기록
        - 주문 접수 상태로 초기화 및 알림 생성
    """
    logger.debug(f"홈쇼핑 주문 생성 시작: user_id={current_user.user_id}, product_id={order_data.product_id}, quantity={order_data.quantity}")
    logger.info(f"홈쇼핑 주문 생성 요청: user_id={current_user.user_id}, product_id={order_data.product_id}, quantity={order_data.quantity}")
    
    try:
        # CRUD 계층에 주문 생성 위임
        order_result = await create_homeshopping_order(
            db, 
            current_user.user_id, 
            order_data.product_id,
            order_data.quantity
        )
        logger.debug(f"홈쇼핑 주문 생성 성공: user_id={current_user.user_id}, order_id={order_result['order_id']}")
        
        # 주문 생성 로그 기록
        if background_tasks:
            http_info = extract_http_info(request, response_code=201)
            background_tasks.add_task(
                send_user_log, 
                user_id=current_user.user_id, 
                event_type="homeshopping_order_create", 
                event_data={
                    "order_id": order_result["order_id"], 
                    "product_id": order_data.product_id,
                    "quantity": order_data.quantity
                },
                **http_info  # HTTP 정보를 키워드 인자로 전달
            )
        
        logger.info(f"홈쇼핑 주문 생성 완료: user_id={current_user.user_id}, order_id={order_result['order_id']}")
        return order_result
        
    except ValueError as e:
        logger.warning(f"홈쇼핑 주문 생성 실패 - 잘못된 값: user_id={current_user.user_id}, error={str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"홈쇼핑 주문 생성 실패: user_id={current_user.user_id}, error={str(e)}")
        raise HTTPException(status_code=500, detail="주문 생성 중 오류가 발생했습니다.")


@router.get("/{homeshopping_order_id}/status", response_model=HomeshoppingOrderStatusResponse)
async def get_order_status(
        request: Request,
        homeshopping_order_id: int,
        current_user: UserOut = Depends(get_current_user),
        background_tasks: BackgroundTasks = None,
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    홈쇼핑 주문 상태 조회
    
    Args:
        homeshopping_order_id: 홈쇼핑 주문 ID
        current_user: 현재 인증된 사용자 (의존성 주입)
        background_tasks: 백그라운드 작업 관리자
        db: 데이터베이스 세션 (의존성 주입)
    
    Returns:
        HomeshoppingOrderStatusResponse: 주문 상태 정보 (현재 상태 + 변경 이력)
        
    Note:
        - Router 계층: HTTP 요청/응답 처리, 파라미터 검증, 의존성 주입
        - 비즈니스 로직은 CRUD 계층에 위임
        - 특정 홈쇼핑 주문의 현재 상태와 모든 상태 변경 이력을 조회
        - 상태 이력이 없는 경우 기본 상태(ORDER_RECEIVED) 사용
        - 사용자 행동 로그 기록
    """
    logger.debug(f"홈쇼핑 주문 상태 조회 시작: user_id={current_user.user_id}, homeshopping_order_id={homeshopping_order_id}")
    logger.info(f"홈쇼핑 주문 상태 조회 요청: user_id={current_user.user_id}, homeshopping_order_id={homeshopping_order_id}")
    
    try:
        # CRUD 계층에 주문 상태 조회 위임
        order_data = await get_hs_order_with_status(db, homeshopping_order_id)
        if not order_data:
            logger.warning(f"홈쇼핑 주문을 찾을 수 없음: homeshopping_order_id={homeshopping_order_id}, user_id={current_user.user_id}")
            raise HTTPException(status_code=404, detail="해당 홈쇼핑 주문을 찾을 수 없습니다.")
        logger.debug(f"홈쇼핑 주문 조회 성공: homeshopping_order_id={homeshopping_order_id}")
        
        # 2. 현재 상태 조회
        current_status = await get_hs_current_status(db, homeshopping_order_id)
        
        # 기본 상태 조회 (ORDER_RECEIVED) - 항상 조회
        default_status_result = await db.execute(
            select(StatusMaster).where(StatusMaster.status_code == "ORDER_RECEIVED")
        )
        default_status = default_status_result.scalars().first()
        if not default_status:
            logger.error(f"기본 상태 정보를 찾을 수 없음: ORDER_RECEIVED")
            raise HTTPException(status_code=404, detail="기본 상태 정보를 찾을 수 없습니다.")
        
        if not current_status:
            logger.debug(f"현재 상태가 없어 기본 상태 사용: homeshopping_order_id={homeshopping_order_id}")
            # 기본 상태로 current_status 설정
            current_status = type('obj', (object,), {
                'status': default_status
            })()
        
        # 상태 변경 이력 조회
        status_history = await get_hs_order_status_history(db, homeshopping_order_id)
        logger.debug(f"상태 이력 조회 완료: homeshopping_order_id={homeshopping_order_id}, history_count={len(status_history)}")
        
        # 주문 상태 조회 로그 기록
        if background_tasks:
            http_info = extract_http_info(request, response_code=200)
            background_tasks.add_task(
                send_user_log, 
                user_id=current_user.user_id, 
                event_type="homeshopping_order_status_view", 
                event_data={
                    "homeshopping_order_id": homeshopping_order_id,
                    "current_status": current_status.status.status_code if current_status and current_status.status else "UNKNOWN"
                },
                **http_info  # HTTP 정보를 키워드 인자로 전달
            )
        
        logger.info(f"홈쇼핑 주문 상태 조회 완료: user_id={current_user.user_id}, homeshopping_order_id={homeshopping_order_id}")
        
        # 상태 이력을 스키마에 맞게 변환
        formatted_status_history = []
        for history_item in status_history:
            if history_item and history_item.status:
                formatted_history = {
                    "history_id": history_item.history_id,
                    "homeshopping_order_id": history_item.homeshopping_order_id,
                    "status": history_item.status,
                    "created_at": history_item.changed_at  # changed_at을 created_at으로 매핑
                }
                formatted_status_history.append(formatted_history)
        
        # API 명세서에 맞게 current_status가 항상 유효한 값을 가지도록 보장
        if not current_status or not current_status.status:
            # 기본 상태 정보 반환
            return {
                "homeshopping_order_id": homeshopping_order_id,
                "current_status": {
                    "status_id": default_status.status_id,
                    "status_code": default_status.status_code,
                    "status_name": default_status.status_name
                },
                "status_history": formatted_status_history
            }
        
        return {
            "homeshopping_order_id": homeshopping_order_id,
            "current_status": {
                "status_id": current_status.status.status_id,
                "status_code": current_status.status.status_code,
                "status_name": current_status.status.status_name
            },
            "status_history": formatted_status_history
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"홈쇼핑 주문 상태 조회 실패: homeshopping_order_id={homeshopping_order_id}, user_id={current_user.user_id}, error={str(e)}")
        raise HTTPException(status_code=500, detail="주문 상태 조회 중 오류가 발생했습니다.")

@router.get("/{homeshopping_order_id}/with-status", response_model=HomeshoppingOrderWithStatusResponse)
async def get_order_with_status(
        request: Request,
        homeshopping_order_id: int,
        current_user: UserOut = Depends(get_current_user),
        background_tasks: BackgroundTasks = None,
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    홈쇼핑 주문과 상태 함께 조회
    
    Args:
        homeshopping_order_id: 홈쇼핑 주문 ID
        current_user: 현재 인증된 사용자 (의존성 주입)
        background_tasks: 백그라운드 작업 관리자
        db: 데이터베이스 세션 (의존성 주입)
    
    Returns:
        HomeshoppingOrderWithStatusResponse: 주문 상세 정보와 상태 정보
        
    Note:
        - Router 계층: HTTP 요청/응답 처리, 파라미터 검증, 의존성 주입
        - 비즈니스 로직은 CRUD 계층에 위임
        - 주문 상세 정보와 현재 상태를 한 번에 조회
        - 상품 정보, 주문 정보, 상태 정보를 모두 포함
        - 사용자 행동 로그 기록
    """
    logger.debug(f"홈쇼핑 주문 상세 조회 시작: user_id={current_user.user_id}, homeshopping_order_id={homeshopping_order_id}")
    logger.info(f"홈쇼핑 주문 상세 조회 요청: user_id={current_user.user_id}, homeshopping_order_id={homeshopping_order_id}")
    
    try:
        order_data = await get_hs_order_with_status(db, homeshopping_order_id)
        if not order_data:
            logger.warning(f"홈쇼핑 주문을 찾을 수 없음: homeshopping_order_id={homeshopping_order_id}, user_id={current_user.user_id}")
            raise HTTPException(status_code=404, detail="주문을 찾을 수 없습니다.")
        logger.debug(f"홈쇼핑 주문 상세 조회 성공: homeshopping_order_id={homeshopping_order_id}")
        
        # 주문과 상태 함께 조회 로그 기록
        if background_tasks:
            http_info = extract_http_info(request, response_code=200)
            background_tasks.add_task(
                send_user_log, 
                user_id=current_user.user_id,
                event_type="homeshopping_order_with_status_view", 
                event_data={
                    "homeshopping_order_id": homeshopping_order_id,
                    "current_status": order_data.get("current_status", {}).get("status_code") if order_data.get("current_status") else None
                },
                **http_info  # HTTP 정보를 키워드 인자로 전달
            )
        
        logger.info(f"홈쇼핑 주문 상세 조회 완료: user_id={current_user.user_id}, homeshopping_order_id={homeshopping_order_id}")
        
        return order_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"홈쇼핑 주문 상세 조회 실패: homeshopping_order_id={homeshopping_order_id}, user_id={current_user.user_id}, error={str(e)}")
        raise HTTPException(status_code=500, detail="주문 조회 중 오류가 발생했습니다.")
