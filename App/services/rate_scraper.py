"""Playwright 费率页面抓取 — 同步抓取速卖通帮助中心页面 HTML（在后台线程中运行）."""

from __future__ import annotations

from typing import TYPE_CHECKING

from App.core.logging import get_logger

if TYPE_CHECKING:
    from App.services.browser import BrowserService

logger = get_logger(__name__)

# ── 可配置的目标页面 URL ─────────────────────────
DEFAULT_LOGISTICS_URL = (
    "https://sale.aliexpress.com/__pc/category/logistics.htm"
)
DEFAULT_FEES_URL = (
    "https://sale.aliexpress.com/__pc/category/commission.htm"
)

SCRAPE_TIMEOUT_MS = 30_000
SCRAPE_WAIT_MS = 3_000


def _fetch_page_html_sync(
    browser_service: BrowserService,
    url: str,
    timeout_ms: int = SCRAPE_TIMEOUT_MS,
    wait_ms: int = SCRAPE_WAIT_MS,
) -> str:
    """同步抓取指定页面，返回完整 HTML。在所有 BrowserService 使用场景下运行在后台线程。"""
    context = browser_service.new_context()  # 无需 Cookie，帮助页是公开的
    page = None
    try:
        page = context.new_page()
        logger.info("正在抓取页面: %s", url)

        page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
        page.wait_for_timeout(wait_ms)

        html = page.content()
        logger.info("页面抓取完成: %d 字符", len(html))
        return html

    except Exception as exc:
        logger.error("页面抓取失败: %s — %s", url, exc)
        raise RuntimeError(f"页面抓取失败 ({url}): {exc}") from exc

    finally:
        if page is not None:
            try:
                page.close()
            except Exception:
                logger.debug("page close failed in rate scraper")
        context.close()


def fetch_logistics_page_sync(browser_service: BrowserService) -> str:
    """同步抓取物流费率页面 HTML。"""
    return _fetch_page_html_sync(browser_service, DEFAULT_LOGISTICS_URL)


def fetch_fees_page_sync(browser_service: BrowserService) -> str:
    """同步抓取平台佣金页面 HTML。"""
    return _fetch_page_html_sync(browser_service, DEFAULT_FEES_URL)
