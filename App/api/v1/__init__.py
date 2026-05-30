"""API v1 路由注册."""

from fastapi import APIRouter

from App.api.v1.auth import router as auth_router
from App.api.v1.health import router as health_router

router = APIRouter()
router.include_router(health_router, tags=["health"])
router.include_router(auth_router, tags=["auth"])
