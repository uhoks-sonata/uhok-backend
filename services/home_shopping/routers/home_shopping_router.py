"""
HomeShopping 주문 생성 API 라우터
"""
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from services.order.schemas.order_schema import HomeShoppingOrderCreate, OrderRead
from services.order.crud.order_crud import create_homeshopping_order
from common.database.mariadb_service import get_maria_service_db
from common.dependencies import get_current_user

router = APIRouter(prefix="/api/home-shopping", tags=["Home Shopping"])

@router.post("/orders", response_model=OrderRead, status_code=status.HTTP_201_CREATED)
async def create_homeshopping_order_api(
    order_data: HomeShoppingOrderCreate,
    db: AsyncSession = Depends(get_maria_service_db),
    user=Depends(get_current_user)
):
    order = await create_homeshopping_order(db, user.user_id, order_data.live_id)
    return order

