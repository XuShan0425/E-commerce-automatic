"""系统状态查询端点 — 只读，免鉴权."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from App.core.database import get_db
from App.services.cookie_health import get_system_status
from App.services.cookie_manager import CookieManager

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/status")
async def system_status(db: AsyncSession = Depends(get_db)) -> dict:
    """返回系统运行状态（全局停止标志、Cookie 有效性）。"""
    cookie_mgr = CookieManager(db)
    return await get_system_status(db, cookie_mgr)
