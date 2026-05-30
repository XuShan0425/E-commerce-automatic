"""API 请求拦截器 — 监听速卖通后台网络请求，提取广告和价格数据."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from playwright.sync_api import Page, Response as PWResponse


# ── 广告数据识别模式 ────────────────────────────
# 速卖通后台 API 可能使用多种字段名（驼峰/下划线/缩写）
_AD_FIELD_PATTERNS: dict[str, list[str]] = {
    "impressions": ["impression", "impressions", "impressionCnt", "showCnt", "impression_count"],
    "clicks": ["click", "clicks", "clickCnt", "click_count"],
    "ctr": ["ctr", "clickRate", "click_rate", "ctrRate"],
    "orders": ["order", "orders", "orderCnt", "orderCount", "order_count", "transactionCnt"],
    "conversion_rate": ["conversionRate", "conversion_rate", "cvr", "cvrRate", "orderRate"],
    "ad_spend": ["spend", "cost", "adSpend", "adCost", "ad_spend", "charge", "consumeAmt"],
    "revenue": ["revenue", "sales", "salesAmt", "salesAmount", "revenueAmt", "transAmt"],
    "ad_type": ["adType", "ad_type", "campaignType", "campaign_type", "marketingType"],
    "buyer_region": [
        "buyerRegionBreakdown", "buyer_region_breakdown",
        "regionBreakdown", "countryBreakdown", "areaDistribution",
        "regionList", "countryList",
    ],
    "sku_id": ["skuId", "sku_id", "productId", "product_id", "itemId", "item_id"],
}

_PRICE_FIELD_PATTERNS: dict[str, list[str]] = {
    "current_price": ["currentPrice", "current_price", "price", "sellPrice", "salePrice"],
}


def _has_any_key(data: dict, patterns: list[str]) -> bool:
    """递归检查 JSON 对象（含嵌套）是否包含模式中的任一键。"""
    if not isinstance(data, dict):
        return False
    for key in data:
        if key in patterns or key.lower() in [p.lower() for p in patterns]:
            return True
    for value in data.values():
        if isinstance(value, dict):
            if _has_any_key(value, patterns):
                return True
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict) and _has_any_key(item, patterns):
                    return True
    return False


def _find_value(data: dict, patterns: list[str]) -> Any | None:
    """在 JSON 对象中递归查找匹配模式的第一个值。"""
    if not isinstance(data, dict):
        return None
    lower_patterns = [p.lower() for p in patterns]
    for key, value in data.items():
        if key in patterns or key.lower() in lower_patterns:
            return value
    for value in data.values():
        if isinstance(value, dict):
            found = _find_value(value, patterns)
            if found is not None:
                return found
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    found = _find_value(item, patterns)
                    if found is not None:
                        return found
    return None


def _find_all_dicts(data: Any, field_patterns: dict[str, list[str]]) -> list[dict]:
    """递归搜索 JSON，找出所有包含广告字段的对象。"""
    results: list[dict] = []
    if isinstance(data, dict):
        if _has_any_key(data, list(field_patterns.values())[0]):
            # 这个对象可能包含广告数据
            results.append(data)
        for value in data.values():
            results.extend(_find_all_dicts(value, field_patterns))
    elif isinstance(data, list):
        for item in data:
            results.extend(_find_all_dicts(item, field_patterns))
    return results


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


# ── 广告 API URL 特征 ───────────────────────────
_AD_URL_PATTERNS = [
    r"gsp\.aliexpress\.com",
    r"alds\.aliexpress\.com",
    r"/ad/",
    r"/campaign/",
    r"/promotion/",
    r"/report/",
    r"effect",
    r"advert",
    r"recommend",
    r"traffic",
]


def _is_ad_api(url: str) -> bool:
    return any(re.search(pattern, url, re.IGNORECASE) for pattern in _AD_URL_PATTERNS)


# ── 拦截器 ──────────────────────────────────────

@dataclass
class CollectedAdData:
    source_url: str = ""
    sku_id: str = ""
    impressions: int = 0
    clicks: int = 0
    ctr: float = 0.0
    orders: int = 0
    conversion_rate: float = 0.0
    ad_spend: float = 0.0
    revenue: float = 0.0
    ad_type: str = "unknown"
    buyer_region_breakdown: dict | None = None
    raw_data: dict | None = None


@dataclass
class CollectedPriceData:
    source_url: str = ""
    sku_id: str = ""
    current_price: float = 0.0


@dataclass
class InterceptResult:
    ad_data: list[CollectedAdData] = field(default_factory=list)
    price_data: list[CollectedPriceData] = field(default_factory=list)
    total_responses: int = 0
    ad_api_responses: int = 0


class AdDataInterceptor:
    """Playwright 网络拦截器：监听 response 事件，提取广告和价格数据。"""

    def __init__(self) -> None:
        self.result = InterceptResult()

    def reset(self) -> None:
        self.result = InterceptResult()

    def attach(self, page: Page) -> None:
        """将拦截器注册到 Playwright page。"""
        self.reset()
        page.on("response", self._on_response)

    def _on_response(self, response: PWResponse) -> None:
        self.result.total_responses += 1

        url = response.url
        # 只处理 API 请求
        if not _is_ad_api(url):
            return

        self.result.ad_api_responses += 1

        try:
            body = response.json()
        except Exception:
            return

        if not isinstance(body, (dict, list)):
            return

        self._extract_ad_data(url, body)
        self._extract_price_data(url, body)

    def _extract_ad_data(self, url: str, body: Any) -> None:
        candidates = _find_all_dicts(body, _AD_FIELD_PATTERNS)
        for candidate in candidates:
            ad = CollectedAdData(source_url=url)
            ad.sku_id = str(_find_value(candidate, _AD_FIELD_PATTERNS["sku_id"]) or "")
            ad.impressions = _safe_int(_find_value(candidate, _AD_FIELD_PATTERNS["impressions"]))
            ad.clicks = _safe_int(_find_value(candidate, _AD_FIELD_PATTERNS["clicks"]))
            ad.ctr = _safe_float(_find_value(candidate, _AD_FIELD_PATTERNS["ctr"]))
            ad.orders = _safe_int(_find_value(candidate, _AD_FIELD_PATTERNS["orders"]))
            ad.conversion_rate = _safe_float(_find_value(candidate, _AD_FIELD_PATTERNS["conversion_rate"]))
            ad.ad_spend = _safe_float(_find_value(candidate, _AD_FIELD_PATTERNS["ad_spend"]))
            ad.revenue = _safe_float(_find_value(candidate, _AD_FIELD_PATTERNS["revenue"]))
            ad.ad_type = str(_find_value(candidate, _AD_FIELD_PATTERNS["ad_type"]) or "unknown")
            region = _find_value(candidate, _AD_FIELD_PATTERNS["buyer_region"])
            if isinstance(region, (dict, list)):
                ad.buyer_region_breakdown = region
            ad.raw_data = candidate

            # 至少要有一些关键字段才算有效数据
            if ad.impressions > 0 or ad.clicks > 0 or ad.ad_spend > 0 or ad.sku_id:
                self.result.ad_data.append(ad)

    def _extract_price_data(self, url: str, body: Any) -> None:
        candidates = _find_all_dicts(body, _PRICE_FIELD_PATTERNS)
        for candidate in candidates:
            price = CollectedPriceData(source_url=url)
            price.sku_id = str(_find_value(candidate, _AD_FIELD_PATTERNS["sku_id"]) or "")
            price.current_price = _safe_float(_find_value(candidate, _PRICE_FIELD_PATTERNS["current_price"]))
            if price.current_price > 0 or price.sku_id:
                self.result.price_data.append(price)
