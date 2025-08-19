"""
통합 주문 조회/상세/통계 API 라우터 (콕, HomeShopping 모두 지원)
"""
import requests
from fastapi import APIRouter, Depends, Query, HTTPException, BackgroundTasks
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta
from typing import List

from services.order.models.order_model import Order, KokOrder, HomeShoppingOrder

from services.order.schemas.order_schema import (
    OrderRead, 
    OrderCountResponse,
    PaymentConfirmV1Request,
    PaymentConfirmV1Response
)
from services.order.crud.order_crud import get_order_by_id, get_user_orders, calculate_order_total_price

from common.database.mariadb_service import get_maria_service_db
from common.dependencies import get_current_user
from common.log_utils import send_user_log
from common.logger import get_logger

from services.user.schemas.user_schema import UserOut

router = APIRouter(prefix="/api/orders", tags=["Orders"])
logger = get_logger("order_router")

@router.get("/", response_model=List[OrderRead])
async def list_orders(
    limit: int = Query(10, description="조회 개수"),
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_maria_service_db),
    user=Depends(get_current_user)
):
    """
    내 주문 리스트 (공통+서비스별 상세 포함)
    """
    order_list = await get_user_orders(db, user.user_id, limit, 0)
    
    # 주문 목록 조회 로그 기록
    if background_tasks:
        background_tasks.add_task(
            send_user_log, 
            user_id=user.user_id, 
            event_type="order_list_view", 
            event_data={"limit": limit, "order_count": len(order_list)}
        )
    
    return order_list


@router.get("/count", response_model=OrderCountResponse)
async def order_count(
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_maria_service_db),
    user=Depends(get_current_user)
):
    """
    로그인 사용자의 전체 주문 개수 조회
    """
    result = await db.execute(
        select(func.count()).select_from(Order).where(Order.user_id == user.user_id) # type: ignore
    )
    count = result.scalar()
    
    # 주문 개수 조회 로그 기록
    if background_tasks:
        background_tasks.add_task(
            send_user_log, 
            user_id=user.user_id, 
            event_type="order_count_view", 
            event_data={"order_count": count}
        )
    
    return OrderCountResponse(order_count=count)

@router.get("/recent", response_model=List[OrderRead])
async def recent_orders(
    days: int = Query(7, description="최근 조회 일수 (default=7)"),
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_maria_service_db),
    user=Depends(get_current_user)
):
    """
    최근 N일간 주문 내역 리스트 조회
    """
    since = datetime.now() - timedelta(days=days)
    
    # 최근 N일간 주문 조회 (get_user_orders 사용)
    order_list = await get_user_orders(db, user.user_id, 100, 0)  # 충분히 큰 limit
    
    # 날짜 필터링
    filtered_orders = [
        order for order in order_list 
        if order["order_time"] >= since
    ]
    
    # 최근 주문 조회 로그 기록
    if background_tasks:
        background_tasks.add_task(
            send_user_log, 
            user_id=user.user_id, 
            event_type="recent_orders_view", 
            event_data={"days": days, "order_count": len(filtered_orders)}
        )
    
    return filtered_orders


@router.get("/{order_id}", response_model=OrderRead)
async def read_order(
        order_id: int,
        background_tasks: BackgroundTasks = None,
        db: AsyncSession = Depends(get_maria_service_db),
        user=Depends(get_current_user)
):
    """
    단일 주문 조회 (공통+콕+HomeShopping 상세 포함)
    """
    order_data = await get_order_by_id(db, order_id)
    if not order_data or order_data["user_id"] != user.user_id:
        raise HTTPException(status_code=404, detail="주문 내역이 없습니다.")

    # 주문 상세 조회 로그 기록
    if background_tasks:
        background_tasks.add_task(
            send_user_log,
            user_id=user.user_id,
            event_type="order_detail_view",
            event_data={"order_id": order_id}
        )

    return order_data


@router.post("/{order_id}/payment/confirm/v1", response_model=PaymentConfirmV1Response)
async def confirm_payment_v1(
        order_id: int,
        payment_data: PaymentConfirmV1Request,
        current_user=Depends(get_current_user),
        background_tasks: BackgroundTasks = None,
        db: AsyncSession = Depends(get_maria_service_db)
):
    """
    주문 결제 확인 v1 (외부 결제 API 연동)
    - 192.168.101.206:9000/pay로 결제 요청을 보내고 외부 API 응답을 기다림
    - 외부 API가 응답하면 그때 결제 완료 처리
    - 해당 order_id의 모든 하위 주문들을 PAYMENT_COMPLETED로 변경
    - 권한: 주문자 본인만 가능
    - 부가효과: 상태 변경 이력/알림 기록
    """
    logger.info(f"주문 결제 확인 v1 요청: user_id={current_user.user_id}, order_id={order_id}")
    
    try:        
        # 주문 존재 여부 및 권한 확인
        order_data = await get_order_by_id(db, order_id)
        if not order_data or order_data["user_id"] != current_user.user_id:
            raise HTTPException(status_code=404, detail="주문 내역이 없습니다.")
        
        # 주문 총액 계산 (CRUD 함수 사용)
        total_order_price = await calculate_order_total_price(db, order_id)
        
        # 외부 결제 API 호출
        payment_request_data = {
            "order_id": f"order_{order_id}",
            "payment_amount": total_order_price
        }
        
        # POST 요청으로 결제 API 호출하고 응답을 기다림
        logger.info(f"외부 결제 API 호출 시작: order_id={order_id}")
        response = requests.post(
            "http://192.168.101.206:9000/pay",
            json=payment_request_data,
            headers={"Content-Type": "application/json"},
            timeout=60  # 60초 타임아웃으로 외부 API 응답을 충분히 기다림
        )
        
        # 외부 API 응답 확인
        if response.status_code != 200:
            logger.error(f"외부 결제 API 호출 실패: order_id={order_id}, status_code={response.status_code}, response={response.text}")
            raise HTTPException(status_code=400, detail=f"외부 결제 API 호출 실패: {response.status_code}")
        
        # 외부 API 응답 파싱
        payment_result = response.json()
        logger.info(f"외부 결제 API 응답 수신: order_id={order_id}, response={payment_result}")
        
        # 외부 API가 응답했으므로 이제 결제 완료 처리 진행
        # TODO: 여기서 order_id에 해당하는 모든 하위 주문들의 상태를 PAYMENT_COMPLETED로 변경하는 로직 필요
        # 현재는 외부 API 응답만 확인하고 성공 응답을 반환
        
        # 결제 확인 로그 기록
        if background_tasks:
            background_tasks.add_task(
                send_user_log, 
                user_id=current_user.user_id, 
                event_type="order_payment_confirm_v1", 
                event_data={
                    "order_id": order_id,
                    "external_payment_id": payment_result.get("payment_id"),
                    "external_response": payment_result
                }
            )
        
        # 외부 API 응답을 기반으로 응답 데이터 구성
        confirm_response = PaymentConfirmV1Response(
            payment_id=payment_result.get("payment_id", f"payment_{order_id}"),
            order_id=payment_result.get("order_id", f"order_{order_id}"),
            status=payment_result.get("status", "PAYMENT_COMPLETED"),
            payment_amount=payment_result.get("payment_amount", 0),  # 외부 API에서 받은 금액 사용
            method=payment_result.get("method", "EXTERNAL_API"),
            confirmed_at=datetime.now(),
            order_id_internal=order_id
        )
        
        logger.info(f"주문 결제 확인 v1 완료: user_id={current_user.user_id}, order_id={order_id}, external_payment_id={payment_result.get('payment_id')}")
        
        return confirm_response
        
    except requests.exceptions.Timeout:
        logger.error(f"외부 결제 API 타임아웃: order_id={order_id}")
        raise HTTPException(status_code=408, detail="외부 결제 서비스 응답 시간 초과")
    except requests.exceptions.RequestException as e:
        logger.error(f"외부 결제 API 연결 실패: order_id={order_id}, error={str(e)}")
        raise HTTPException(status_code=503, detail="외부 결제 서비스에 연결할 수 없습니다")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"주문 결제 확인 v1 실패: order_id={order_id}, error={str(e)}")
        raise HTTPException(status_code=500, detail="결제 확인 중 오류가 발생했습니다.")
