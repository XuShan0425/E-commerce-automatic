"""数据采集编排器 — 浏览器 + Cookie + 拦截器 + DB写入全流程."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from App.services.api_interceptor import AdDataInterceptor, CollectedAdData, CollectedPriceData

if TYPE_CHECKING:
    from App.services.browser import BrowserService
    from App.services.cookie_manager import CookieManager

# ── 速卖通卖家中心页面 ──────────────────────────
# 广告数据通常在以下几个页面能触发 API 调用
AD_PAGES = [
    "https://ad.aliexpress.com/campaign/home",
    "https://gsp.aliexpress.com/apps/promotion/home",
    "https://home.aliexpress.com/index.htm",  # 首页也可能触发
]


def _run_collection_sync(
    cookie_manager: CookieManager,
    headless: bool = True,
    timeout: int = 60,
) -> dict:
    """在同步线程中执行数据采集。返回结构化结果。"""
    from App.services.browser import BrowserService

    result: dict = {
        "success": False,
        "ad_count": 0,
        "price_count": 0,
        "total_responses": 0,
        "ad_api_responses": 0,
        "errors": [],
        "duration_seconds": 0,
        "collected_at": datetime.now(timezone.utc).isoformat(),
    }

    t0 = time.perf_counter()
    browser_svc: BrowserService | None = None

    try:
        browser_svc = BrowserService(headless=headless)
        context = browser_svc.new_context(cookie_manager=cookie_manager)
        page = context.new_page()
        interceptor = AdDataInterceptor()
        interceptor.attach(page)

        # 逐个访问广告相关页面，等待 API 响应
        for page_url in AD_PAGES:
            try:
                page.goto(page_url, wait_until="domcontentloaded", timeout=30_000)
                # 等待额外时间让 XHR/Fetch 请求完成
                page.wait_for_timeout(5_000)
                # 滚动页面触发懒加载
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(2_000)
            except Exception as exc:
                result["errors"].append(f"页面 {page_url} 访问异常: {exc}")

        page.close()
        context.close()

        result["ad_data"] = interceptor.result.ad_data
        result["price_data"] = interceptor.result.price_data
        result["ad_count"] = len(interceptor.result.ad_data)
        result["price_count"] = len(interceptor.result.price_data)
        result["total_responses"] = interceptor.result.total_responses
        result["ad_api_responses"] = interceptor.result.ad_api_responses
        result["success"] = True

    except Exception as exc:
        result["errors"].append(f"采集流程异常: {exc}")
    finally:
        if browser_svc is not None:
            browser_svc.close()
        result["duration_seconds"] = round(time.perf_counter() - t0, 2)

    return result


async def collect_ad_data(
    db: AsyncSession,
    cookie_manager: CookieManager,
    headless: bool = True,
    timeout: int = 60,
) -> dict:
    """执行一次完整的数据采集，将结果写入数据库。"""
    import asyncio

    # ── 前置检查：Cookie ──────────────────────────
    cookies = await cookie_manager.load_cookies("aliexpress.com")
    if not cookies:
        return {
            "success": False,
            "error": "no_cookie",
            "message": "没有有效的速卖通 Cookie，请先执行首次登录",
        }

    # ── 检查全局停止 ──────────────────────────────
    from App.models.system_state import SystemState
    stop_result = await db.execute(
        select(SystemState).where(SystemState.key == "global_stop")
    )
    stop_record = stop_result.scalar_one_or_none()
    if stop_record and stop_record.value.get("enabled"):
        return {
            "success": False,
            "error": "global_stop",
            "message": "全局停止已启用，跳过采集",
        }

    # ── 在后台线程执行同步浏览器操作 ──────────────
    loop = asyncio.get_event_loop()
    raw = await loop.run_in_executor(
        None, _run_collection_sync, cookie_manager, headless, timeout
    )

    if not raw.get("success"):
        return {
            "success": False,
            "error": "collection_failed",
            "message": "数据采集失败: " + "; ".join(raw.get("errors", [])),
        }

    # ── 写入数据库 ────────────────────────────────
    from App.models.base import AdSnapshot, PriceSnapshot

    saved_ads = 0
    saved_prices = 0
    now = datetime.now(timezone.utc)

    for ad in raw.get("ad_data", []):
        if not isinstance(ad, CollectedAdData):
            continue
        if not ad.sku_id:
            continue
        snapshot = AdSnapshot(
            sku_id=ad.sku_id,
            snapshot_time=now,
            impressions=ad.impressions,
            clicks=ad.clicks,
            ctr=ad.ctr,
            orders=ad.orders,
            conversion_rate=ad.conversion_rate,
            ad_spend=ad.ad_spend,
            revenue=ad.revenue,
            ad_type=ad.ad_type,
            buyer_region_breakdown=ad.buyer_region_breakdown,
        )
        db.add(snapshot)
        saved_ads += 1

    for price in raw.get("price_data", []):
        if not isinstance(price, CollectedPriceData):
            continue
        if not price.sku_id or price.current_price <= 0:
            continue
        snapshot = PriceSnapshot(
            sku_id=price.sku_id,
            snapshot_time=now,
            current_price=price.current_price,
        )
        db.add(snapshot)
        saved_prices += 1

    await db.flush()

    return {
        "success": True,
        "ad_count": saved_ads,
        "price_count": saved_prices,
        "total_responses": raw.get("total_responses", 0),
        "ad_api_responses": raw.get("ad_api_responses", 0),
        "duration_seconds": raw.get("duration_seconds", 0),
        "errors": raw.get("errors", []),
        "collected_at": raw.get("collected_at"),
    }
