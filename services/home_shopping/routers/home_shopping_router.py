# """
# HomeShopping 주문 생성 API 라우터
# """
# from fastapi import APIRouter, Depends, status, BackgroundTasks
# from sqlalchemy.ext.asyncio import AsyncSession
# from services.order.schemas.order_schema import HomeShoppingOrderCreate, OrderRead
# from services.order.crud.order_crud import create_homeshopping_order
# from common.database.mariadb_service import get_maria_service_db
# from common.dependencies import get_current_user
# from common.log_utils import send_user_log
# 
# router = APIRouter(prefix="/api/home-shopping", tags=["Home Shopping"])
# 
# @router.post("/orders", response_model=OrderRead, status_code=status.HTTP_201_CREATED)
# async def create_homeshopping_order_api(
#     order_data: HomeShoppingOrderCreate,
#     background_tasks: BackgroundTasks = None,
#     db: AsyncSession = Depends(get_maria_service_db),
#     user=Depends(get_current_user)
# ):
#     order = await create_homeshopping_order(db, user.user_id, order_data.live_id)
#     
#     # 홈쇼핑 주문 생성 로그 기록
#     if background_tasks:
#         background_tasks.add_task(
#             send_user_log, 
#             user_id=user.user_id, 
#             event_type="homeshopping_order_create", 
#             event_data={
#                 "order_id": order.order_id,
#                 "live_id": order_data.live_id,
#                 "service_type": "home_shopping"
#             }
#         )
#     
#     return order

