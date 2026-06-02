"""联盟营销数据采集模块 — 采集联盟推广商品、佣金率、效果数据.

采集策略:
  1. 使用 Playwright 导航到速卖通联盟营销页面
  2. 通过 API 拦截器捕获联盟数据 API 响应
  3. 提取佣金率、推广效果等结构化数据

设计原则:
  - 与 AdDataInterceptor 协作，复用 URL/字段匹配模式
  - 支持独立采集，不依赖 data_collector 主流程
  - 数据以 dataclass 返回，由调用方决定是否持久化
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from App.services.api_interceptor import AdDataInterceptor, CollectedAffiliateData

if TYPE_CHECKING:
    from App.services.cookie_manager import CookieManager

logger = logging.getLogger(__name__)


# ── 联盟数据采集页码 ──────────────────────────────
# 速卖通 CSP 联盟营销相关页面
AFFILIATE_PAGES = [
    "https://csp.aliexpress.com/m_apps/affiliate/home",
    "https://csp.aliexpress.com/m_apps/affiliate/commission",
    "https://csp.aliexpress.com/m_apps/affiliate/performance",
    "https://csp.aliexpress.com/m_apps/all-in-one-promotion/home",
]

# ── 采集超时配置 ──────────────────────────────────
AFFILIATE_TIMEOUT = 55
AFFILIATE_PAGE_WAIT = 3.0  # 页面加载后额外等待（秒）


@dataclass
class AffiliateCommissionItem:
    """联盟佣金条目 — 单个商品的佣金率信息。"""

    sku_id: str = ""
    product_name: str = ""
    commission_rate: float = 0.0
    commission_amount: float = 0.0
    price: float = 0.0


@dataclass
class AffiliatePerformanceItem:
    """联盟效果数据条目 — 单个商品的推广效果。"""

    sku_id: str = ""
    product_name: str = ""
    clicks: int = 0
    orders: int = 0
    commission_earned: float = 0.0
    revenue: float = 0.0
    conversion_rate: float = 0.0


@dataclass
class AffiliateCollectResult:
    """联盟数据采集结果。"""

    commissions: list[AffiliateCommissionItem] = field(default_factory=list)
    performance: list[AffiliatePerformanceItem] = field(default_factory=list)
    raw_affiliate_data: list[CollectedAffiliateData] = field(default_factory=list)
    total_pages_visited: int = 0
    total_api_responses: int = 0
    affiliate_api_responses: int = 0
    success: bool = False
    errors: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0
    collected_at: str = ""


class AffiliateCollector:
    """联盟营销数据采集器。

    使用 Playwright 导航到速卖通 CSP 联盟营销页面，
    通过 AdDataInterceptor 捕获 API 响应中的联盟推广数据。

    使用方式:
        collector = AffiliateCollector(headless=True)
        result = collector.collect(cookies)
    """

    def __init__(self, headless: bool = True) -> None:
        self.headless = headless
        self.result = AffiliateCollectResult()

    def collect(
        self,
        cookies: list[dict[str, Any]],
        timeout: int = AFFILIATE_TIMEOUT,
    ) -> AffiliateCollectResult:
        """执行一次联盟数据采集。

        Args:
            cookies: Playwright 格式的 cookie 列表
            timeout: 单次操作超时（秒）

        Returns:
            AffiliateCollectResult 包含采集到的联盟数据
        """
        t0 = time.perf_counter()
        self.result = AffiliateCollectResult()
        self.result.collected_at = datetime.now(UTC).isoformat()

        from App.services.browser import BrowserService

        browser_svc: BrowserService | None = None

        try:
            browser_svc = BrowserService(headless=self.headless)
            context = browser_svc.new_context(cookies=cookies)
            page = context.new_page()
            interceptor = AdDataInterceptor()
            interceptor.attach(page)

            for page_url in AFFILIATE_PAGES:
                try:
                    page.goto(
                        page_url,
                        wait_until="domcontentloaded",
                        timeout=min(30_000, timeout * 1000),
                    )
                    page.wait_for_timeout(int(AFFILIATE_PAGE_WAIT * 1000))
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    page.wait_for_timeout(2_000)
                    self.result.total_pages_visited += 1
                except Exception as exc:
                    self.result.errors.append(f"页面 {page_url} 访问异常: {exc}")

            page.close()
            context.close()

            # ── 提取采集结果 ─────────────────────
            self.result.raw_affiliate_data = interceptor.result.affiliate_data
            self.result.total_api_responses = interceptor.result.total_responses
            self.result.affiliate_api_responses = interceptor.result.ad_api_responses

            # 转换 raw_affiliate_data 为结构化的佣金和效果列表
            for aff in interceptor.result.affiliate_data:
                # 有佣金率的归入佣金列表
                if aff.commission_rate > 0 or aff.commission_amount > 0:
                    self.result.commissions.append(
                        AffiliateCommissionItem(
                            sku_id=aff.sku_id,
                            product_name=aff.product_name,
                            commission_rate=aff.commission_rate,
                            commission_amount=aff.commission_amount,
                            price=aff.revenue if aff.revenue > 0 else 0.0,
                        )
                    )
                # 有点击/订单的归入效果列表
                if aff.clicks > 0 or aff.orders > 0 or aff.revenue > 0:
                    self.result.performance.append(
                        AffiliatePerformanceItem(
                            sku_id=aff.sku_id,
                            product_name=aff.product_name,
                            clicks=aff.clicks,
                            orders=aff.orders,
                            commission_earned=aff.commission_amount,
                            revenue=aff.revenue,
                            conversion_rate=aff.conversion_rate,
                        )
                    )

            self.result.success = True

            if not self.result.errors:
                logger.info(
                    "联盟数据采集完成: %d 页, %d 佣金条目, %d 效果条目",
                    self.result.total_pages_visited,
                    len(self.result.commissions),
                    len(self.result.performance),
                )

        except Exception as exc:
            self.result.errors.append(f"采集流程异常: {exc}")
            logger.error("联盟数据采集异常: %s", exc)
        finally:
            if browser_svc is not None:
                browser_svc.close()
            self.result.duration_seconds = round(time.perf_counter() - t0, 2)

        return self.result

    async def collect_async(
        self,
        cookie_manager: CookieManager,
        timeout: int = AFFILIATE_TIMEOUT,
    ) -> AffiliateCollectResult:
        """异步联盟数据采集（在 executor 中执行同步 collect）。"""
        import asyncio

        cookies = await cookie_manager.load_cookies("aliexpress.com")
        if not cookies:
            self.result.errors.append("Cookie 不可用，请先执行首次登录")
            self.result.success = False
            return self.result

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None, self.collect, cookies, timeout
        )
        return result


def format_affiliate_result(result: AffiliateCollectResult) -> dict:
    """将 AffiliateCollectResult 格式化为可序列化的 dict。

    用于 API 响应返回。
    """
    return {
        "success": result.success,
        "total_pages_visited": result.total_pages_visited,
        "total_api_responses": result.total_api_responses,
        "affiliate_api_responses": result.affiliate_api_responses,
        "commissions": [
            {
                "sku_id": c.sku_id,
                "product_name": c.product_name,
                "commission_rate": c.commission_rate,
                "commission_amount": c.commission_amount,
                "price": c.price,
            }
            for c in result.commissions
        ],
        "performance": [
            {
                "sku_id": p.sku_id,
                "product_name": p.product_name,
                "clicks": p.clicks,
                "orders": p.orders,
                "commission_earned": p.commission_earned,
                "revenue": p.revenue,
                "conversion_rate": p.conversion_rate,
            }
            for p in result.performance
        ],
        "errors": result.errors,
        "duration_seconds": result.duration_seconds,
        "collected_at": result.collected_at,
    }
