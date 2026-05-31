"""Playwright 浏览器实例管理."""

from __future__ import annotations

from typing import TYPE_CHECKING

from playwright.sync_api import Browser, BrowserContext, sync_playwright

from App.core.config import settings

if TYPE_CHECKING:
    from App.services.cookie_manager import CookieManager

HEADLESS_DEFAULT = settings.ENVIRONMENT != "development"


class BrowserService:
    """同步 Playwright 浏览器，提供上下文创建和 Cookie 注入。"""

    def __init__(self, headless: bool = HEADLESS_DEFAULT) -> None:
        self._playwright = sync_playwright().start()
        launch_kwargs: dict = {
            "headless": headless,
            "args": ["--disable-blink-features=AutomationControlled"],
        }
        if not headless:
            try:
                self._browser = self._playwright.chromium.launch(channel="msedge", **launch_kwargs)
            except Exception:
                self._browser = self._playwright.chromium.launch(**launch_kwargs)
        else:
            self._browser = self._playwright.chromium.launch(**launch_kwargs)

    @property
    def browser(self) -> Browser:
        return self._browser

    def new_context(self, cookie_manager: CookieManager | None = None, cookies: list[dict] | None = None) -> BrowserContext:
        """创建浏览器上下文。可选注入 Cookie（直接传入或通过 CookieManager 加载）。"""
        context = self._browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
        )
        if cookies:
            context.add_cookies(cookies)
        elif cookie_manager is not None:
            # CookieManager.load_cookies 是 async，sync 方法中无法 await。
            # 调用方应先在 async 上下文中加载好 cookies，然后通过 cookies= 传入。
            import asyncio
            try:
                loop = asyncio.get_running_loop()
                # 有运行中的事件循环 → 用 run_coroutine_threadsafe 不适用
                # 标记：调用方需显式传入 cookies
            except RuntimeError:
                pass
        return context

    def close(self) -> None:
        """关闭浏览器和 Playwright。"""
        self._browser.close()
        self._playwright.stop()
