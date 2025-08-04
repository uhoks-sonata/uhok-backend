"""
주문 관련 API 엔드포인트 (JWT 인증, 각 기능별 주석 포함)
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from datetime import datetime

from services.order.crud.order_crud import (
    get_order_count_by_user,
    get_recent_orders_by_user,
    get_orders_by_user,
    get_order_detail
)
from services.order.schemas.order_schema import (
    OrderCountResponse,
    OrderRecentListResponse,
    OrderListResponse,
    OrderDetailResponse,
    OrderSummary,
    OrderProduct
)

from common.database.mariadb_service import get_maria_service_db
from common.dependencies import get_current_user

router = APIRouter(prefix="/api/orders", tags=["Orders"])

@router.get("/", response_model=OrderListResponse)
async def order_list(
    status: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    sort_by: str = Query("order_time"),
    sort_order: str = Query("desc"),
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1),
    db: AsyncSession = Depends(get_maria_service_db),
    user=Depends(get_current_user)
):
    """
    주문 목록(페이지네이션) 조회
    """
    total_count, orders = await get_orders_by_user(
        db, user.user_id, status, start_date, end_date,
        sort_by, sort_order, page, size
    )
    orders_list = [
        OrderSummary(
            order_id=o.order_id,
            product_name="(상품명)",  # 실제 상품명 join 필요
            product_image=None,       # 실제 상품 이미지 join 필요
            brand_name=None,          # 실제 브랜드명 join 필요
            order_date=o.order_time
        )
        for o in orders
    ]
    return OrderListResponse(
        total_count=total_count,
        page=page,
        size=size,
        orders=orders_list
    )


@router.get("/{order_id}", response_model=OrderDetailResponse)
async def order_detail(
    order_id: int,
    db: AsyncSession = Depends(get_maria_service_db),
    user=Depends(get_current_user)
):
    """
    주문 상세 조회
    """
    order = await get_order_detail(db, user.user_id, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="주문 내역이 없습니다.")

    # 실제로는 아래 product 정보 join, status, payment, shipping 등도 join 필요!
    products = [
        OrderProduct(
            product_id=1,
            product_name="(상품명)",  # 실제 상품명
            product_image=None,
            brand_name=None,
            quantity=1,
            price=order.price_id  # 임시, 실제 가격정보 필요
        )
    ]
    return OrderDetailResponse(
        order_id=order.order_id,
        order_date=order.order_time,
        total_price=order.price_id,   # 실제 결제금액 컬럼 사용
        status="배송완료",            # 실제 주문상태 컬럼 사용
        payment_method="신용카드",    # 실제 결제수단 컬럼 사용
        shipping_address="(주소)",    # 실제 배송주소 컬럼 사용
        products=products
    )


@router.get("/count", response_model=OrderCountResponse)
async def order_count(
    db: AsyncSession = Depends(get_maria_service_db),
    user=Depends(get_current_user)
):
    """
    로그인 사용자의 전체 주문 개수 조회
    """
    count = await get_order_count_by_user(db, user.user_id)
    return OrderCountResponse(order_count=count)


@router.get("/recent", response_model=OrderRecentListResponse)
async def recent_orders(
    days: int = Query(7, description="최근 조회 일수 (default=7)"),
    db: AsyncSession = Depends(get_maria_service_db),
    user=Depends(get_current_user)
):
    """
    최근 N일간 주문 내역 리스트 조회
    """
    orders = await get_recent_orders_by_user(db, user.user_id, days)
    orders_list = [
        OrderSummary(
            order_id=o.order_id,
            product_name="(상품명)",   # 실제 상품명 join 필요
            product_image=None,       # 실제 상품 이미지 join 필요
            brand_name=None,          # 실제 브랜드명 join 필요
            order_date=o.order_time
        )
        for o in orders
    ]
    return OrderRecentListResponse(orders=orders_list)

