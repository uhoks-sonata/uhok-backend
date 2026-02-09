"""HomeShopping API router entrypoint."""

from fastapi import APIRouter

from services.homeshopping.routers.likes_router import router as likes_router
from services.homeshopping.routers.notification_router import router as notification_router
from services.homeshopping.routers.product_router import router as product_router
from services.homeshopping.routers.recommendation_router import router as recommendation_router
from services.homeshopping.routers.schedule_router import router as schedule_router
from services.homeshopping.routers.search_router import router as search_router
from services.homeshopping.routers.stream_router import router as stream_router

router = APIRouter(prefix="/api/homeshopping", tags=["HomeShopping"])

router.include_router(schedule_router, tags=["HomeShopping"])
router.include_router(stream_router, tags=["HomeShopping"])
router.include_router(product_router, tags=["HomeShopping"])
router.include_router(recommendation_router, tags=["HomeShopping"])
router.include_router(search_router, tags=["HomeShopping"])
router.include_router(likes_router, tags=["HomeShopping"])
router.include_router(notification_router, tags=["HomeShopping"])
