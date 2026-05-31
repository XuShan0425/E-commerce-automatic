"""费率 AI 解析编排 — 串联抓取 → AI 解析 → 确认写入流程."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from sqlalchemy import delete as sql_delete

from App.schemas.rates import (
    ConfirmFeesRequest,
    ConfirmLogisticsRequest,
    ParseResultFees,
    ParseResultLogistics,
    ParsedLogisticsRate,
    ParsedPlatformFee,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
    from App.services.browser import BrowserService

logger = logging.getLogger(__name__)


async def parse_logistics_rates(
    browser_service: BrowserService,
) -> ParseResultLogistics:
    """抓取物流费率页面并 AI 解析。

    抓取在后台线程执行（BrowserService 是同步的），AI 解析原生异步调用。
    """
    from App.services.ai_client import parse_logistics_html
    from App.services.rate_scraper import DEFAULT_LOGISTICS_URL, fetch_logistics_page_sync

    source_url = DEFAULT_LOGISTICS_URL
    raw_response = ""
    parsed_items: list[ParsedLogisticsRate] = []

    try:
        loop = asyncio.get_event_loop()
        html = await loop.run_in_executor(None, fetch_logistics_page_sync, browser_service)
        raw_data = await parse_logistics_html(html)
        import json
        raw_response = json.dumps(raw_data, ensure_ascii=False, indent=2)

        for item in raw_data:
            try:
                parsed_items.append(ParsedLogisticsRate(
                    destination_region=str(item.get("destination_region", "")).upper(),
                    weight_range_min=float(item.get("weight_range_min", 0)),
                    weight_range_max=float(item.get("weight_range_max", 0)),
                    cost=float(item.get("cost", 0)),
                ))
            except (ValueError, TypeError) as exc:
                logger.warning("跳过无效费率条目: %s — %s", item, exc)

    except Exception as exc:
        logger.error("物流费率解析失败: %s", exc)
        raw_response = str(exc)

    return ParseResultLogistics(
        source_url=source_url,
        parsed_items=parsed_items,
        raw_ai_response=raw_response,
    )


async def parse_platform_fees(
    browser_service: BrowserService,
) -> ParseResultFees:
    """抓取平台佣金页面并 AI 解析。

    抓取在后台线程执行（BrowserService 是同步的），AI 解析原生异步调用。
    """
    from App.services.ai_client import parse_fees_html
    from App.services.rate_scraper import DEFAULT_FEES_URL, fetch_fees_page_sync

    source_url = DEFAULT_FEES_URL
    raw_response = ""
    parsed_items: list[ParsedPlatformFee] = []

    try:
        loop = asyncio.get_event_loop()
        html = await loop.run_in_executor(None, fetch_fees_page_sync, browser_service)
        raw_data = await parse_fees_html(html)
        import json
        raw_response = json.dumps(raw_data, ensure_ascii=False, indent=2)

        for item in raw_data:
            try:
                parsed_items.append(ParsedPlatformFee(
                    category=str(item.get("category", "")),
                    fee_rate=float(item.get("fee_rate", 0)),
                ))
            except (ValueError, TypeError) as exc:
                logger.warning("跳过无效佣金条目: %s — %s", item, exc)

    except Exception as exc:
        logger.error("平台佣金解析失败: %s", exc)
        raw_response = str(exc)

    return ParseResultFees(
        source_url=source_url,
        parsed_items=parsed_items,
        raw_ai_response=raw_response,
    )


async def confirm_logistics_rates(
    db: AsyncSession,
    request: ConfirmLogisticsRequest,
) -> dict:
    """确认物流费率并写入数据库。"""
    from App.models.base import LogisticsRate

    if request.overwrite:
        await db.execute(sql_delete(LogisticsRate))
        await db.flush()

    count = 0
    for item in request.items:
        rate = LogisticsRate(**item.model_dump())
        db.add(rate)
        count += 1

    await db.flush()
    logger.info("物流费率确认写入: %d 条 (overwrite=%s)", count, request.overwrite)

    return {
        "inserted": count if not request.overwrite else 0,
        "replaced": count if request.overwrite else 0,
    }


async def confirm_platform_fees(
    db: AsyncSession,
    request: ConfirmFeesRequest,
) -> dict:
    """确认平台佣金并写入数据库。"""
    from App.models.base import PlatformFee

    if request.overwrite:
        await db.execute(sql_delete(PlatformFee))
        await db.flush()

    count = 0
    for item in request.items:
        fee = PlatformFee(**item.model_dump())
        db.add(fee)
        count += 1

    await db.flush()
    logger.info("平台佣金确认写入: %d 条 (overwrite=%s)", count, request.overwrite)

    return {
        "inserted": count if not request.overwrite else 0,
        "replaced": count if request.overwrite else 0,
    }
