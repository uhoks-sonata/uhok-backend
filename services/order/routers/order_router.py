"""
통합 주문 조회/상세/통계 API 라우터 (콕, HomeShopping 모두 지원)
Router 계층: HTTP 요청/응답 처리, 파라미터 검증, 의존성 주입만 담당
비즈니스 로직은 CRUD 계층에 위임, 직접 DB 처리(트랜잭션)는 하지 않음
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
    RecentOrderItem,
    RecentOrdersResponse,
    OrderGroup,
    OrderGroupItem,
    OrdersListResponse
)
from services.order.crud.order_crud import get_order_by_id, get_user_orders, get_delivery_info

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
    Router 계층: HTTP 요청/응답 처리, 파라미터 검증, 의존성 주입
    비즈니스 로직은 CRUD 계층에 위임
    """
    # CRUD 계층에 주문 조회 위임
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
            try:
                # CRUD 계층에 배송 정보 조회 위임
                delivery_status, delivery_date = await get_delivery_info(db, "kok", kok_order.kok_order_id)
            except Exception as e:
                logger.warning(f"콕 주문 배송 정보 조회 실패: kok_order_id={kok_order.kok_order_id}, error={str(e)}")
                delivery_status, delivery_date = "상태 조회 실패", "배송 정보 없음"
            
            # 상품명이 None인 경우 기본값 제공
            product_name = getattr(kok_order, "product_name", None)
            if product_name is None:
                product_name = f"콕 상품 (ID: {kok_order.kok_product_id})"
            
            item = OrderGroupItem(
                product_name=product_name,
                product_image=getattr(kok_order, "product_image", None),
                price=getattr(kok_order, "order_price", 0) or 0,  # order_price 필드 사용
                quantity=getattr(kok_order, "quantity", 1),
                delivery_status=delivery_status,
                delivery_date=delivery_date,
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
            try:
                # CRUD 계층에 배송 정보 조회 위임
                delivery_status, delivery_date = await get_delivery_info(db, "homeshopping", hs_order.homeshopping_order_id)
            except Exception as e:
                logger.warning(f"홈쇼핑 주문 배송 정보 조회 실패: homeshopping_order_id={hs_order.homeshopping_order_id}, error={str(e)}")
                delivery_status, delivery_date = "상태 조회 실패", "배송 정보 없음"
            
            # 상품명이 None인 경우 기본값 제공
            product_name = getattr(hs_order, "product_name", None)
            if product_name is None:
                product_name = f"홈쇼핑 상품 (ID: {hs_order.product_id})"
            
            item = OrderGroupItem(
                product_name=product_name,
                product_image=getattr(hs_order, "product_image", None),
                price=getattr(hs_order, "order_price", 0) or 0,  # order_price 필드 사용
                quantity=getattr(hs_order, "quantity", 1),
                delivery_status=delivery_status,
                delivery_date=delivery_date,
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
            event_type="orders_list_view", 
            event_data={"limit": limit, "order_count": len(order_groups)}
        )
    
    return OrdersListResponse(
        limit=limit,
        total_count=len(order_groups),
        order_groups=order_groups
    )


@router.get("/count", response_model=OrderCountResponse)
async def get_order_count(
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_maria_service_db),
    user=Depends(get_current_user)
):
    """
    내 주문 개수 조회 (전체)
    Router 계층: HTTP 요청/응답 처리, 파라미터 검증, 의존성 주입
    비즈니스 로직은 CRUD 계층에 위임
    """
    # CRUD 계층에 주문 조회 위임
    order_list = await get_user_orders(db, user.user_id, limit=1000, offset=0)
    
    # 주문 개수 조회 로그 기록
    if background_tasks:
        background_tasks.add_task(
            send_user_log, 
            user_id=user.user_id, 
            event_type="order_count_view", 
            event_data={"order_count": len(order_list)}
        )
    
    return OrderCountResponse(
        order_count=len(order_list)
    )


@router.get("/recent", response_model=RecentOrdersResponse)
async def get_recent_orders(
    days: int = Query(7, description="조회 기간 (일)"),
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_maria_service_db),
    user=Depends(get_current_user)
):
    """
    최근 주문 조회 (최근 N일)
    Router 계층: HTTP 요청/응답 처리, 파라미터 검증, 의존성 주입
    비즈니스 로직은 CRUD 계층에 위임
    """
    # CRUD 계층에 주문 조회 위임
    order_list = await get_user_orders(db, user.user_id, limit=1000, offset=0)
    
    # 최근 N일 필터링
    cutoff_date = datetime.now() - timedelta(days=days)
    filtered_orders = [
        order for order in order_list 
        if order["order_time"] >= cutoff_date
    ]
    
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
            try:
                # CRUD 계층에 배송 정보 조회 위임
                delivery_status, delivery_date = await get_delivery_info(db, "kok", kok_order.kok_order_id)
            except Exception as e:
                logger.warning(f"콕 주문 배송 정보 조회 실패: kok_order_id={kok_order.kok_order_id}, error={str(e)}")
                delivery_status, delivery_date = "상태 조회 실패", "배송 정보 없음"
            
            # 상품명이 None인 경우 기본값 제공
            product_name = getattr(kok_order, "product_name", None)
            if product_name is None:
                product_name = f"콕 상품 (ID: {kok_order.kok_product_id})"
            
            item = RecentOrderItem(
                order_id=order["order_id"],
                order_number=order_number,
                order_date=order_date,
                delivery_status=delivery_status,
                delivery_date=delivery_date,
                product_name=product_name,
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
            try:
                # CRUD 계층에 배송 정보 조회 위임
                delivery_status, delivery_date = await get_delivery_info(db, "homeshopping", hs_order.homeshopping_order_id)
            except Exception as e:
                logger.warning(f"홈쇼핑 주문 배송 정보 조회 실패: homeshopping_order_id={hs_order.homeshopping_order_id}, error={str(e)}")
                delivery_status, delivery_date = "상태 조회 실패", "배송 정보 없음"
            
            # 상품명이 None인 경우 기본값 제공
            product_name = getattr(hs_order, "product_name", None)
            if product_name is None:
                product_name = f"홈쇼핑 상품 (ID: {hs_order.product_id})"
            
            item = RecentOrderItem(
                order_id=order["order_id"],
                order_number=order_number,
                order_date=order_date,
                delivery_status=delivery_status,
                delivery_date=delivery_date,
                product_name=product_name,
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
    Router 계층: HTTP 요청/응답 처리, 파라미터 검증, 의존성 주입
    비즈니스 로직은 CRUD 계층에 위임
    """
    # CRUD 계층에 주문 조회 위임
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
