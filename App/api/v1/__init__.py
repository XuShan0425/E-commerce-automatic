"""API v1 路由注册."""

from fastapi import APIRouter

from App.api.v1.alerts import router as alerts_router
from App.api.v1.auth import router as auth_router
from App.api.v1.auth_flow import router as auth_flow_router
from App.api.v1.collect import router as collect_router
from App.api.v1.health import router as health_router
from App.api.v1.scheduler_api import router as scheduler_router
from App.api.v1.system import router as system_router

router = APIRouter()
router.include_router(health_router, tags=["health"])
router.include_router(auth_router, tags=["auth"])
router.include_router(auth_flow_router, tags=["auth"])
router.include_router(alerts_router, tags=["alerts"])
router.include_router(collect_router, tags=["collection"])
router.include_router(scheduler_router, tags=["scheduler"])
router.include_router(system_router, tags=["system"])
