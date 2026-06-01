"""系统状态查询端点 — 只读，免鉴权。"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from App.core.database import get_db
from App.core.logging import get_logger
from App.core.security import verify_api_key
from App.models.auth import ApiKey
from App.models.cookie import CookieStore
from App.models.system_state import SystemState
from App.services.scheduler import get_scheduler

logger = get_logger(__name__)

router = APIRouter(prefix="/system", tags=["system"])

# 项目根目录 (system.py 向上 4 级: App/api/v1/system.py → 项目根)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_RESTART_FILE = _PROJECT_ROOT / "data" / "restart.flag"
_LOG_FILE = _PROJECT_ROOT / "logs" / "app.log"


@router.get("/status")
async def system_status(db: AsyncSession = Depends(get_db)) -> dict:
    """返回系统聚合运行状态。免鉴权。"""
    # Cookie 状态
    cookie_result = await db.execute(
        select(CookieStore).where(CookieStore.domain == "aliexpress.com")
    )
    cookie_record = cookie_result.scalar_one_or_none()

    if cookie_record is None:
        cookie_status = "no_cookie"
    elif cookie_record.is_valid:
        cookie_status = "valid"
    else:
        cookie_status = "invalid"

    # 全局停止
    stop_result = await db.execute(
        select(SystemState).where(SystemState.key == "global_stop")
    )
    stop_record = stop_result.scalar_one_or_none()
    global_stop = bool(stop_record.value.get("enabled", False)) if stop_record else False

    # 调度器状态
    sched = get_scheduler()
    scheduler_running = sched.is_running if sched else False
    scheduler_interval = 30  # 默认值

    # 最近采集结果
    last_collection = sched.last_result if sched else None

    # API Key 数量
    key_count_result = await db.execute(select(func.count(ApiKey.id)))
    api_keys_count = key_count_result.scalar_one()

    return {
        "global_stop": global_stop,
        "cookie_status": cookie_status,
        "scheduler_running": scheduler_running,
        "scheduler_interval": scheduler_interval,
        "last_collection": last_collection,
        "api_keys_count": api_keys_count,
    }


# ── 热重启 ──────────────────────────────────────────

@router.post("/restart")
async def restart_server(
    _api_key: str = Depends(verify_api_key),
) -> dict:
    """热重启后端服务（通过 start.py 启动器实现零停机重启）。"""
    _RESTART_FILE.parent.mkdir(parents=True, exist_ok=True)
    _RESTART_FILE.write_text("1")
    logger.info("热重启请求已接收，将在 1 秒后重启")

    async def _delayed_exit():
        await asyncio.sleep(1)
        os._exit(0)

    asyncio.create_task(_delayed_exit())
    return {"status": "ok", "message": "系统将在 1 秒后重启"}


# ── 日志查看 ─────────────────────────────────────────

@router.get("/logs")
async def get_logs(
    lines: int = Query(50, ge=1, le=500),
    _api_key: str = Depends(verify_api_key),
) -> dict:
    """获取最近的应用日志。返回纯文本格式的日志尾部。"""
    if not _LOG_FILE.exists():
        return {"status": "ok", "lines": 0,
                "content": "日志文件不存在，请通过 scripts/start.py 启动"}

    try:
        with open(_LOG_FILE, encoding="utf-8", errors="replace") as f:
            all_lines = f.readlines()
        tail = "".join(all_lines[-lines:])
        return {
            "status": "ok",
            "lines": min(lines, len(all_lines)),
            "total_lines": len(all_lines),
            "content": tail,
        }
    except Exception as exc:
        logger.error("读取日志失败", extra={"error": str(exc)})
        return {"status": "error", "lines": 0, "content": f"读取日志失败: {exc}"}
