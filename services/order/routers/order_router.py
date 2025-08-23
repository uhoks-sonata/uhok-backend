"""
통합 주문 조회/상세/통계 API 라우터 (콕, HomeShopping 모두 지원)
"""
import requests
import asyncio
from fastapi import APIRouter, Depends, Query, HTTPException, BackgroundTasks, status, Header
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta
from typing import List

from services.order.models.order_model import Order

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
from services.order.crud.order_crud import get_order_by_id, get_user_orders, confirm_payment_and_update_status_v1

from common.database.mariadb_service import get_maria_service_db
from common.dependencies import get_current_user
from common.log_utils import send_user_log
from common.logger import get_logger


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
        # 주문 번호는 order_id 그대로 사용
        order_number = str(order['order_id'])
        
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
                product_name=getattr(kok_order, "product_name", f"콕 상품 (ID: {kok_order.kok_product_id})"),
                product_image=getattr(kok_order, "product_image", None),
                price=getattr(kok_order, "order_price", 0) or 0,  # order_price 필드 사용
                quantity=getattr(kok_order, "quantity", 1),
                delivery_status="배송완료",  # 실제 배송 상태로 변경 필요
                delivery_date="7/28(월) 도착",  # 실제 도착일로 변경 필요
                recipe_related=True,  # 콕 주문은 레시피 관련
                recipe_title=getattr(kok_order, "recipe_title", None),
                recipe_rating=getattr(kok_order, "recipe_rating", 0.0),
                recipe_scrap_count=getattr(kok_order, "recipe_scrap_count", 0),
                recipe_description=getattr(kok_order, "recipe_description", None),
                ingredients_owned=getattr(kok_order, "ingredients_owned", 0),
                total_ingredients=getattr(kok_order, "total_ingredients", 0)
            )
            order_items.append(item)
            total_amount += (getattr(kok_order, "order_price", 0) or 0) * getattr(kok_order, "quantity", 1)
        
        # 홈쇼핑 주문 처리
        for hs_order in order.get("homeshopping_orders", []):
            item = OrderGroupItem(
                product_name=getattr(hs_order, "product_name", f"홈쇼핑 상품 (ID: {hs_order.product_id})"),
                product_image=getattr(hs_order, "product_image", None),
                price=getattr(hs_order, "order_price", 0) or 0,  # order_price 필드 사용
                quantity=getattr(hs_order, "quantity", 1),
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
            total_amount += (getattr(hs_order, "order_price", 0) or 0) * getattr(hs_order, "quantity", 1)
        
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
                product_name=getattr(kok_order, "product_name", f"콕 상품 (ID: {kok_order.kok_product_id})"),
                product_image=getattr(kok_order, "product_image", None),
                price=getattr(kok_order, "order_price", 0) or 0,  # order_price 필드 사용
                quantity=getattr(kok_order, "quantity", 1),
                recipe_related=True,  # 콕 주문은 레시피 관련
                recipe_title=getattr(kok_order, "recipe_title", None),
                recipe_rating=getattr(kok_order, "recipe_rating", 0.0),
                recipe_scrap_count=getattr(kok_order, "recipe_scrap_count", 0),
                recipe_description=getattr(kok_order, "recipe_description", None),
                ingredients_owned=getattr(kok_order, "ingredients_owned", 0),
                total_ingredients=getattr(kok_order, "total_ingredients", 0)
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
                product_name=getattr(hs_order, "product_name", f"홈쇼핑 상품 (ID: {hs_order.product_id})"),
                product_image=getattr(hs_order, "product_image", None),
                price=getattr(hs_order, "order_price", 0) or 0,  # order_price 필드 사용
                quantity=getattr(hs_order, "quantity", 1),
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


@router.post("/{order_id}/payment/confirm/v1", response_model=PaymentConfirmV1Response, status_code=status.HTTP_200_OK)
async def confirm_payment_v1(
    order_id: int,
    payment_data: PaymentConfirmV1Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_maria_service_db),
    current_user=Depends(get_current_user),
):
    """
    주문 결제 확인 v1 (외부 결제 API 응답을 기다리는 방식)
    - 외부 결제 생성 → payment_id 수신 → 결제 상태 폴링(PENDING→완료/실패)
    - 완료 시: 해당 order_id 하위 주문들을 PAYMENT_COMPLETED로 갱신(트랜잭션)
    - 실패/타임아웃 시: 적절한 HTTPException 반환
    """
    return await confirm_payment_and_update_status_v1(
        db=db,
        order_id=order_id,
        user_id=current_user.user_id,
        payment_data=payment_data,
        background_tasks=background_tasks,
    )
