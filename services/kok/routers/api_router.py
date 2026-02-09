"""KOK API router entrypoint."""

from fastapi import APIRouter

from services.kok.routers.cache_router import router as cache_router
from services.kok.routers.cart_router import router as cart_router
from services.kok.routers.likes_router import router as likes_router
from services.kok.routers.listing_router import router as listing_router
from services.kok.routers.product_router import router as product_router
from services.kok.routers.recommendation_router import router as recommendation_router
from services.kok.routers.search_router import router as search_router

router = APIRouter(prefix="/api/kok", tags=["Kok"])

router.include_router(listing_router, tags=["Kok"])
router.include_router(product_router, tags=["Kok"])
router.include_router(search_router, tags=["Kok"])
router.include_router(likes_router, tags=["Kok"])
router.include_router(cart_router, tags=["Kok"])
router.include_router(recommendation_router, tags=["Kok"])
router.include_router(cache_router, tags=["Kok"])
