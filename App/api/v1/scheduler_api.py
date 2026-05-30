"""调度器 API 端点 — 启动/停止/查看定时采集."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from App.core.database import async_session_factory, get_db
from App.core.security import verify_api_key
from App.services.scheduler import get_scheduler, init_scheduler

router = APIRouter(prefix="/scheduler", tags=["scheduler"])


@router.post("/start")
async def scheduler_start(
    interval_minutes: int = 30,
    _api_key: str = Depends(verify_api_key),
) -> dict:
    """启动定时采集任务。"""
    sched = get_scheduler()
    if sched is None:
        sched = init_scheduler(async_session_factory)
    sched.start(interval_minutes=interval_minutes)
    return {"status": "ok", "message": f"定时采集已启动，间隔 {interval_minutes} 分钟"}


@router.post("/stop")
async def scheduler_stop(
    _api_key: str = Depends(verify_api_key),
) -> dict:
    """停止定时采集任务。"""
    sched = get_scheduler()
    if sched is not None:
        sched.stop()
    return {"status": "ok", "message": "定时采集已停止"}


@router.get("/status")
async def scheduler_status(
    _api_key: str = Depends(verify_api_key),
) -> dict:
    """查看调度器运行状态。"""
    sched = get_scheduler()
    if sched is None:
        return {"running": False, "message": "调度器未初始化"}
    return {
        "running": sched.is_running,
        "last_result": sched.last_result,
    }
