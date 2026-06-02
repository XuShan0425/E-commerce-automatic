"""速卖通广告智能管理系统 — FastAPI 应用入口."""

from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from App.api.v1 import router as v1_router
from App.core.config import settings
from App.core.database import async_session_factory, engine
from App.core.logging import get_logger
from App.services.scheduler import init_scheduler, get_scheduler

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    # 启动时初始化调度器（不自动开始，通过 API 手动触发）
    init_scheduler(async_session_factory)
    logger.info("app_startup", extra={"version": "0.1.0"})
    yield
    logger.info("app_shutdown")
    sched = get_scheduler()
    if sched is not None:
        sched.stop()
    await engine.dispose()


app = FastAPI(
    title="速卖通广告智能管理系统",
    description="AliExpress Ad Manager",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(v1_router, prefix="/api/v1")
