"""费率解析服务 — 使用 requests + BeautifulSoup 抓取公开帮助页面，经 Claude AI 解析后返回结构化数据。

相比原有的 rate_scraper.py (Playwright)，此服务使用轻量级 HTTP 请求，
适用于速卖通公开帮助页面（无需 Cookie/登录）。
"""

from __future__ import annotations

from typing import Any

from App.core.logging import get_logger

logger = get_logger(__name__)

# ── 目标页面 URL ──────────────────────────────────
LOGISTICS_URL = (
    "https://sale.aliexpress.com/__pc/category/logistics.htm"
)
COMMISSION_URL = (
    "https://sale.aliexpress.com/__pc/category/commission.htm"
)

REQUEST_TIMEOUT = 30


async def fetch_logistics_page() -> str:
    """抓取物流费率页面文本内容（使用 requests，无需浏览器）。"""
    import asyncio
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _fetch_page_text, LOGISTICS_URL)


async def fetch_commission_page() -> str:
    """抓取平台佣金页面文本内容。"""
    import asyncio
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _fetch_page_text, COMMISSION_URL)


def _fetch_page_text(url: str) -> str:
    """同步抓取页面，返回纯净文本（去除 HTML 标签）。"""
    import requests
    from bs4 import BeautifulSoup

    try:
        logger.info("正在抓取页面: %s", url)
        resp = requests.get(url, timeout=REQUEST_TIMEOUT, headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
        })
        resp.raise_for_status()
        # 自动检测编码
        resp.encoding = resp.apparent_encoding or "utf-8"

        soup = BeautifulSoup(resp.text, "html.parser")

        # 移除 script/style 等标签
        for tag in soup(["script", "style", "noscript", "iframe", "svg"]):
            tag.decompose()

        text = soup.get_text(separator="\n", strip=True)
        logger.info("页面抓取完成: %d 字符", len(text))
        return text[:50000]  # 限制 5 万字符，避免超出 Claude 上下文

    except Exception as exc:
        logger.error("页面抓取失败: %s — %s", url, exc)
        raise RuntimeError(f"页面抓取失败 ({url}): {exc}") from exc


async def parse_logistics_rates() -> list[dict[str, Any]]:
    """抓取物流费率页面并用 AI 解析为结构化列表。"""
    from App.services.ai_client import parse_logistics_html

    text = await fetch_logistics_page()
    # 包装成简单 HTML 格式传给现有的 AI 解析函数
    wrapped = f"<html><body><pre>{text}</pre></body></html>"
    result = await parse_logistics_html(wrapped)
    return result


async def parse_commission_rates() -> list[dict[str, Any]]:
    """抓取平台佣金页面并用 AI 解析为结构化列表。"""
    from App.services.ai_client import parse_fees_html

    text = await fetch_commission_page()
    wrapped = f"<html><body><pre>{text}</pre></body></html>"
    result = await parse_fees_html(wrapped)
    return result
