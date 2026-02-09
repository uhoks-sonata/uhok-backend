"""Recipe API router entrypoint."""

from fastapi import APIRouter

from services.recipe.routers.detail_router import router as detail_router
from services.recipe.routers.product_router import router as product_router
from services.recipe.routers.rating_router import router as rating_router
from services.recipe.routers.recommendation_router import router as recommendation_router
from services.recipe.routers.search_router import router as search_router
from services.recipe.routers.status_router import router as status_router

router = APIRouter(prefix="/api/recipes", tags=["Recipe"])

router.include_router(recommendation_router)
router.include_router(search_router)
router.include_router(detail_router)
router.include_router(rating_router)
router.include_router(status_router)
router.include_router(product_router)
