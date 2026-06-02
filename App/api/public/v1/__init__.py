"""Public API v1 — 路由注册."""
from fastapi import APIRouter
from App.api.public.v1.export import router as export_router

router = APIRouter()
router.include_router(export_router)
