"""平台管理 API — 对接 PlatformSyncService."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from App.core.logging import get_logger
from App.services.platform.base import PlatformType
from App.services.platform_sync import get_platform_sync

logger = get_logger(__name__)
router = APIRouter()


@router.get("/platforms")
async def list_platforms() -> list[dict[str, Any]]:
    """获取所有已注册平台列表及状态。"""
    sync = get_platform_sync()
    return sync.list_platforms()


@router.get("/platforms/{platform_type}/health")
async def check_platform_health(
    platform_type: str,
) -> dict[str, Any]:
    """检查指定平台健康状态。"""
    sync = get_platform_sync()
    try:
        ptype = PlatformType(platform_type)
    except ValueError:
        return {"status": "error", "message": f"未知平台: {platform_type}"}

    adapter = sync.get_adapter(ptype)
    if adapter is None:
        return {"status": "error", "message": f"平台 {platform_type} 未注册"}

    result = await adapter.check_health()
    return {
        "status": "ok" if result.is_healthy else "error",
        "platform": platform_type,
        "is_healthy": result.is_healthy,
        "cookie_valid": result.cookie_valid,
        "message": result.message,
        "details": result.details,
    }


@router.post("/platforms/{platform_type}/login")
async def login_platform(
    platform_type: str,
    headless: bool = True,
) -> dict[str, Any]:
    """触发指定平台的登录流程。"""
    sync = get_platform_sync()
    try:
        ptype = PlatformType(platform_type)
    except ValueError:
        return {"status": "error", "message": f"未知平台: {platform_type}"}

    adapter = sync.get_adapter(ptype)
    if adapter is None:
        return {"status": "error", "message": f"平台 {platform_type} 未注册"}

    try:
        success = await adapter.login(headless=headless)
        return {
            "status": "ok" if success else "error",
            "platform": platform_type,
            "message": "登录成功" if success else "登录失败",
        }
    except Exception as exc:
        logger.error("platform_api: %s 登录异常: %s", platform_type, exc)
        return {"status": "error", "message": f"登录异常: {exc}"}


@router.post("/platforms/{platform_type}/reconnect")
async def reconnect_platform(platform_type: str) -> dict[str, Any]:
    """重新连接指定平台。"""
    sync = get_platform_sync()
    try:
        ptype = PlatformType(platform_type)
    except ValueError:
        return {"status": "error", "message": f"未知平台: {platform_type}"}

    success = await sync.reconnect_platform(ptype)
    return {
        "status": "ok" if success else "error",
        "platform": platform_type,
        "message": "重新连接成功" if success else "重新连接失败",
    }


@router.post("/platforms/{platform_type}/toggle")
async def toggle_platform(platform_type: str, enabled: bool) -> dict[str, Any]:
    """启用或禁用指定平台。"""
    sync = get_platform_sync()
    try:
        ptype = PlatformType(platform_type)
    except ValueError:
        return {"status": "error", "message": f"未知平台: {platform_type}"}

    if enabled:
        success = await sync.enable_platform(ptype)
    else:
        success = await sync.disable_platform(ptype)

    return {
        "status": "ok" if success else "error",
        "platform": platform_type,
        "enabled": enabled,
        "message": f"平台已{'启用' if enabled else '禁用'}" if success else "操作失败",
    }


@router.post("/platforms/collect-all")
async def collect_all_platforms() -> dict[str, Any]:
    """对所有已启用平台执行数据采集。"""
    sync = get_platform_sync()
    try:
        results = await sync.collect_all()
        total = sum(len(data) for data in results.values())
        return {
            "status": "ok",
            "platforms": list(results.keys()),
            "total_records": total,
            "details": {
                ptype: len(data)
                for ptype, data in results.items()
            },
        }
    except Exception as exc:
        logger.error("platform_api: 全平台采集异常: %s", exc)
        return {"status": "error", "message": f"采集异常: {exc}"}
