"""速卖通广告智能管理系统 — FastAPI 应用入口."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from App.api.public import router as public_router
from App.api.public.v1 import router as public_v1_router
from App.api.v1 import router as v1_router
from App.core.config import settings
from App.core.database import async_session_factory, engine
from App.core.logging import get_logger
from App.services.plugin_loader import PluginLoader
from App.services.scheduler import get_scheduler, init_scheduler

logger = get_logger(__name__)

# 全局插件加载器（lifespan 中初始化）
plugin_loader: PluginLoader | None = None


def get_plugin_loader() -> PluginLoader | None:
    """获取全局插件加载器实例。"""
    return plugin_loader


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator:
    global plugin_loader

    # 启动时初始化调度器（不自动开始，通过 API 手动触发）
    init_scheduler(async_session_factory)

    # 初始化插件加载器
    plugin_dir = Path(__file__).resolve().parent.parent / "App" / "plugins"
    loader = PluginLoader(plugin_dir=str(plugin_dir), auto_enable=True)
    await loader.discover()
    await loader.load_all()
    await loader.start_all()
    plugin_loader = loader
    loaded = loader.get_registry_status()
    loaded_names = [p["name"] for p in loaded if p["status"] == "enabled"]
    logger.info(
        "plugin_loader_ready",
        extra={
            "plugin_count": loader.get_loaded_count(),
            "plugins": loaded_names,
        },
    )

    logger.info("app_startup", extra={"version": "0.1.0"})
    yield

    # 关闭时停止插件
    if plugin_loader is not None:
        await plugin_loader.stop_all()

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
