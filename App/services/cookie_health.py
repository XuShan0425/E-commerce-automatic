"""Cookie 健康检查服务 — 检测速卖通登录态是否有效."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

class CookieHealth(str, Enum):
    """Cookie 健康状态枚举。"""

    VALID = "valid"
    INVALID = "invalid"
    NO_COOKIE = "no_cookie"
    ERROR = "error"


def _is_login_page(url: str) -> bool:
    """判断当前 URL 是否为登录页面。"""
    return any(pattern in url for pattern in LOGIN_URL_PATTERNS)


from App.core.database import Base


def _detect_cookie_expiry(cookies: list[dict]) -> int | None:
    """检测 Cookie 中最早过期的天数（负数表示已过期）。返回 None 表示无过期信息。"""
    now = datetime.now(timezone.utc)
    min_days = None
    for c in cookies:
        expires = c.get("expires")
        if expires is None or expires <= 0:
            continue
        try:
            exp_time = datetime.fromtimestamp(expires, tz=timezone.utc)
            days = (exp_time - now).total_seconds() / 86400
            if min_days is None or days < min_days:
                min_days = days
        except Exception:
            continue
    return min_days


async def check_cookie_health(
    db: AsyncSession,
    browser_service: BrowserService,
    cookie_manager: CookieManager,
    domain: str = "aliexpress.com",
) -> CookieHealth:
    """检查指定域名的 Cookie 是否仍有效。

    流程：
    1. 从 DB 加载 Cookie
    2. 用 Playwright 访问速卖通卖家中心
    3. 检测是否被重定向到登录页
    4. 更新数据库中的有效性标记
    """
    cookies = await cookie_manager.load_cookies(domain)
    if not cookies:
        return CookieHealth.NO_COOKIE

    try:
        context = browser_service.new_context(cookies=cookies)
        page = context.new_page()

        # 访问卖家中心首页
        response = page.goto(ALIEXPRESS_SELLER_URL, wait_until="domcontentloaded", timeout=30_000)

        current_url = page.url
        page.close()
        context.close()

        # 判断登录状态
        if response is None:
            await cookie_manager.mark_invalid(domain)
            return CookieHealth.ERROR

        if _is_login_page(current_url):
            await cookie_manager.mark_invalid(domain)
            return CookieHealth.INVALID

        # Cookie 有效
        await cookie_manager.mark_valid(domain)
        return CookieHealth.VALID

    except Exception:
        # 网络错误等异常
        return CookieHealth.ERROR


async def get_system_status(
    db: AsyncSession,
    cookie_manager: CookieManager,
) -> dict:
    """获取系统聚合状态，供 `/system/status` 端点使用。"""

    result = await db.execute(
        select(SystemState).where(SystemState.key == "global_stop")
    )
    global_stop_record = result.scalar_one_or_none()
    global_stop = False
    if global_stop_record is not None:
        global_stop = bool(global_stop_record.value.get("enabled", False))

    cookies = await cookie_manager.load_cookies("aliexpress.com")
    cookie_valid = len(cookies) > 0
    days_remaining = _detect_cookie_expiry(cookies) if cookies else None

    return {
        "global_stop": global_stop,
        "cookie_valid": cookie_valid,
        "cookie_days_remaining": days_remaining,
    }
