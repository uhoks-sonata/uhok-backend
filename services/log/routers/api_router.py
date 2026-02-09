"""Log API router entrypoint."""

from fastapi import APIRouter

from services.log.routers.activity_router import router as activity_router
from services.log.routers.event_router import router as event_router

router = APIRouter(tags=["Log"])

router.include_router(event_router)
router.include_router(activity_router)
