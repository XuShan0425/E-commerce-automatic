"""数据采集 API 端点 — 手动触发采集、查看状态."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from App.core.database import get_db
from App.core.security import verify_api_key
from App.services.cookie_manager import CookieManager
from App.services.data_collector import collect_ad_data

router = APIRouter(prefix="/collect", tags=["collection"])


@router.post("/run")
async def collect_now(
    headless: bool = True,
    _api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """手动触发一次数据采集（headless 模式）。"""
    cookie_mgr = CookieManager(db)
    result = await collect_ad_data(db, cookie_mgr, headless=headless)
    return result


@router.get("/status")
async def collect_status(
    _api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """查询最近一次采集结果（从 scheduler 缓存）。"""
    from App.services.scheduler import get_scheduler

    sched = get_scheduler()
    if sched is None or sched.last_result is None:
        return {"status": "no_data", "message": "尚未执行过采集"}
    return {"status": "ok", "last_result": sched.last_result}
