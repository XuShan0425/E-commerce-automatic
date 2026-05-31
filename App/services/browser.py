"""Playwright 浏览器实例管理 — 含反检测 stealth 注入."""

from __future__ import annotations

from typing import TYPE_CHECKING

from App.core.logging import get_logger

from playwright.sync_api import Browser, BrowserContext, sync_playwright

from App.core.config import settings
from App.services.stealth import STEALTH_JS

logger = get_logger(__name__)

HEADLESS_DEFAULT = settings.ENVIRONMENT != "development"

# 真实 Chrome 125 Windows UA
CHROME_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)


class BrowserService:
    """同步 Playwright 浏览器，提供上下文创建、Cookie 注入和反检测保护。

    每个 context 自动注入 stealth.js 对抗:
      - navigator.webdriver 检测
      - Chrome runtime 缺失检测
      - plugins/mimeTypes 空白检测
      - WebGL 指纹
      - 阿里 Baxia 反爬
    """

    def __init__(self, headless: bool = HEADLESS_DEFAULT) -> None:
        self._playwright = sync_playwright().start()
        launch_kwargs: dict = {
            "headless": headless,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--disable-features=IsolateOrigins,site-per-process",
                "--disable-site-isolation-trials",
                "--disable-infobars",
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-web-security",
                "--disable-features=BlockInsecurePrivateNetworkRequests",
            ],
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

    def new_context(
        self,
        cookies: list[dict] | None = None,
    ) -> BrowserContext:
        """创建浏览器上下文，自动注入反检测脚本。

        可选注入 Cookie（直接传入 Playwright 格式的 cookies 列表）。
        """
        context = self._browser.new_context(
            viewport={"width": 1440, "height": 900},
            user_agent=CHROME_UA,
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
            # 模拟真实屏幕
            screen={"width": 1920, "height": 1080},
            # 权限策略 — 不主动声明以避免指纹异常
            permissions=["geolocation"],
            geolocation={"latitude": 30.2741, "longitude": 120.1551},  # 杭州
            # 减少自动化特征
            reduced_motion="no-preference",
            # 确保色彩/字体与真实 Chrome 一致
            color_scheme="light",
        )

        # ── 注入反检测脚本 ──────────────────────
        context.add_init_script(STEALTH_JS)
        logger.debug("Stealth script injected into browser context")

        # ── Cookie 注入 ─────────────────────────
        if cookies:
            context.add_cookies(cookies)

        return context

    def close(self) -> None:
        """关闭浏览器和 Playwright。"""
        try:
            self._browser.close()
        except Exception:
            logger.debug("browser close failed (may already be closed)")
        try:
            self._playwright.stop()
        except Exception:
            logger.debug("playwright stop failed (may already be closed)")
