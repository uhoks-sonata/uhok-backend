from fastapi import APIRouter, Depends, Query, HTTPException, BackgroundTasks, status
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from common.database.mariadb_service import get_maria_service_db
from common.dependencies import get_current_user
from common.log_utils import send_user_log
from common.logger import get_logger

from services.user.schemas.user_schema import UserOut

from services.order.models.order_model import (
    Order, StatusMaster
)
from services.order.schemas.hs_order_schema import (
    HomeshoppingOrderRequest,
    HomeshoppingOrderResponse
)

from services.order.crud.hs_order_crud import create_homeshopping_order

router = APIRouter(prefix="/api/orders/homeshopping", tags=["HomeShopping Orders"])
logger = get_logger("hs_order_router")

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
    """
    logger.info(f"홈쇼핑 주문 생성 요청: user_id={current_user.user_id}, product_id={order_data.product_id}, quantity={order_data.quantity}")
    
    try:
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
