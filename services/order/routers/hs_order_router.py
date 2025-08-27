"""
홈쇼핑 주문 관련 API 라우터
Router 계층: HTTP 요청/응답 처리, 파라미터 검증, 의존성 주입만 담당
비즈니스 로직은 CRUD 계층에 위임, 직접 DB 처리(트랜잭션)는 하지 않음
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from services.user.schemas.user_schema import UserOut
from services.order.models.order_model import (
    Order, StatusMaster, HomeShoppingOrder, HomeShoppingOrderStatusHistory
)
from services.order.schemas.hs_order_schema import (
    HomeshoppingOrderRequest,
    HomeshoppingOrderResponse,
    HomeshoppingOrderStatusResponse,
    HomeshoppingOrderWithStatusResponse,
    PaymentConfirmResponse
)  
from services.order.crud.hs_order_crud import (
    create_homeshopping_order,
    get_hs_order_status_history,
    get_hs_order_with_status,
    confirm_hs_payment,
    start_hs_auto_update,
    get_hs_current_status,
    start_auto_hs_order_status_update
)

from common.database.mariadb_service import get_maria_service_db
from common.dependencies import get_current_user
from common.log_utils import send_user_log

from common.logger import get_logger
logger = get_logger("hs_order_router")


router = APIRouter(prefix="/api/orders/homeshopping", tags=["HomeShopping Orders"])

# ================================
# 홈쇼핑 주문 관련 API
# ================================

@router.post("/order", response_model=HomeshoppingOrderResponse)
async def create_order(
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
    logger.info(f"홈쇼핑 주문 생성 요청: user_id={current_user.user_id}, product_id={order_data.product_id}, quantity={order_data.quantity}")
    
    try:
        # CRUD 계층에 주문 생성 위임
        order_result = await create_homeshopping_order(
            db, 
            current_user.user_id, 
            order_data.product_id,
            order_data.quantity
        )
        
        # 주문 생성 로그 기록
        if background_tasks:
            background_tasks.add_task(
                send_user_log, 
                user_id=current_user.user_id, 
                event_type="homeshopping_order_create", 
                event_data={
                    "order_id": order_result["order_id"], 
                    "product_id": order_data.product_id,
                    "quantity": order_data.quantity
                }
            )
        
        logger.info(f"홈쇼핑 주문 생성 완료: user_id={current_user.user_id}, order_id={order_result['order_id']}")
        return order_result
        
    except ValueError as e:
        logger.warning(f"홈쇼핑 주문 생성 실패 (검증 오류): user_id={current_user.user_id}, error={str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
        
    except Exception as e:
        logger.error(f"홈쇼핑 주문 생성 실패: user_id={current_user.user_id}, error={str(e)}")
        raise HTTPException(status_code=500, detail="주문 생성 중 오류가 발생했습니다.")


@router.get("/{homeshopping_order_id}/status", response_model=HomeshoppingOrderStatusResponse)
async def get_order_status(
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
    logger.info(f"홈쇼핑 주문 상태 조회 요청: user_id={current_user.user_id}, homeshopping_order_id={homeshopping_order_id}")
    
    try:
        # CRUD 계층에 주문 상태 조회 위임
        order_data = await get_hs_order_with_status(db, homeshopping_order_id)
        if not order_data:
            raise HTTPException(status_code=404, detail="해당 홈쇼핑 주문을 찾을 수 없습니다.")
        
        # 2. 현재 상태 조회
        current_status = await get_hs_current_status(db, homeshopping_order_id)
        
        # 기본 상태 조회 (ORDER_RECEIVED) - 항상 조회
        default_status_result = await db.execute(
            select(StatusMaster).where(StatusMaster.status_code == "ORDER_RECEIVED")
        )
        default_status = default_status_result.scalars().first()
        if not default_status:
            raise HTTPException(status_code=404, detail="기본 상태 정보를 찾을 수 없습니다.")
        
        if not current_status:
            # 기본 상태로 current_status 설정
            current_status = type('obj', (object,), {
                'status': default_status
            })()
        
        # 상태 변경 이력 조회
        status_history = await get_hs_order_status_history(db, homeshopping_order_id)
        
        # 주문 상태 조회 로그 기록
        if background_tasks:
            background_tasks.add_task(
                send_user_log, 
                user_id=current_user.user_id, 
                event_type="homeshopping_order_status_view", 
                event_data={
                    "homeshopping_order_id": homeshopping_order_id,
                    "current_status": current_status.status.status_code if current_status and current_status.status else "UNKNOWN"
                }
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
        logger.error(f"홈쇼핑 주문 상태 조회 실패: homeshopping_order_id={homeshopping_order_id}, error={str(e)}")
        raise HTTPException(status_code=500, detail="주문 상태 조회 중 오류가 발생했습니다.")


@router.get("/{homeshopping_order_id}/with-status", response_model=HomeshoppingOrderWithStatusResponse)
async def get_order_with_status(
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
    logger.info(f"홈쇼핑 주문과 상태 함께 조회 요청: user_id={current_user.user_id}, homeshopping_order_id={homeshopping_order_id}")
    
    try:
        order_data = await get_hs_order_with_status(db, homeshopping_order_id)
        if not order_data:
            raise HTTPException(status_code=404, detail="주문을 찾을 수 없습니다.")
        
        # 주문과 상태 함께 조회 로그 기록
        if background_tasks:
            background_tasks.add_task(
                send_user_log, 
                user_id=current_user.user_id, 
                event_type="homeshopping_order_with_status_view", 
                event_data={
                    "homeshopping_order_id": homeshopping_order_id,
                    "current_status": order_data.get("current_status", {}).get("status_code") if order_data.get("current_status") else None
                }
            )
        
        logger.info(f"홈쇼핑 주문과 상태 함께 조회 완료: user_id={current_user.user_id}, homeshopping_order_id={homeshopping_order_id}")
        
        return order_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"홈쇼핑 주문과 상태 함께 조회 실패: homeshopping_order_id={homeshopping_order_id}, error={str(e)}")
        raise HTTPException(status_code=500, detail="주문과 상태 함께 조회 중 오류가 발생했습니다.")


@router.post("/{homeshopping_order_id}/payment/confirm", response_model=PaymentConfirmResponse)
async def confirm_payment(
        homeshopping_order_id: int,
        current_user: UserOut = Depends(get_current_user),
        background_tasks: BackgroundTasks = None,
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    홈쇼핑 결제 확인(단건)
    - 현재 상태가 PAYMENT_REQUESTED인 해당 homeshopping_order_id의 주문을 PAYMENT_COMPLETED로 변경
    - 권한: 주문자 본인만 가능
    - 부가효과: 상태 변경 이력/알림 기록
    """
    logger.info(f"홈쇼핑 결제 확인 요청: user_id={current_user.user_id}, homeshopping_order_id={homeshopping_order_id}")
    
    try:
        # 1. 주문 존재 여부 확인
        order_data = await get_hs_order_with_status(db, homeshopping_order_id)
        if not order_data:
            raise HTTPException(status_code=404, detail="해당 홈쇼핑 주문을 찾을 수 없습니다.")
        
        # 2. 결제 확인 처리
        payment_result = await confirm_hs_payment(db, homeshopping_order_id, current_user.user_id)
        
        # 결제 확인 로그 기록
        if background_tasks:
            background_tasks.add_task(
                send_user_log, 
                user_id=current_user.user_id, 
                event_type="homeshopping_payment_confirm", 
                event_data={
                    "homeshopping_order_id": homeshopping_order_id,
                    "previous_status": payment_result["previous_status"],
                    "current_status": payment_result["current_status"]
                }
            )
        
        # 결제 확인 후 자동 상태 업데이트 시작
        if payment_result["current_status"] == "PAYMENT_COMPLETED":
            background_tasks.add_task(
                start_hs_auto_update,
                homeshopping_order_id=homeshopping_order_id,
                db_session_generator=get_maria_service_db()
            )
        
        logger.info(f"홈쇼핑 결제 확인 완료: user_id={current_user.user_id}, homeshopping_order_id={homeshopping_order_id}")
        
        return payment_result
        
    except ValueError as e:
        logger.warning(f"홈쇼핑 결제 확인 실패 (검증 오류): user_id={current_user.user_id}, homeshopping_order_id={homeshopping_order_id}, error={str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"홈쇼핑 결제 확인 실패: homeshopping_order_id={homeshopping_order_id}, error={str(e)}")
        raise HTTPException(status_code=500, detail="결제 확인 중 오류가 발생했습니다.")


@router.post("/{homeshopping_order_id}/auto-update", status_code=status.HTTP_200_OK)
async def start_auto_status_update_api(
    homeshopping_order_id: int,
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_maria_service_db)
):
    """
    특정 주문의 자동 상태 업데이트 시작 (테스트용)
    - 결제 완료 상태인 경우에만 자동 업데이트 시작
    """
    try:
        # 주문 존재 확인
        hs_order_result = await db.execute(
            select(HomeShoppingOrder).where(HomeShoppingOrder.homeshopping_order_id == homeshopping_order_id)
        )
        hs_order = hs_order_result.scalars().first()
        if not hs_order:
            raise HTTPException(status_code=404, detail="해당 홈쇼핑 주문을 찾을 수 없습니다.")
        
        # 디버깅: 직접 상태 이력 조회
        
        # 1단계: 상태 이력만 조회
        history_result = await db.execute(
            select(HomeShoppingOrderStatusHistory)
            .where(HomeShoppingOrderStatusHistory.homeshopping_order_id == homeshopping_order_id)
            .order_by(desc(HomeShoppingOrderStatusHistory.changed_at))
            .limit(1)
        )
        
        current_history = history_result.scalars().first()
        if not current_history:
            raise HTTPException(
                status_code=400, 
                detail="주문이 생성되었지만 아직 상태 이력이 없습니다."
            )
        
        logger.info(f"상태 이력 조회 성공: history_id={current_history.history_id}, status_id={current_history.status_id}")
        
        # 2단계: 상태 정보 조회
        status_result = await db.execute(
            select(StatusMaster).where(StatusMaster.status_id == current_history.status_id)
        )
        
        current_status = status_result.scalars().first()
        if not current_status:
            logger.error(f"상태 ID {current_history.status_id}에 해당하는 상태 정보를 찾을 수 없습니다.")
            raise HTTPException(
                status_code=400, 
                detail=f"상태 ID {current_history.status_id}에 해당하는 상태 정보를 찾을 수 없습니다."
            )
        
        logger.info(f"상태 정보 조회 성공: status_id={current_status.status_id}, status_code={current_status.status_code}, status_name={current_status.status_name}")
        
        # 결제 완료 상태가 아니면 에러 반환
        if current_status.status_code != "PAYMENT_COMPLETED":
            raise HTTPException(
                status_code=400, 
                detail=f"결제 완료 상태가 아닙니다. 현재 상태: {current_status.status_name} ({current_status.status_code})"
            )
        
        # 자동 상태 업데이트 시작
        if background_tasks:
            background_tasks.add_task(
                start_auto_hs_order_status_update,
                homeshopping_order_id=homeshopping_order_id
            )
        
        return {"message": f"주문 {homeshopping_order_id}의 자동 상태 업데이트가 시작되었습니다. (현재 상태: {current_status.status_name})"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"자동 상태 업데이트 시작 실패: homeshopping_order_id={homeshopping_order_id}, error={str(e)}")
        raise HTTPException(status_code=500, detail=f"서버 오류가 발생했습니다: {str(e)}")
