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

# ── 价格数据识别模式 ────────────────────────────
# 扩展字段名覆盖更多速卖通 API 响应中的价格字段变体
_PRICE_FIELD_PATTERNS: dict[str, list[str]] = {
    "current_price": [
        "currentPrice", "current_price", "price", "sellPrice", "salePrice",
        "unitPrice", "itemPrice", "originalPrice", "priceAmount", "priceValue",
        "actualPrice", "totalPrice", "minPrice", "maxPrice",
        "单品价格", "商品价格", "单价", "价格",
    ],
    "sku_id": [
        "skuId", "sku_id", "productId", "product_id",
        "itemId", "item_id", "offerId", "offer_id",
    ],
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
    """递归搜索 JSON，找出所有包含广告或价格字段的对象。

    将所有模式组中的字段名展平后一同检查，避免只检查第一组而漏检。
    """
    all_patterns = [p for patterns in field_patterns.values() for p in patterns]
    results: list[dict] = []
    if isinstance(data, dict):
        if _has_any_key(data, all_patterns):
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


# ── 价格 API URL 特征（含商品/订单/详情等价格渠道） ─
_PRICE_URL_PATTERNS = [
    # CSP 商品/订单/详情 API
    r"seller-acs\.aliexpress\.com/h5/mtop.*product",
    r"seller-acs\.aliexpress\.com/h5/mtop.*offer",
    r"seller-acs\.aliexpress\.com/h5/mtop.*item",
    r"seller-acs\.aliexpress\.com/h5/mtop.*price",
    r"seller-acs\.aliexpress\.com/h5/mtop.*order",
    r"seller-acs\.aliexpress\.com/h5/mtop.*detail",
    r"seller-acs\.aliexpress\.com/h5/mtop.*logistics",
    r"seller-acs\.aliexpress\.com/h5/mtop.*freight",
    # 通用电商路径
    r"/product/",
    r"/offer/",
    r"/item/",
    r"/price/",
    r"/detail/",
]


def _is_price_api(url: str) -> bool:
    return any(re.search(pattern, url, re.IGNORECASE) for pattern in _PRICE_URL_PATTERNS)


# ── 拦截器 ──────────────────────────────────────

# ── 备选价格提取策略（正则匹配含 "price" 的键） ──
_PRICE_KEY_RE = re.compile(r"price", re.IGNORECASE)


def _extract_price_fallback(body: Any) -> list[tuple[str, float]]:
    """备选价格提取：递归搜索 JSON，匹配键名含 'price' 的字段。

    Returns:
        list of (sku_id, price_value) tuples.
    """
    results: list[tuple[str, float]] = []

    def _search(data: Any, path: str = "") -> None:
        if isinstance(data, dict):
            sku = str(_find_value(data, _AD_FIELD_PATTERNS["sku_id"]) or "")
            for key, value in data.items():
                if isinstance(key, str) and _PRICE_KEY_RE.search(key):
                    p = _safe_float(value)
                    if p > 0:
                        results.append((sku, p))
                _search(value, f"{path}/{key}")
        elif isinstance(data, list):
            for item in data:
                _search(item, path)

    _search(body)
    return results


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
    """价格采集数据。包含来源溯源和多源追踪字段。"""
    source_url: str = ""
    sku_id: str = ""
    current_price: float = 0.0
    all_prices: dict[str, float] | None = None  # 字段名 -> 价格值，用于一致性校验
    price_source_count: int = 0  # 从多少个 API 来源提取到价格
    is_fallback: bool = False  # 是否通过备选策略提取


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
        is_ad = _is_ad_api(url)
        is_price = _is_price_api(url)

        # 只处理广告或价格相关的 API 响应
        if not is_ad and not is_price:
            return

        if is_ad:
            self.result.ad_api_responses += 1

        try:
            body = response.json()
        except Exception:
            return

        if not isinstance(body, (dict, list)):
            return

        if is_ad:
            self._extract_ad_data(url, body)
        self._extract_price_data(url, body, is_pure_price=is_price and not is_ad)

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

    def _extract_price_data(self, url: str, body: Any, is_pure_price: bool = False) -> None:
        """从 API 响应中提取价格数据。

        采用主备双策略：
          主策略 — 按已知字段名精确匹配
          备策略 — 当主策略无结果时，正则搜索含 'price' 的键

        Args:
            url: 来源 API URL。
            body: 解析后的 JSON 响应体。
            is_pure_price: 是否来自纯价格 API（非广告 API），用于统计。
        """
        # 主策略：搜索已知价格字段模式
        candidates = _find_all_dicts(body, _PRICE_FIELD_PATTERNS)
        for candidate in candidates:
            price = CollectedPriceData(source_url=url)
            price.sku_id = str(_find_value(candidate, _AD_FIELD_PATTERNS["sku_id"]) or "")

            # 收集该对象中所有价格字段的值，用于一致性追踪
            all_prices: dict[str, float] = {}
            for field_name, patterns in _PRICE_FIELD_PATTERNS.items():
                if field_name == "sku_id":
                    continue
                val = _find_value(candidate, patterns)
                if val is not None:
                    p = _safe_float(val)
                    if p > 0:
                        all_prices[field_name] = p

            # 优先使用 current_price 组的值，否则取第一个有效价格
            price.all_prices = all_prices if all_prices else None
            price.price_source_count = len(all_prices)
            if "current_price" in all_prices:
                price.current_price = all_prices["current_price"]
            elif all_prices:
                price.current_price = next(iter(all_prices.values()))

            if price.current_price > 0 or price.sku_id:
                self.result.price_data.append(price)

        # 备策略：主策略没有找到有效价格时，使用正则搜索含 "price" 的键
        if not self.result.price_data or is_pure_price:
            fallback_prices = _extract_price_fallback(body)
            for sku_id, price_val in fallback_prices:
                # 避免与主策略结果重复
                already_exists = any(
                    p.sku_id == sku_id and abs(p.current_price - price_val) < 0.01
                    for p in self.result.price_data
                )
                if not already_exists:
                    fp = CollectedPriceData(
                        source_url=url,
                        sku_id=sku_id,
                        current_price=price_val,
                        is_fallback=True,
                    )
                    self.result.price_data.append(fp)
