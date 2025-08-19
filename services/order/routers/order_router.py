"""
통합 주문 조회/상세/통계 API 라우터 (콕, HomeShopping 모두 지원)
"""
import requests
import asyncio
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
    PaymentConfirmV1Response,
    RecentOrderItem,
    RecentOrdersResponse,
    OrderGroup,
    OrderGroupItem,
    OrdersListResponse
)
from services.order.crud.order_crud import get_order_by_id, get_user_orders, calculate_order_total_price

from common.database.mariadb_service import get_maria_service_db
from common.dependencies import get_current_user
from common.log_utils import send_user_log
from common.logger import get_logger

from services.user.schemas.user_schema import UserOut

router = APIRouter(prefix="/api/orders", tags=["Orders"])
logger = get_logger("order_router")

@router.get("/", response_model=OrdersListResponse)
async def list_orders(
    limit: int = Query(10, description="조회 개수"),
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_maria_service_db),
    user=Depends(get_current_user)
):
    """
    내 주문 리스트 (order_id로 그룹화하여 표시)
    """
    order_list = await get_user_orders(db, user.user_id, limit, 0)
    
    # order_id별로 그룹화
    order_groups = []
    
    for order in order_list:
        # 주문 번호 생성 (예: 00020250725309)
        order_number = f"{order['order_id']:012d}"
        
        # 주문 날짜 포맷팅 (예: 2025. 7. 25) - Windows 호환
        month = order["order_time"].month
        day = order["order_time"].day
        order_date = f"{order['order_time'].year}. {month}. {day}"
        
        # 주문 상품 아이템들 수집
        order_items = []
        total_amount = 0
        
        # 콕 주문 처리
        for kok_order in order.get("kok_orders", []):
            item = OrderGroupItem(
                product_name=kok_order.get("product_name", "상품명 없음"),
                product_image=kok_order.get("product_image"),
                price=kok_order.get("price", 0),
                quantity=kok_order.get("quantity", 1),
                delivery_status="배송완료",  # 실제 배송 상태로 변경 필요
                delivery_date="7/28(월) 도착",  # 실제 도착일로 변경 필요
                recipe_related=True,  # 콕 주문은 레시피 관련
                recipe_title=kok_order.get("recipe_title"),
                recipe_rating=kok_order.get("rating", 5.0),
                recipe_scrap_count=kok_order.get("scrap_count", 5),
                recipe_description=kok_order.get("description", "아무도 모르게 다가온 이별에 대면했을 때 또다시 혼자 가 되는 게 두려워 외면했었네 꿈에도 그리던..."),
                ingredients_owned=3,  # 실제 보유 재료 수로 변경 필요
                total_ingredients=8   # 실제 총 재료 수로 변경 필요
            )
            order_items.append(item)
            total_amount += kok_order.get("price", 0) * kok_order.get("quantity", 1)
        
        # 홈쇼핑 주문 처리
        for hs_order in order.get("homeshopping_orders", []):
            item = OrderGroupItem(
                product_name=hs_order.get("product_name", "상품명 없음"),
                product_image=hs_order.get("product_image"),
                price=hs_order.get("price", 0),
                quantity=hs_order.get("quantity", 1),
                delivery_status="배송완료",  # 실제 배송 상태로 변경 필요
                delivery_date="7/28(월) 도착",  # 실제 도착일로 변경 필요
                recipe_related=False,  # 홈쇼핑 주문은 일반 상품
                recipe_title=None,
                recipe_rating=None,
                recipe_scrap_count=None,
                recipe_description=None,
                ingredients_owned=None,
                total_ingredients=None
            )
            order_items.append(item)
            total_amount += hs_order.get("price", 0) * hs_order.get("quantity", 1)
        
        # 주문 그룹 생성
        order_group = OrderGroup(
            order_id=order["order_id"],
            order_number=order_number,
            order_date=order_date,
            total_amount=total_amount,
            item_count=len(order_items),
            items=order_items
        )
        order_groups.append(order_group)
    
    # 주문 목록 조회 로그 기록
    if background_tasks:
        background_tasks.add_task(
            send_user_log, 
            user_id=user.user_id, 
            event_type="order_list_view", 
            event_data={"limit": limit, "order_count": len(order_groups)}
        )
    
    return OrdersListResponse(
        limit=limit,
        total_count=len(order_groups),
        order_groups=order_groups
    )


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

@router.get("/recent", response_model=RecentOrdersResponse)
async def recent_orders(
    days: int = Query(7, description="최근 조회 일수 (default=7)"),
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_maria_service_db),
    user=Depends(get_current_user)
):
    """
    최근 N일간 주문 내역 리스트 조회 (이미지 형태로 표시)
    """
    since = datetime.now() - timedelta(days=days)
    
    # 최근 N일간 주문 조회 (get_user_orders 사용)
    order_list = await get_user_orders(db, user.user_id, 100, 0)  # 충분히 큰 limit
    
    # 날짜 필터링
    filtered_orders = [
        order for order in order_list 
        if order["order_time"] >= since
    ]
    
    # 이미지 형태에 맞는 데이터 변환
    recent_order_items = []
    
    for order in filtered_orders:
        # 주문 번호 생성 (예: 00020250725309)
        order_number = f"{order['order_id']:012d}"
        
        # 주문 날짜 포맷팅 (예: 2025. 7. 25) - Windows 호환
        month = order["order_time"].month
        day = order["order_time"].day
        order_date = f"{order['order_time'].year}. {month}. {day}"
        
        # 콕 주문 처리
        for kok_order in order.get("kok_orders", []):
            item = RecentOrderItem(
                order_id=order["order_id"],
                order_number=order_number,
                order_date=order_date,
                delivery_status="배송완료",  # 실제 배송 상태로 변경 필요
                delivery_date="7/28(월) 도착",  # 실제 도착일로 변경 필요
                product_name=kok_order.get("product_name", "상품명 없음"),
                product_image=kok_order.get("product_image"),
                price=kok_order.get("price", 0),
                quantity=kok_order.get("quantity", 1),
                recipe_related=True,  # 콕 주문은 레시피 관련
                recipe_title=kok_order.get("recipe_title"),
                recipe_rating=kok_order.get("rating", 5.0),
                recipe_scrap_count=kok_order.get("scrap_count", 5),
                recipe_description=kok_order.get("description", "아무도 모르게 다가온 이별에 대면했을 때 또다시 혼자 가 되는 게 두려워 외면했었네 꿈에도 그리던..."),
                ingredients_owned=3,  # 실제 보유 재료 수로 변경 필요
                total_ingredients=8   # 실제 총 재료 수로 변경 필요
            )
            recent_order_items.append(item)
        
        # 홈쇼핑 주문 처리
        for hs_order in order.get("homeshopping_orders", []):
            item = RecentOrderItem(
                order_id=order["order_id"],
                order_number=order_number,
                order_date=order_date,
                delivery_status="배송완료",  # 실제 배송 상태로 변경 필요
                delivery_date="7/28(월) 도착",  # 실제 도착일로 변경 필요
                product_name=hs_order.get("product_name", "상품명 없음"),
                product_image=hs_order.get("product_image"),
                price=hs_order.get("price", 0),
                quantity=hs_order.get("quantity", 1),
                recipe_related=False,  # 홈쇼핑 주문은 일반 상품
                recipe_title=None,
                recipe_rating=None,
                recipe_scrap_count=None,
                recipe_description=None,
                ingredients_owned=None,
                total_ingredients=None
            )
            recent_order_items.append(item)
    
    # 최근 주문 조회 로그 기록
    if background_tasks:
        background_tasks.add_task(
            send_user_log, 
            user_id=user.user_id, 
            event_type="recent_orders_view", 
            event_data={"days": days, "order_count": len(recent_order_items)}
        )
    
    return RecentOrdersResponse(
        days=days,
        order_count=len(recent_order_items),
        orders=recent_order_items
    )


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
            timeout=120  # 60초 → 120초(2분)로 증가하여 외부 API 응답을 충분히 기다림
        )
        
        # 외부 API 응답 확인
        if response.status_code != 200:
            logger.error(f"외부 결제 API 호출 실패: order_id={order_id}, status_code={response.status_code}, response={response.text}")
            raise HTTPException(status_code=400, detail=f"외부 결제 API 호출 실패: {response.status_code}")
        
        # 외부 API 응답 파싱
        payment_result = response.json()
        payment_id = payment_result.get("payment_id")
        logger.info(f"외부 결제 API 응답 수신: order_id={order_id}, payment_id={payment_id}, response={payment_result}")
        
        # 결제 상태 확인 (폴링 방식)
        max_retries = 30
        retry_count = 0
        
        logger.info(f"결제 상태 확인 시작: payment_id={payment_id}")
        
        while retry_count < max_retries:
            try:
                status_response = requests.get(
                    f"http://192.168.101.206:9000/payment-status/{payment_id}",
                    timeout=30  # 10초 → 30초로 증가
                )
                
                if status_response.status_code == 200:
                    payment_status = status_response.json()
                    logger.info(f"결제 상태 확인 결과: payment_id={payment_id}, status={payment_status['status']}, retry={retry_count}")
                    
                    if payment_status["status"] == "PAYMENT_COMPLETED":
                        # 결제 완료 확인됨 - 상태 변경 진행
                        logger.info(f"결제 완료 확인됨: payment_id={payment_id}")
                        break
                    elif payment_status["status"] == "PAYMENT_FAILED":
                        logger.error(f"결제 실패: payment_id={payment_id}, status={payment_status['status']}")
                        raise HTTPException(status_code=400, detail="결제가 실패했습니다")
                    elif payment_status["status"] == "PENDING":
                        # 점진적 대기 시간 증가 (10초부터 시작해서 최대 60초)
                        wait_time = min(10 + (retry_count * 5), 60)
                        logger.info(f"결제 처리 중: payment_id={payment_id}, retry={retry_count + 1}/{max_retries}, wait={wait_time}초")
                        await asyncio.sleep(wait_time)
                        retry_count += 1
                        continue
                    else:
                        # 예상치 못한 상태
                        logger.warning(f"예상치 못한 결제 상태: payment_id={payment_id}, status={payment_status['status']}")
                        retry_count += 1
                        continue
                        
                else:
                    logger.error(f"결제 상태 확인 실패: payment_id={payment_id}, status_code={status_response.status_code}")
                    retry_count += 1
                    continue
                    
            except requests.exceptions.RequestException as e:
                logger.error(f"결제 상태 확인 중 오류: payment_id={payment_id}, error={str(e)}")
                retry_count += 1
                continue
        
        if retry_count >= max_retries:
            logger.error(f"결제 상태 확인 시간 초과: payment_id={payment_id}, max_retries={max_retries}")
            raise HTTPException(status_code=408, detail="결제 상태 확인 시간 초과 (최대 30회 시도)")
        
        # 결제 완료 확인 후 상태 변경 진행
        logger.info(f"결제 완료 확인됨, 상태 변경 시작: order_id={order_id}")
        
        # 1. 콕 주문 상태 변경
        kok_orders = order_data.get("kok_orders", [])
        for kok_order in kok_orders:
            try:
                from services.order.crud.kok_order_crud import update_kok_order_status
                await update_kok_order_status(
                    db=db,
                    kok_order_id=kok_order.kok_order_id,
                    new_status_code="PAYMENT_COMPLETED",
                    changed_by=current_user.user_id
                )
                logger.info(f"콕 주문 상태 변경 완료: kok_order_id={kok_order.kok_order_id}, status=PAYMENT_COMPLETED")
            except Exception as e:
                logger.error(f"콕 주문 상태 변경 실패: kok_order_id={kok_order.kok_order_id}, error={str(e)}")
                # 개별 주문 상태 변경 실패해도 전체 프로세스는 계속 진행
        
        # 2. 홈쇼핑 주문 상태 변경
        homeshopping_orders = order_data.get("homeshopping_orders", [])
        for hs_order in homeshopping_orders:
            try:
                from services.order.crud.hs_order_crud import update_hs_order_status
                await update_hs_order_status(
                    db=db,
                    homeshopping_order_id=hs_order.homeshopping_order_id,
                    new_status_code="PAYMENT_COMPLETED",
                    changed_by=current_user.user_id
                )
                logger.info(f"홈쇼핑 주문 상태 변경 완료: homeshopping_order_id={hs_order.homeshopping_order_id}, status=PAYMENT_COMPLETED")
            except Exception as e:
                logger.error(f"홈쇼핑 주문 상태 변경 실패: homeshopping_order_id={hs_order.homeshopping_order_id}, error={str(e)}")
                # 개별 주문 상태 변경 실패해도 전체 프로세스는 계속 진행
        
        logger.info(f"모든 하위 주문 상태 변경 완료: order_id={order_id}, kok_count={len(kok_orders)}, hs_count={len(homeshopping_orders)}")
        
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
