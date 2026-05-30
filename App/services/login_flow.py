"""首次登录流程 — 启动浏览器，用户手动登录，自动保存 Cookie."""

from __future__ import annotations

import asyncio
import threading
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from App.models.system_state import SystemState

if TYPE_CHECKING:
    from App.services.browser import BrowserService
    from App.services.cookie_manager import CookieManager


class LoginStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"


ALIEXPRESS_LOGIN_URL = "https://login.aliexpress.com/"
ALIEXPRESS_SELLER_URL = "https://home.aliexpress.com/index.htm"
LOGIN_TIMEOUT_SECONDS = 300  # 5 分钟超时


async def _set_login_status(db: AsyncSession, status: str, message: str = "") -> None:
    """更新登录流程状态到 system_state 表。"""
    result = await db.execute(
        select(SystemState).where(SystemState.key == "login_status")
    )
    record = result.scalar_one_or_none()
    value = {"status": status, "message": message, "updated_at": datetime.now(timezone.utc).isoformat()}
    if record is not None:
        record.value = value  # type: ignore[assignment]
    else:
        record = SystemState(key="login_status", value=value)  # type: ignore[arg-type]
        db.add(record)
    await db.flush()


async def get_login_status(db: AsyncSession) -> dict:
    """查询当前登录流程状态。"""
    result = await db.execute(
        select(SystemState).where(SystemState.key == "login_status")
    )
    record = result.scalar_one_or_none()
    if record is None:
        return {"status": LoginStatus.IDLE.value, "message": ""}
    return record.value


def _run_login_sync(
    db_url: str,
    cookie_manager_class: type,
    domain: str,
    timeout: int,
) -> dict:
    """在新线程中执行同步 Playwright 登录流程。

    从数据库加载/保存 Cookie 需要独立的 sync session，
    因为 Playwright 在 sync 上下文运行。
    """
    from playwright.sync_api import sync_playwright

    result: dict = {"status": LoginStatus.FAILED.value, "message": ""}

    try:
        pw = sync_playwright().start()
        browser = pw.chromium.launch(
            headless=False,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()
        page.goto(ALIEXPRESS_LOGIN_URL, wait_until="domcontentloaded")

        # 等待用户完成登录（轮询 URL 和 Cookie 变化）
        elapsed = 0
        poll_interval = 2
        while elapsed < timeout:
            page.wait_for_timeout(poll_interval * 1000)
            elapsed += poll_interval

            current_url = page.url
            # 检测是否已离开登录页（登录成功标志）
            if "login.aliexpress.com" not in current_url and "passport.aliexpress.com" not in current_url:
                cookies = context.cookies()
                if cookies:
                    result = {
                        "status": LoginStatus.SUCCESS.value,
                        "message": "登录成功，Cookie 已保存",
                        "cookies": [
                            {
                                "name": c["name"],
                                "value": c["value"],
                                "domain": c.get("domain", ""),
                                "path": c.get("path", "/"),
                                "expires": c.get("expires", -1),
                                "httpOnly": c.get("httpOnly", False),
                                "secure": c.get("secure", False),
                                "sameSite": c.get("sameSite", "Lax"),
                            }
                            for c in cookies
                        ],
                        "cookie_count": len(cookies),
                    }
                    break

        else:
            # 超时
            result = {
                "status": LoginStatus.TIMEOUT.value,
                "message": f"登录超时（{timeout} 秒），请重试",
            }

        browser.close()
        pw.stop()

    except Exception as exc:
        result = {
            "status": LoginStatus.FAILED.value,
            "message": f"登录流程异常: {str(exc)}",
        }

    return result


async def start_login_flow(
    db: AsyncSession,
    cookie_manager: CookieManager,
    domain: str = "aliexpress.com",
    timeout: int = LOGIN_TIMEOUT_SECONDS,
) -> dict:
    """启动首次登录流程。

    在后台线程中启动非 headless 浏览器，用户在浏览器中手动登录速卖通。
    登录成功后自动保存 Cookie 到数据库。
    """
    # 检查是否已有登录流程在运行
    current = await get_login_status(db)
    if current.get("status") == LoginStatus.RUNNING.value:
        return {"status": "error", "message": "已有登录流程正在运行，请等待完成或超时"}

    await _set_login_status(db, LoginStatus.RUNNING.value, "浏览器已启动，请在浏览器中登录速卖通")

    # 在后台线程运行同步浏览器操作
    result: dict = {"status": LoginStatus.FAILED.value, "message": ""}

    def _run() -> None:
        nonlocal result
        result = _run_login_sync("", type(cookie_manager), domain, timeout)

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()

    # 等待线程完成（非阻塞轮询，给 asyncio 事件循环让出时间）
    while thread.is_alive():
        await asyncio.sleep(1)

    # 线程完成，处理结果
    if result.get("status") == LoginStatus.SUCCESS.value:
        cookies = result.get("cookies", [])
        if cookies:
            await cookie_manager.save_cookies(domain, cookies)
        await _set_login_status(db, LoginStatus.SUCCESS.value, result.get("message", ""))
    else:
        await _set_login_status(db, result.get("status", LoginStatus.FAILED.value), result.get("message", ""))

    return result
