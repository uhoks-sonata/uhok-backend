"""HomeShopping payment/automation API routes."""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status, Request
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from common.database.mariadb_service import get_maria_service_db
from common.dependencies import get_current_user
from common.log_utils import send_user_log
from common.http_dependencies import extract_http_info
from common.logger import get_logger
from services.user.schemas.profile_schema import UserOut
from services.order.models.order_base_model import StatusMaster
from services.order.models.homeshopping.hs_order_model import (
    HomeShoppingOrder,
    HomeShoppingOrderStatusHistory,
)
from services.order.schemas.homeshopping.payment_schema import PaymentConfirmResponse
from services.order.crud.homeshopping.hs_order_flow_crud import (
    confirm_hs_payment,
    start_hs_auto_update,
)
from services.order.crud.homeshopping.hs_order_status_crud import (
    get_hs_order_with_status,
    start_auto_hs_order_status_update,
)

logger = get_logger("hs_order_router")
router = APIRouter()

@router.post("/{homeshopping_order_id}/payment/confirm", response_model=PaymentConfirmResponse)
async def confirm_payment(
        request: Request,
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
    logger.debug(f"홈쇼핑 결제 확인 시작: user_id={current_user.user_id}, homeshopping_order_id={homeshopping_order_id}")
    logger.info(f"홈쇼핑 결제 확인 요청: user_id={current_user.user_id}, homeshopping_order_id={homeshopping_order_id}")
    
    try:
        # 1. 주문 존재 여부 확인
        order_data = await get_hs_order_with_status(db, homeshopping_order_id)
        if not order_data:
            logger.warning(f"홈쇼핑 주문을 찾을 수 없음: homeshopping_order_id={homeshopping_order_id}, user_id={current_user.user_id}")
            raise HTTPException(status_code=404, detail="해당 홈쇼핑 주문을 찾을 수 없습니다.")
        
        # 2. 결제 확인 처리
        payment_result = await confirm_hs_payment(db, homeshopping_order_id, current_user.user_id)
        logger.debug(f"홈쇼핑 결제 확인 성공: homeshopping_order_id={homeshopping_order_id}, previous_status={payment_result['previous_status']}, current_status={payment_result['current_status']}")
        
        # 결제 확인 로그 기록
        if background_tasks:
            http_info = extract_http_info(request, response_code=200)
            background_tasks.add_task(
                send_user_log, 
                user_id=current_user.user_id, 
                event_type="homeshopping_payment_confirm", 
                event_data={
                    "homeshopping_order_id": homeshopping_order_id,
                    "previous_status": payment_result["previous_status"],
                    "current_status": payment_result["current_status"]
                },
                **http_info  # HTTP 정보를 키워드 인자로 전달
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
    logger.debug(f"홈쇼핑 자동 상태 업데이트 시작 요청: homeshopping_order_id={homeshopping_order_id}")
    logger.info(f"홈쇼핑 자동 상태 업데이트 시작 요청: homeshopping_order_id={homeshopping_order_id}")
    
    try:
        # 주문 존재 확인
        hs_order_result = await db.execute(
            select(HomeShoppingOrder).where(HomeShoppingOrder.homeshopping_order_id == homeshopping_order_id)
        )
        hs_order = hs_order_result.scalars().first()
        if not hs_order:
            logger.warning(f"홈쇼핑 주문을 찾을 수 없음: homeshopping_order_id={homeshopping_order_id}")
            raise HTTPException(status_code=404, detail="해당 홈쇼핑 주문을 찾을 수 없습니다.")
        
        logger.debug(f"홈쇼핑 주문 조회 성공: homeshopping_order_id={homeshopping_order_id}")
        
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
            logger.warning(f"상태 이력이 없음: homeshopping_order_id={homeshopping_order_id}")
            raise HTTPException(
                status_code=400, 
                detail="주문이 생성되었지만 아직 상태 이력이 없습니다."
            )
        
        logger.debug(f"상태 이력 조회 성공: history_id={current_history.history_id}, status_id={current_history.status_id}")
        
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
        
        logger.debug(f"상태 정보 조회 성공: status_id={current_status.status_id}, status_code={current_status.status_code}, status_name={current_status.status_name}")
        
        # 결제 완료 상태가 아니면 에러 반환
        if current_status.status_code != "PAYMENT_COMPLETED":
            logger.warning(f"결제 완료 상태가 아님: homeshopping_order_id={homeshopping_order_id}, current_status={current_status.status_code}")
            raise HTTPException(
                status_code=400, 
                detail=f"결제 완료 상태가 아닙니다. 현재 상태: {current_status.status_name} ({current_status.status_code})"
            )
        
        # 자동 상태 업데이트 시작
        if background_tasks:
            logger.debug(f"자동 상태 업데이트 백그라운드 작업 시작: homeshopping_order_id={homeshopping_order_id}")
            background_tasks.add_task(
                start_auto_hs_order_status_update,
                homeshopping_order_id=homeshopping_order_id
            )
        
        # logger.info(f"홈쇼핑 자동 상태 업데이트 완료: homeshopping_order_id={homeshopping_order_id}, current_status={current_status.status_code}")
        return {"message": f"주문 {homeshopping_order_id}의 자동 상태 업데이트가 시작되었습니다. (현재 상태: {current_status.status_name})"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"자동 상태 업데이트 시작 실패: homeshopping_order_id={homeshopping_order_id}, error={str(e)}")
        raise HTTPException(status_code=500, detail=f"서버 오류가 발생했습니다: {str(e)}")
