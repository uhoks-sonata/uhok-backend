"""
주문 관련 API 엔드포인트 정의 (DB 연결: get_maria_service_db)
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from services.order.schemas.order_schema import OrderCreate, OrderRead
from services.order.crud.order_crud import create_order, get_order_by_id, cancel_order
from common.database.mariadb_service import get_maria_service_db

router = APIRouter(prefix="/api/orders", tags=["Orders"])

@router.post("/", response_model=OrderRead, status_code=status.HTTP_201_CREATED)
async def create_new_order(
    order_data: OrderCreate,
    db: AsyncSession = Depends(get_maria_service_db)
):
    """
    주문 생성 API
    """
    order = await create_order(db, order_data)
    return order

@router.get("/{order_id}", response_model=OrderRead)
async def read_order(
    order_id: int,
    db: AsyncSession = Depends(get_maria_service_db)
):
    """
    주문 단일 조회 API
    """
    order = await get_order_by_id(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="주문 내역이 없습니다.")
    return order

@router.patch("/{order_id}/cancel", response_model=OrderRead)
async def cancel_order_api(
    order_id: int,
    db: AsyncSession = Depends(get_maria_service_db)
):
    """
    주문 취소 API (cancel_time 갱신)
    """
    order = await cancel_order(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="주문 내역이 없습니다.")
    return order
