"""API 请求拦截器 — 监听速卖通后台网络请求，提取广告和价格数据.

提供结构变更检测:
  - detect_structure_change() 分析拦截结果，返回疑似 API 字段/URL 变更的信号
  - 在采集流程中调用，避免后端 API 改版后静默失败
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from App.core.logging import get_logger

logger = get_logger(__name__)

from playwright.sync_api import Page, Response as PWResponse


# ── 广告数据识别模式 ────────────────────────────
# 速卖通后台 API 可能使用多种字段名（驼峰/下划线/缩写）
_AD_FIELD_PATTERNS: dict[str, list[str]] = {
    "impressions": [
        "impression", "impressions", "impressionCnt", "showCnt",
        "impression_count", "展现", "展现量", "展示", "曝光", "曝光量",
    ],
    "clicks": ["click", "clicks", "clickCnt", "click_count", "点击", "点击量", "клик", "clic"],
    "ctr": ["ctr", "clickRate", "click_rate", "ctrRate", "点击率"],
    "orders": [
        "order", "orders", "orderCnt", "orderCount", "order_count",
        "transactionCnt", "订单", "订单量", "заказ",
    ],
    "conversion_rate": [
        "conversionRate", "conversion_rate", "cvr", "cvrRate",
        "orderRate", "转化率", "конверсия",
    ],
    "ad_spend": [
        "spend", "cost", "adSpend", "adCost", "ad_spend",
        "charge", "consumeAmt", "花费", "消耗", "расход",
    ],
    "revenue": [
        "revenue", "sales", "salesAmt", "salesAmount",
        "revenueAmt", "transAmt", "销售额", "выручка",
    ],
    "ad_type": [
        "adType", "ad_type", "campaignType", "campaign_type", "marketingType", "广告类型",
    ],
    "buyer_region": [
        "buyerRegionBreakdown", "buyer_region_breakdown",
        "regionBreakdown", "countryBreakdown", "areaDistribution",
        "regionList", "countryList", "国家", "地区",
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
    # ── 实时 mtop API (CSP 卖家中心) ────────────
    r"seller-acs\.aliexpress\.com/h5/mtop.*adv",
    r"seller-acs\.aliexpress\.com/h5/mtop.*campaign",
    r"seller-acs\.aliexpress\.com/h5/mtop.*promotion",
    r"seller-acs\.aliexpress\.com/h5/mtop.*advert",
    r"seller-acs\.aliexpress\.com/h5/mtop.*dashboard",
    r"seller-acs\.aliexpress\.com/h5/mtop.*report",
    r"seller-acs\.aliexpress\.com/h5/mtop.*performance",
    r"seller-acs\.aliexpress\.com/h5/mtop.*bidding",
    r"seller-acs\.aliexpress\.com/h5/mtop.*budget",
    r"seller-acs\.aliexpress\.com/h5/mtop.*effect",
    r"seller-acs\.aliexpress\.com/h5/mtop.*insight",
    # ── 旧版 API 模式 ──────────────────────────
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
    r"dashboard",
    r"performance",
    r"analytics",
    r"insight",
    r"overview",
    r"creative",
    r"targeting",
    r"bidding",
    r"budget",
    r"roi",
    r"conversion",
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
    # ── 结构变更检测字段 ──────────────────────────
    responses_without_match: int = 0  # 匹配 URL 但未提取到任何字段的响应数
    response_urls: list[str] = field(default_factory=list)  # 所有 API 响应 URL


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
        self.result.response_urls.append(url)

        try:
            body = response.json()
        except Exception:
            self.result.responses_without_match += 1
            return

        if not isinstance(body, (dict, list)):
            self.result.responses_without_match += 1
            return

        # 记录本次响应中是否提取到数据
        ad_before = len(self.result.ad_data)
        price_before = len(self.result.price_data)

        self._extract_ad_data(url, body)
        self._extract_price_data(url, body)

        if len(self.result.ad_data) == ad_before and len(self.result.price_data) == price_before:
            # API 响应已匹配 URL 模式，但字段提取未命中
            self.result.responses_without_match += 1

    def detect_structure_change(self) -> dict:
        """分析当前拦截结果，返回结构变更检测报告。

        报告包含:
          - detected: bool — 是否检测到疑似结构变更
          - confidence: float — 0.0 ~ 1.0
          - reason: str — 判断依据
          - metrics: dict — 诊断指标

        判断逻辑:
          1. 零 API 响应: 页面可能完全改版（URL 模式全部失效）
          2. 全部未命中: 所有 API 响应都无法提取数据（字段名已变更）
          3. 部分未命中: 部分 API 数据格式已变化（渐进式改版）
          4. 正常: 大部分 API 响应都能正常提取数据
        """
        total_api = self.result.ad_api_responses
        total_matched_ad = len(self.result.ad_data)
        total_matched_price = len(self.result.price_data)
        total_matched = total_matched_ad + total_matched_price
        no_match = self.result.responses_without_match

        metrics = {
            "total_api_responses": total_api,
            "total_ad_records": total_matched_ad,
            "total_price_records": total_matched_price,
            "responses_without_match": no_match,
        }

        # ── 场景 1: 没有 API 响应 ──────────────────
        if total_api == 0 and self.result.total_responses > 0:
            # 有普通响应但没有 API 响应 → URL 模式可能全部失效
            return {
                "detected": True,
                "confidence": 0.9,
                "reason": "页面已加载但未捕获任何广告 API 响应，URL 模式可能已变更",
                "metrics": metrics,
            }

        # ── 场景 2: 全部未命中 ─────────────────────
        if total_api > 0 and no_match == total_api and total_matched == 0:
            return {
                "detected": True,
                "confidence": 0.85,
                "reason": (
                    f"共捕获 {total_api} 个 API 响应，但均无法提取广告或价格数据。"
                    "API 返回格式可能已变更"
                ),
                "metrics": metrics,
            }

        # ── 场景 3: 高比例未命中 ───────────────────
        if total_api > 3 and no_match > 0:
            match_rate = 1.0 - (no_match / total_api)
            if match_rate < 0.3:
                return {
                    "detected": True,
                    "confidence": 0.75,
                    "reason": (
                        f"API 响应匹配率仅 {match_rate:.0%} "
                        f"({total_api - no_match}/{total_api})，"
                        "字段模式可能已部分失效"
                    ),
                    "metrics": {**metrics, "match_rate": round(match_rate, 2)},
                }
            if match_rate < 0.6:
                return {
                    "detected": True,
                    "confidence": 0.5,
                    "reason": (
                        f"API 响应匹配率 {match_rate:.0%} "
                        f"({total_api - no_match}/{total_api})，"
                        "部分 API 格式可能已变化，建议关注"
                    ),
                    "metrics": {**metrics, "match_rate": round(match_rate, 2)},
                }

        # ── 场景 4: 正常 ───────────────────────────
        return {
            "detected": False,
            "confidence": 0.0,
            "reason": "结构正常",
            "metrics": metrics,
        }

    def _extract_ad_data(self, url: str, body: Any) -> None:
        candidates = _find_all_dicts(body, _AD_FIELD_PATTERNS)
        for candidate in candidates:
            ad = CollectedAdData(source_url=url)
            ad.sku_id = str(_find_value(candidate, _AD_FIELD_PATTERNS["sku_id"]) or "")
            ad.impressions = _safe_int(_find_value(candidate, _AD_FIELD_PATTERNS["impressions"]))
            ad.clicks = _safe_int(_find_value(candidate, _AD_FIELD_PATTERNS["clicks"]))
            ad.ctr = _safe_float(_find_value(candidate, _AD_FIELD_PATTERNS["ctr"]))
            ad.orders = _safe_int(_find_value(candidate, _AD_FIELD_PATTERNS["orders"]))
            ad.conversion_rate = _safe_float(
                _find_value(candidate, _AD_FIELD_PATTERNS["conversion_rate"])
            )
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
            price.current_price = _safe_float(
                _find_value(candidate, _PRICE_FIELD_PATTERNS["current_price"])
            )
            if price.current_price > 0 or price.sku_id:
                self.result.price_data.append(price)
