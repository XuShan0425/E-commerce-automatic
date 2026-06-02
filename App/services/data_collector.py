"""数据采集编排器 — 浏览器 + Cookie + CSP 导出 + DB写入全流程.

采集策略（按优先级）:
  1. CSP SYCM 官方导出 (CSV/XLSX 下载) — 主路径，2026-06 起默认启用
  2. API 拦截 (XHR 响应嗅探) — 回退路径，主路径失败时自动切换

设计原则:
  - 所有浏览器操作在同步线程中执行 (`loop.run_in_executor`)
  - 双路径共享同一 DB 写入逻辑
  - 下载文件使用 tempfile 自动清理
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import Insert as PgInsert
from sqlalchemy.ext.asyncio import AsyncSession

from App.models.base import AdSnapshot, PriceSnapshot, Product
from App.models.system_state import is_global_stop_active

from App.services.api_interceptor import AdDataInterceptor, CollectedAdData, CollectedPriceData
from App.core.errors import ErrorCode, error_response
from App.models.base import AdSnapshot, PriceSnapshot, Product
from App.models.system_state import is_global_stop_active

if TYPE_CHECKING:
    from App.services.browser import BrowserService
    from App.services.cookie_manager import CookieManager

logger = logging.getLogger(__name__)

# ── Feature flag ───────────────────────────────────
# 设为 False 可一键回退到旧 API 拦截方案
USE_CSP_EXPORT = True

# ── 速卖通卖家中心页面 (旧 API 拦截回退用) ──────
AD_PAGES = [
    "https://csp.aliexpress.com/",
    "https://csp.aliexpress.com/m_apps/p4p-pages/home?p4p_enter_from=sidebar",
    "https://csp.aliexpress.com/m_apps/all-in-one-promotion/home",
]

# ── CSP 导出默认超时 ──────────────────────────────
CSP_EXPORT_TIMEOUT = 55       # 单次导出等待上限（秒）
CSP_EXPORT_MAX_RETRIES = 1    # 失败重试次数


def _run_csp_export_sync(
    products: list[dict[str, Any]],
    cookies: list[dict],
    headless: bool = True,
    timeout: int = CSP_EXPORT_TIMEOUT,
) -> dict:
    """在同步线程中执行 CSP 导出采集。返回结构化结果。

    对每个 tracked SKU:
      1. 打开 SYCM 搜索页 → 搜索 SKU → 进入详情页
      2. 导出核心指标 XLSX → openpyxl 解析
      3. 映射列名 → AdSnapshot/PriceSnapshot 字段
      4. 失败时重试 1 次后跳过
    """
    from App.services.browser import BrowserService
    from App.services.product_analytics_service import (
        export_product_ad_data_sync,
        map_export_records_to_ad_snapshot,
    )

    result: dict = {
        "success": False,
        "ad_data": [],
        "price_data": [],
        "ad_count": 0,
        "price_count": 0,
        "total_responses": 0,
        "ad_api_responses": 0,
        "errors": [],
        "duration_seconds": 0,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "method": "csp_export",
    }

    t0 = time.perf_counter()
    browser_svc: BrowserService | None = None

    try:
        browser_svc = BrowserService(headless=headless)
        context = browser_svc.new_context(cookies=cookies)
        page = context.new_page()

        for prod in products:
            sku_id = prod.get("sku_id", "")
            if not sku_id:
                continue

            records: list[dict] = []
            for attempt in range(1 + CSP_EXPORT_MAX_RETRIES):
                try:
                    records = export_product_ad_data_sync(page, sku_id)
                    if records:
                        logger.info(
                            "CSP 导出成功 [SKU=%s] 尝试=%d 记录数=%d",
                            sku_id, attempt + 1, len(records),
                        )
                        break
                    logger.warning(
                        "CSP 导出无记录 [SKU=%s] 尝试=%d/{%d}",
                        sku_id, attempt + 1, CSP_EXPORT_MAX_RETRIES + 1,
                    )
                except Exception as exc:
                    logger.warning(
                        "CSP 导出异常 [SKU=%s] 尝试=%d: %s",
                        sku_id, attempt + 1, exc,
                    )
                    if attempt < CSP_EXPORT_MAX_RETRIES:
                        time.sleep(2)

            if not records:
                result["errors"].append(f"SKU {sku_id} CSP 导出失败（已重试）")
                continue

            # 映射为 AdSnapshot 格式
            mapped = map_export_records_to_ad_snapshot(records, sku_id)
            for snap in mapped:
                ad = CollectedAdData(
                    source_url="csp_export",
                    sku_id=snap.get("sku_id", sku_id),
                    impressions=snap.get("impressions", 0),
                    clicks=snap.get("clicks", 0),
                    ctr=snap.get("ctr", 0.0),
                    orders=snap.get("orders", 0),
                    conversion_rate=snap.get("conversion_rate", 0.0),
                    ad_spend=snap.get("ad_spend", 0.0),
                    revenue=snap.get("revenue", 0.0),
                    ad_type=snap.get("ad_type", "standard"),
                )
                result["ad_data"].append(ad)

                # 如果有价格信息，同时产出 price_data
                price = prod.get("current_price", prod.get("price", 0))
                if price and price > 0:
                    result["price_data"].append(
                        CollectedPriceData(
                            source_url="csp_export",
                            sku_id=sku_id,
                            current_price=float(price),
                        )
                    )

        page.close()
        context.close()

        result["ad_count"] = len(result["ad_data"])
        result["price_count"] = len(result["price_data"])
        result["success"] = True

    except Exception as exc:
        result["errors"].append(f"CSP 导出流程异常: {exc}")
    finally:
        if browser_svc is not None:
            browser_svc.close()
        result["duration_seconds"] = round(time.perf_counter() - t0, 2)

    return result


def _run_collection_sync(
    cookies: list[dict],
    headless: bool = True,
    timeout: int = 60,
) -> dict:
    """[回退路径] 在同步线程中执行 API 拦截数据采集。返回结构化结果。"""
    from App.services.browser import BrowserService

    result: dict = {
        "success": False,
        "ad_data": [],
        "price_data": [],
        "ad_count": 0,
        "price_count": 0,
        "total_responses": 0,
        "ad_api_responses": 0,
        "errors": [],
        "duration_seconds": 0,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "method": "api_intercept",
    }

    t0 = time.perf_counter()
    browser_svc: BrowserService | None = None

    try:
        browser_svc = BrowserService(headless=headless)
        context = browser_svc.new_context(cookies=cookies)
        page = context.new_page()
        interceptor = AdDataInterceptor()
        interceptor.attach(page)

        for page_url in AD_PAGES:
            try:
                page.goto(
                    page_url,
                    wait_until="domcontentloaded",
                    timeout=min(30_000, timeout * 1000),
                )
                page.wait_for_timeout(max(2_000, timeout * 50))
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
    """执行一次完整的数据采集，将结果写入数据库。

    采集策略:
      1. CSP SYCM 导出（主路径，USE_CSP_EXPORT=True 时启用）
      2. API 拦截（回退路径）
    """
    import asyncio

    # ── 前置检查：Cookie ──────────────────────────
    cookies = await cookie_manager.load_cookies("aliexpress.com")
    if not cookies:
        return error_response(ErrorCode.COOKIE_MISSING, details={"action": "请先执行首次登录"})

    # ── 检查全局停止 ──────────────────────────────
    if await is_global_stop_active(db):
        return error_response(ErrorCode.GLOBAL_STOP, details={"action": "请检查警报中心并清除全局停止"})

    # ── 查询已跟踪商品 ───────────────────────────
    prod_result = await db.execute(select(Product).where(Product.is_tracked))
    products = list(prod_result.scalars().all())

    loop = asyncio.get_event_loop()

    raw: dict | None = None

    # ── 主路径：CSP 导出 ─────────────────────────
    if USE_CSP_EXPORT and products:
        logger.info("采集策略: CSP SYCM 导出（%d 个商品）", len(products))
        prod_dicts = [
            {
                "sku_id": p.sku_id,
                "name": p.name,
                "category": p.category,
                "current_price": p.cost_price,
            }
            for p in products
        ]
        raw = await loop.run_in_executor(
            None, _run_csp_export_sync, prod_dicts, cookies, headless, CSP_EXPORT_TIMEOUT
        )

        if raw.get("success") and raw.get("ad_data"):
            logger.info(
                "CSP 导出成功: %d 条广告数据, %d 条价格数据",
                raw["ad_count"], raw["price_count"],
            )
        else:
            logger.warning(
                "CSP 导出未返回数据 (%s)，切换到 API 拦截回退",
                "; ".join(raw.get("errors", [])),
            )
            raw = None  # 触发回退

    # ── 回退路径：API 拦截 ───────────────────────
    if raw is None:
        logger.info("采集策略: API 拦截（回退路径）")
        raw = await loop.run_in_executor(
            None, _run_collection_sync, cookies, headless, timeout
        )

    if not raw.get("success"):
        return error_response(
            ErrorCode.NETWORK_ERROR,
            "数据采集失败: " + "; ".join(raw.get("errors", [])),
        )

    # ── 写入数据库 ────────────────────────────────
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
        "method": raw.get("method", "unknown"),
    }


# ── Product upsert via CSP export ─────────────────────


async def upsert_products_from_export(
    db: AsyncSession,
    cookie_manager: CookieManager,
    headless: bool = True,
    timeout: int = 60,
) -> dict:
    """使用 CSP 导出功能采集商品数据并 upsert 到 products 表。

    流程:
      1. 使用 product_scraper.scrape_products_via_export 从 CSP 导出商品列表
      2. 使用 PostgreSQL ON CONFLICT upsert 写入 products 表

    Args:
        db: 数据库会话
        cookie_manager: Cookie 管理器
        headless: 是否无头模式
        timeout: 导出等待超时（秒）

    Returns:
        {"success": bool, "upserted": int, "products": list, "errors": list, ...}
    """
    import asyncio

    from App.services.product_scraper import scrape_products_via_export

    # ── 前置检查：Cookie ──────────────────────────
    cookies = await cookie_manager.load_cookies("aliexpress.com")
    if not cookies:
        return error_response(ErrorCode.COOKIE_MISSING, details={"action": "请先执行首次登录"})

    # ── 执行导出采集 ──────────────────────────────
    export_result = await scrape_products_via_export(
        cookie_manager, headless=headless, timeout=timeout
    )

    if not export_result.get("success"):
        return {
            "success": False,
            "upserted": 0,
            "products": [],
            "errors": export_result.get("errors", ["导出采集失败"]),
            "duration_seconds": export_result.get("duration_seconds", 0),
        }

    products = export_result.get("products", [])
    if not products:
        return {
            "success": True,
            "upserted": 0,
            "products": [],
            "errors": ["导出文件为空，无商品数据需要同步"],
            "duration_seconds": export_result.get("duration_seconds", 0),
        }

    # ── Upsert 到 products 表 ─────────────────────
    upserted_count = 0
    upserted_skus: list[str] = []

    for prod in products:
        sku_id = prod.get("sku_id", "")
        name = prod.get("name", "")
        category = prod.get("category", "")

        if not sku_id or not name:
            continue

        try:
            stmt = PgInsert(Product).values(
                sku_id=sku_id,
                name=name,
                category=category if category else None,
                cost_price=0.0,  # 成本价默认值，用户可在控制台修改
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["sku_id"],
                set_={
                    "name": stmt.excluded.name,
                    "category": stmt.excluded.category,
                },
            )
            await db.execute(stmt)
            upserted_count += 1
            upserted_skus.append(sku_id)
        except Exception as exc:
            logger.error("商品 upsert 失败: sku=%s error=%s", sku_id, exc)

    await db.flush()

    logger.info(
        "商品数据同步完成: 导出 %d 件, upsert %d 件",
        len(products),
        upserted_count,
    )

    return {
        "success": True,
        "upserted": upserted_count,
        "total_exported": len(products),
        "products": upserted_skus,
        "errors": export_result.get("errors", []),
        "duration_seconds": export_result.get("duration_seconds", 0),
    }
