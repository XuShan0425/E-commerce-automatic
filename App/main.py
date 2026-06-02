"""速卖通广告智能管理系统 — FastAPI 应用入口."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from App.api.public import router as public_router
from App.api.public.v1 import router as public_v1_router
from App.api.v1 import router as v1_router
from App.core.config import settings
from App.core.database import async_session_factory, engine
from App.core.logging import get_logger
from App.services.scheduler import get_scheduler, init_scheduler

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator:
    # 启动时初始化调度器（不自动开始，通过 API 手动触发）
    init_scheduler(async_session_factory)
    logger.info("app_startup", extra={"version": "0.1.0"})
    yield
    logger.info("app_shutdown")
    sched = get_scheduler()
    if sched is not None:
        sched.stop()
    await engine.dispose()


# 主应用
app = FastAPI(
    title="速卖通广告智能管理系统",
    description="AliExpress Ad Manager",
    version="0.1.0",
    lifespan=lifespan,
)

# 公共 API 子应用（独立 OpenAPI 文档挂载在 /api/public/v1/docs）
public_app = FastAPI(
    title="AliExpress Ad Manager Public API",
    description="速卖通广告智能管理系统 — 公共 REST API",
    version="0.1.0",
)
public_app.include_router(public_router)
public_app.include_router(public_v1_router)

app.mount("/api/public/v1", public_app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(v1_router, prefix="/api/v1")
