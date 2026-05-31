"""登录流程 API 端点."""

from fastapi import APIRouter, Depends

from App.core.security import verify_api_key
from App.services.login_flow import get_login_status, start_login_flow

router = APIRouter(prefix="/login", tags=["login"])


@router.post("/start")
async def login_start(
    _api_key: str = Depends(verify_api_key),
) -> dict:
    """触发首次登录流程。Playwright 启动可见浏览器，用户手动登录速卖通。"""
    return await start_login_flow()


@router.get("/status")
async def login_status(
    _api_key: str = Depends(verify_api_key),
) -> dict:
    """查询当前登录流程状态。"""
    return await get_login_status()
