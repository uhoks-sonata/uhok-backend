"""User API router entrypoint."""

from fastapi import APIRouter

from services.user.routers.auth_router import router as auth_router
from services.user.routers.profile_router import router as profile_router

router = APIRouter(prefix="/api/user", tags=["User"])

router.include_router(auth_router)
router.include_router(profile_router)
