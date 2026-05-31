"""系统状态查询端点 — 只读，免鉴权."""

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from App.core.database import get_db
from App.models.auth import ApiKey
from App.models.cookie import CookieStore
from App.models.system_state import SystemState
from App.services.cookie_health import get_system_status
from App.services.scheduler import get_scheduler

router = APIRouter(prefix="/system", tags=["system"])


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
