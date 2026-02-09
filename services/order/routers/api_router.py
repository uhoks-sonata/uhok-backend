"""Order API router entrypoint."""

from fastapi import APIRouter

from services.order.routers.common.detail_router import router as order_detail_router
from services.order.routers.common.list_router import router as order_list_router
from services.order.routers.homeshopping.order_status_router import router as hs_order_status_router
from services.order.routers.homeshopping.payment_router import router as hs_payment_router
from services.order.routers.kok.cart_router import router as kok_cart_router
from services.order.routers.kok.payment_router import router as kok_payment_router
from services.order.routers.kok.status_router import router as kok_status_router
from services.order.routers.payment.v1_router import router as payment_v1_router
from services.order.routers.payment.v2_router import router as payment_v2_router

router = APIRouter(tags=["Orders"])

router.include_router(order_list_router, prefix="/api/orders", tags=["Orders"])
router.include_router(order_detail_router, prefix="/api/orders", tags=["Orders"])

router.include_router(payment_v1_router, prefix="/api/orders/payment", tags=["Orders/Payment"])
router.include_router(payment_v2_router, prefix="/api/orders/payment", tags=["Orders/Payment"])

router.include_router(hs_order_status_router, prefix="/api/orders/homeshopping", tags=["HomeShopping Orders"])
router.include_router(hs_payment_router, prefix="/api/orders/homeshopping", tags=["HomeShopping Orders"])

router.include_router(kok_cart_router, prefix="/api/orders/kok", tags=["Kok Orders"])
router.include_router(kok_status_router, prefix="/api/orders/kok", tags=["Kok Orders"])
router.include_router(kok_payment_router, prefix="/api/orders/kok", tags=["Kok Orders"])
