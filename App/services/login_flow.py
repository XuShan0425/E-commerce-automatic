"""首次登录流程 — 启动浏览器，用户手动登录，自动保存 Cookie."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import select

from App.core.database import async_session_factory
from App.models.cookie import CookieStore
from App.models.system_state import SystemState


class LoginStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"


ALIEXPRESS_LOGIN_URL = "https://csp.aliexpress.com/"
LOGIN_TIMEOUT_SECONDS = 300  # 5 分钟超时

# 登录页面 URL 特征（在这些页面时表示用户还在登录中）
LOGIN_PAGE_PATTERNS = ["login.aliexpress.com", "passport.aliexpress.com", "ae.aliexpress.com"]

# 后台线程与主协程之间的结果传递（线程安全）
_result_lock = threading.Lock()
_pending_result: dict | None = None


@dataclass
class LoginResult:
    status: str
    message: str
    cookies: list[dict] | None = None


async def _set_login_status(status: str, message: str = "") -> None:
    """更新登录流程状态到 system_state 表。"""
    async with async_session_factory() as db:
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
        await db.commit()


async def _save_cookies_in_db(domain: str, cookies: list[dict]) -> None:
    """保存 Cookie 到数据库。"""
    async with async_session_factory() as db:
        result = await db.execute(
            select(CookieStore).where(CookieStore.domain == domain)
        )
        record = result.scalar_one_or_none()
        if record is not None:
            record.cookies_json = cookies  # type: ignore[assignment]
            record.is_valid = True
            record.updated_at = datetime.now(timezone.utc)
        else:
            record = CookieStore(
                domain=domain,
                cookies_json=cookies,  # type: ignore[arg-type]
                is_valid=True,
            )
            db.add(record)
        await db.commit()


async def get_login_status(db_ignored=None) -> dict:
    """查询当前登录流程状态。同时消费后台线程写入的结果。"""
    global _pending_result

    # 检查后台线程是否有待消费的结果
    with _result_lock:
        if _pending_result is not None:
            result = _pending_result
            _pending_result = None
            # 释放锁后再做 DB 操作（DB 操作在 async 上下文中安全）
            if result["status"] == LoginStatus.SUCCESS.value and result.get("cookies"):
                await _save_cookies_in_db("aliexpress.com", result["cookies"])
            await _set_login_status(result["status"], result["message"])
            return {"status": result["status"], "message": result["message"]}

    async with async_session_factory() as db:
        result = await db.execute(
            select(SystemState).where(SystemState.key == "login_status")
        )
        record = result.scalar_one_or_none()
        if record is None:
            return {"status": LoginStatus.IDLE.value, "message": ""}
        return record.value


def _run_login_flow_sync(domain: str, timeout: int) -> None:
    """在后台线程中执行登录流程（纯 Playwright 操作，不碰 DB）。

    完成后将结果写入 _pending_result，由下一次 get_login_status() 消费。
    """
    global _pending_result

    try:
        from playwright.sync_api import sync_playwright
        from App.services.stealth import STEALTH_JS

        pw = sync_playwright().start()
        launch_kwargs = {
            "headless": False,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--disable-features=IsolateOrigins,site-per-process",
                "--disable-infobars",
                "--no-sandbox",
            ],
        }
        try:
            browser = pw.chromium.launch(channel="msedge", **launch_kwargs)
        except Exception:
            browser = pw.chromium.launch(**launch_kwargs)

        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
            screen={"width": 1920, "height": 1080},
        )
        context.add_init_script(STEALTH_JS)
        page = context.new_page()
        page.goto(ALIEXPRESS_LOGIN_URL, wait_until="domcontentloaded")

        # 初始等待：给页面重定向留出时间（csp.aliexpress.com 会自动跳转到登录页）
        page.wait_for_timeout(5_000)

        # 等待用户完成登录：url 不再含登录页特征 + cookie 中有 auth 相关的 key
        elapsed = 5  # 配合上面初始等待
        poll_interval = 3
        while elapsed < timeout:
            page.wait_for_timeout(poll_interval * 1000)
            elapsed += poll_interval

            current_url = page.url
            cookies = context.cookies()

            # 还在登录页面 → 继续等待
            if any(p in current_url for p in LOGIN_PAGE_PATTERNS):
                continue

            # 已离开登录页，且有 cookie → 登录成功
            if cookies:
                from App.services.cookie_manager import CookieManager
                serialized = CookieManager.serialize_cookies(cookies)
                browser.close()
                pw.stop()
                with _result_lock:
                    _pending_result = {
                        "status": LoginStatus.SUCCESS.value,
                        "message": "登录成功，Cookie 已保存",
                        "cookies": serialized,
                    }
                return
        else:
            browser.close()
            pw.stop()
            with _result_lock:
                _pending_result = {
                    "status": LoginStatus.TIMEOUT.value,
                    "message": f"登录超时（{timeout} 秒），请重试",
                }
            return

    except Exception as exc:
        with _result_lock:
            _pending_result = {
                "status": LoginStatus.FAILED.value,
                "message": f"登录流程异常: {exc}",
            }


async def start_login_flow(
    domain: str = "aliexpress.com",
    timeout: int = LOGIN_TIMEOUT_SECONDS,
) -> dict:
    """启动首次登录流程（非阻塞）。

    在后台线程中启动可见浏览器，用户手动登录速卖通。
    登录成功后自动保存 Cookie 到数据库。
    立即返回，通过 GET /login/status 轮询进度。
    """
    # 先检查是否有未消费的结果
    global _pending_result
    with _result_lock:
        if _pending_result is not None:
            # 有遗留结果，先消费
            pending = _pending_result
            _pending_result = None
            if pending["status"] == LoginStatus.SUCCESS.value and pending.get("cookies"):
                await _save_cookies_in_db(domain, pending["cookies"])
            await _set_login_status(pending["status"], pending["message"])

    current = await get_login_status()
    if current.get("status") == LoginStatus.RUNNING.value:
        return {"status": "error", "message": "已有登录流程正在运行，请等待完成或超时"}

    await _set_login_status(LoginStatus.RUNNING.value, "浏览器已启动，请在浏览器中登录速卖通")

    thread = threading.Thread(target=_run_login_flow_sync, args=(domain, timeout), daemon=True)
    thread.start()

    return {
        "status": "started",
        "message": "浏览器已启动，请在弹出的浏览器窗口中登录速卖通。完成后系统将自动保存 Cookie。",
    }
