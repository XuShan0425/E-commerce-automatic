"""Playwright 费率页面抓取 — 获取速卖通帮助中心页面 HTML."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from App.core.config import settings

if TYPE_CHECKING:
    from App.services.browser import BrowserService

logger = logging.getLogger(__name__)

# ── 可配置的目标页面 URL ─────────────────────────
# 生产环境中通过 .env 配置，此处为占位默认值
DEFAULT_LOGISTICS_URL = (
    "https://sale.aliexpress.com/__pc/category/logistics.htm"
)
DEFAULT_FEES_URL = (
    "https://sale.aliexpress.com/__pc/category/commission.htm"
)

SCRAPE_TIMEOUT_MS = 30_000  # 页面加载超时
SCRAPE_WAIT_MS = 3_000      # 额外等待时间（动态内容渲染）


async def fetch_page_html(
    browser_service: "BrowserService",
    url: str,
    *,
    timeout_ms: int = SCRAPE_TIMEOUT_MS,
    wait_ms: int = SCRAPE_WAIT_MS,
) -> str:
    """使用 Playwright 抓取指定页面，返回完整 HTML。

    Args:
        browser_service: 已初始化的 BrowserService 实例
        url: 目标页面 URL
        timeout_ms: 页面加载超时（毫秒）
        wait_ms: 加载后额外等待时间（等待动态渲染）

    Returns:
        页面的完整 HTML 内容

    Raises:
        RuntimeError: 页面加载或抓取失败
    """
    context = browser_service.new_context()  # 无需 Cookie，帮助页是公开的
    page = None
    try:
        page = context.new_page()
        logger.info("正在抓取页面: %s", url)

        await asyncio.to_thread(
            page.goto,
            url,
            timeout=timeout_ms,
            wait_until="domcontentloaded",
        )

        # 额外等待，确保表格等动态内容加载完成
        await asyncio.sleep(wait_ms / 1000.0)

        html = await asyncio.to_thread(page.content)
        logger.info("页面抓取完成: %d 字符", len(html))
        return html

    except Exception as exc:
        logger.error("页面抓取失败: %s — %s", url, exc)
        raise RuntimeError(f"页面抓取失败 ({url}): {exc}") from exc

    finally:
        if page is not None:
            await asyncio.to_thread(page.close)
        await asyncio.to_thread(context.close)


async def fetch_logistics_page(browser_service: "BrowserService") -> str:
    """抓取物流费率页面 HTML。"""
    return await fetch_page_html(browser_service, DEFAULT_LOGISTICS_URL)


async def fetch_fees_page(browser_service: "BrowserService") -> str:
    """抓取平台佣金页面 HTML。"""
    return await fetch_page_html(browser_service, DEFAULT_FEES_URL)
