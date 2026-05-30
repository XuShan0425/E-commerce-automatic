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
        self._browser: Browser = self._playwright.chromium.launch(
            headless=headless,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
        )

    @property
    def browser(self) -> Browser:
        return self._browser

    def new_context(self, cookie_manager: CookieManager | None = None) -> BrowserContext:
        """创建浏览器上下文。如果提供了 CookieManager，自动注入已保存的 Cookie。"""
        context = self._browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
        )
        if cookie_manager is not None:
            cookies = cookie_manager.load_cookies("aliexpress.com")
            if cookies:
                context.add_cookies(cookies)
        return context

    def close(self) -> None:
        """关闭浏览器和 Playwright。"""
        self._browser.close()
        self._playwright.stop()
