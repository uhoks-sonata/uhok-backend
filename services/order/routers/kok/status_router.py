"""Kok order status API routes."""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.database.mariadb_service import get_maria_service_db
from common.dependencies import get_current_user
from common.log_utils import send_user_log
from common.http_dependencies import extract_http_info
from common.logger import get_logger
from services.order.models.order_base_model import Order
from services.order.models.kok.kok_order_model import KokOrder
from services.order.schemas.kok.status_schema import (
    KokOrderStatusUpdate,
    KokOrderStatusResponse,
    KokOrderWithStatusResponse,
)
from services.order.crud.kok.kok_order_status_crud import (
    update_kok_order_status,
    get_kok_order_with_current_status,
    get_kok_order_status_history,
)

logger = get_logger("kok_order_router")
router = APIRouter()

@router.patch("/{kok_order_id}/status", response_model=KokOrderStatusResponse)
async def update_kok_order_status_api(
    request: Request,
    kok_order_id: int,
    status_update: KokOrderStatusUpdate,
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_maria_service_db),
    user=Depends(get_current_user)
):
    """
    콕 주문 상태 업데이트
    
    Args:
        kok_order_id: 콕 주문 ID
        status_update: 상태 업데이트 요청 데이터
        background_tasks: 백그라운드 작업 관리자
        db: 데이터베이스 세션 (의존성 주입)
        user: 현재 인증된 사용자 (의존성 주입)
    
    Returns:
        KokOrderStatusResponse: 상태 업데이트 결과 (현재 상태 + 변경 이력)
        
    Note:
        - Router 계층: HTTP 요청/응답 처리, 파라미터 검증, 의존성 주입
        - 비즈니스 로직은 CRUD 계층에 위임
        - 주문자 본인만 상태 변경 가능 (권한 검증)
        - 상태 변경 시 자동으로 알림 생성
        - 상태 변경 이력 기록 및 사용자 행동 로그 기록
    """
    logger.debug(f"콕 주문 상태 업데이트 시작: user_id={user.user_id}, kok_order_id={kok_order_id}, new_status={status_update.status_code}")
    logger.info(f"콕 주문 상태 업데이트 요청: user_id={user.user_id}, kok_order_id={kok_order_id}, new_status={status_update.status_code}")
    
    try:
        # 사용자 권한 확인 - order 정보 명시적으로 로드
        kok_order_result = await db.execute(
            select(KokOrder).where(KokOrder.kok_order_id == kok_order_id)
        )
        kok_order = kok_order_result.scalars().first()
        if not kok_order:
            logger.warning(f"콕 주문을 찾을 수 없음: kok_order_id={kok_order_id}, user_id={user.user_id}")
            raise HTTPException(status_code=404, detail="주문을 찾을 수 없습니다.")
        logger.debug(f"콕 주문 조회 성공: kok_order_id={kok_order_id}")
        
        order_result = await db.execute(
            select(Order).where(Order.order_id == kok_order.order_id)
        )
        order = order_result.scalars().first()
        if not order or order.user_id != user.user_id:
            logger.warning(f"콕 주문 접근 권한 없음: kok_order_id={kok_order_id}, 요청 user_id={user.user_id}, 주문자 user_id={order.user_id if order else None}")
            raise HTTPException(status_code=403, detail="해당 주문에 대한 권한이 없습니다.")
        logger.debug(f"콕 주문 권한 확인 성공: kok_order_id={kok_order_id}, user_id={user.user_id}")
        
        # 상태 업데이트 (INSERT만 사용)
        updated_order = await update_kok_order_status(
            db, 
            kok_order_id, 
            status_update.new_status_code, 
            status_update.changed_by or user.user_id
        )
        logger.debug(f"콕 주문 상태 업데이트 성공: kok_order_id={kok_order_id}, new_status={status_update.new_status_code}")
        
        # 업데이트된 주문과 상태 정보 조회
        order_with_status = await get_kok_order_with_current_status(db, kok_order_id)
        if not order_with_status:
            logger.error(f"업데이트된 주문 상태 정보를 찾을 수 없음: kok_order_id={kok_order_id}")
            raise HTTPException(status_code=404, detail="주문을 찾을 수 없습니다.")
        
        kok_order, current_status, current_status_history = order_with_status
        logger.debug(f"주문 상태 정보 조회 성공: kok_order_id={kok_order_id}")
        
        # 상태 변경 이력 조회
        status_history = await get_kok_order_status_history(db, kok_order_id)
        logger.debug(f"상태 변경 이력 조회 완료: kok_order_id={kok_order_id}, history_count={len(status_history)}")
        
        # 상태 변경 로그 기록
        if background_tasks:
            http_info = extract_http_info(request, response_code=200)
            background_tasks.add_task(
                send_user_log,
                user_id=user.user_id,
                event_type="kok_order_status_update",
                event_data={
                    "kok_order_id": kok_order_id,
                    "new_status": status_update.new_status_code,
                    "changed_by": status_update.changed_by or user.user_id
                },
                **http_info  # HTTP 정보를 키워드 인자로 전달
            )
        
        logger.info(f"콕 주문 상태 업데이트 완료: user_id={user.user_id}, kok_order_id={kok_order_id}, new_status={status_update.new_status_code}")
        return KokOrderStatusResponse(
            kok_order_id=kok_order_id,
            current_status=current_status,
            status_history=status_history
        )
        
    except Exception as e:
        logger.error(f"콕 주문 상태 업데이트 실패: kok_order_id={kok_order_id}, user_id={user.user_id}, error={str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{kok_order_id}/status", response_model=KokOrderStatusResponse)
async def get_kok_order_status(
    request: Request,
    kok_order_id: int,
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_maria_service_db),
    user=Depends(get_current_user)
):
    """
    콕 주문 현재 상태 및 변경 이력 조회 (가장 최근 이력 사용)
    
    Args:
        kok_order_id: 콕 주문 ID
        background_tasks: 백그라운드 작업 관리자
        db: 데이터베이스 세션 (의존성 주입)
        user: 현재 인증된 사용자 (의존성 주입)
    
    Returns:
        KokOrderStatusResponse: 주문 상태 정보 (현재 상태 + 변경 이력)
        
    Note:
        - Router 계층: HTTP 요청/응답 처리, 파라미터 검증, 의존성 주입
        - 비즈니스 로직은 CRUD 계층에 위임
        - 주문자 본인만 조회 가능 (권한 검증)
        - 가장 최근 상태 이력을 기준으로 현재 상태 판단
        - 상태 변경 이력 전체 조회
    """
    logger.debug(f"콕 주문 상태 조회 시작: user_id={user.user_id}, kok_order_id={kok_order_id}")
    logger.info(f"콕 주문 상태 조회 요청: user_id={user.user_id}, kok_order_id={kok_order_id}")
    
    # 1. 주문 존재 여부 확인
    kok_order_result = await db.execute(
        select(KokOrder).where(KokOrder.kok_order_id == kok_order_id)
    )
    kok_order = kok_order_result.scalars().first()
    if not kok_order:
        logger.warning(f"콕 주문을 찾을 수 없음: kok_order_id={kok_order_id}, user_id={user.user_id}")
        raise HTTPException(status_code=404, detail="해당 콕 주문을 찾을 수 없습니다.")
    
    logger.debug(f"콕 주문 조회 성공: kok_order_id={kok_order_id}")
    
    # 2. 주문과 현재 상태 조회
    order_with_status = await get_kok_order_with_current_status(db, kok_order_id)
    if not order_with_status:
        logger.error(f"주문 상태 정보를 찾을 수 없음: kok_order_id={kok_order_id}")
        raise HTTPException(status_code=404, detail="주문 상태 정보를 찾을 수 없습니다.")
    
    _, current_status, current_status_history = order_with_status
    logger.debug(f"주문 상태 정보 조회 성공: kok_order_id={kok_order_id}")
    
    # 사용자 권한 확인 (주문자만 조회 가능) - order 정보 명시적으로 로드
    order_result = await db.execute(
        select(Order).where(Order.order_id == kok_order.order_id)
    )
    order = order_result.scalars().first()
    if not order or order.user_id != user.user_id:
        logger.warning(f"콕 주문 접근 권한 없음: kok_order_id={kok_order_id}, 요청 user_id={user.user_id}, 주문자 user_id={order.user_id if order else None}")
        raise HTTPException(status_code=403, detail="해당 주문에 대한 권한이 없습니다.")
    
    logger.debug(f"콕 주문 권한 확인 성공: kok_order_id={kok_order_id}, user_id={user.user_id}")
    
    # 상태 변경 이력 조회
    status_history = await get_kok_order_status_history(db, kok_order_id)
    logger.debug(f"상태 변경 이력 조회 완료: kok_order_id={kok_order_id}, history_count={len(status_history)}")
    
    # 상태 조회 로그 기록
    if background_tasks:
        http_info = extract_http_info(request, response_code=200)
        background_tasks.add_task(
            send_user_log,
            user_id=user.user_id,
            event_type="kok_order_status_view",
            event_data={"kok_order_id": kok_order_id},
            **http_info  # HTTP 정보를 키워드 인자로 전달
        )
    
    logger.info(f"콕 주문 상태 조회 완료: user_id={user.user_id}, kok_order_id={kok_order_id}")
    return KokOrderStatusResponse(
        kok_order_id=kok_order_id,
        current_status=current_status,
        status_history=status_history
    )


@router.get("/{kok_order_id}/with-status", response_model=KokOrderWithStatusResponse)
async def get_kok_order_with_status(
    request: Request,
    kok_order_id: int,
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_maria_service_db),
    user=Depends(get_current_user)
):
    """
    콕 주문과 현재 상태를 함께 조회
    """
    logger.debug(f"콕 주문 상세 조회 시작: user_id={user.user_id}, kok_order_id={kok_order_id}")
    logger.info(f"콕 주문 상세 조회 요청: user_id={user.user_id}, kok_order_id={kok_order_id}")
    
    # 1. 주문 존재 여부 확인
    kok_order_result = await db.execute(
        select(KokOrder).where(KokOrder.kok_order_id == kok_order_id)
    )
    kok_order = kok_order_result.scalars().first()
    if not kok_order:
        logger.warning(f"콕 주문을 찾을 수 없음: kok_order_id={kok_order_id}, user_id={user.user_id}")
        raise HTTPException(status_code=404, detail="해당 콕 주문을 찾을 수 없습니다.")
    
    logger.debug(f"콕 주문 조회 성공: kok_order_id={kok_order_id}")
    
    # 2. 주문과 현재 상태 조회
    order_with_status = await get_kok_order_with_current_status(db, kok_order_id)
    if not order_with_status:
        logger.error(f"주문 상태 정보를 찾을 수 없음: kok_order_id={kok_order_id}")
        raise HTTPException(status_code=404, detail="주문 상태 정보를 찾을 수 없습니다.")
    
    _, current_status, _ = order_with_status
    logger.debug(f"주문 상태 정보 조회 성공: kok_order_id={kok_order_id}")
    
    # 사용자 권한 확인 - order 정보 명시적으로 로드
    order_result = await db.execute(
        select(Order).where(Order.order_id == kok_order.order_id)
    )
    order = order_result.scalars().first()
    if not order or order.user_id != user.user_id:
        logger.warning(f"콕 주문 접근 권한 없음: kok_order_id={kok_order_id}, 요청 user_id={user.user_id}, 주문자 user_id={order.user_id if order else None}")
        raise HTTPException(status_code=403, detail="해당 주문에 대한 권한이 없습니다.")
    
    logger.debug(f"콕 주문 권한 확인 성공: kok_order_id={kok_order_id}, user_id={user.user_id}")
    
    # 주문과 상태 함께 조회 로그 기록
    if background_tasks:
        http_info = extract_http_info(request, response_code=200)
        background_tasks.add_task(
            send_user_log,
            user_id=user.user_id,
            event_type="kok_order_with_status_view",
            event_data={"kok_order_id": kok_order_id},
            **http_info  # HTTP 정보를 키워드 인자로 전달
        )
    
    logger.info(f"콕 주문 상세 조회 완료: user_id={user.user_id}, kok_order_id={kok_order_id}")
    return KokOrderWithStatusResponse(
        kok_order=kok_order,
        current_status=current_status
    )
