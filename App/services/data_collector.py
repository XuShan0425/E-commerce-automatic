"""数据采集编排器 — 浏览器 + Cookie + 拦截器 + DB写入全流程."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from App.services.api_interceptor import AdDataInterceptor, CollectedAdData, CollectedPriceData
from App.core.errors import ErrorCode, error_response
from App.core.logging import get_logger
from App.models.base import AdSnapshot, PriceSnapshot
from App.models.system_state import is_global_stop_active

if TYPE_CHECKING:
    from App.services.browser import BrowserService
    from App.services.cookie_manager import CookieManager

logger = get_logger(__name__)


# ── 重试策略 ──────────────────────────────────────

@dataclass
class RetryConfig:
    """指数退避重试配置。"""

    max_retries: int = 3
    base_delay: float = 2.0  # 首次重试延迟 (秒)
    backoff_factor: float = 2.0  # 指数退避因子


# 不可重试的异常基类标记
class NonRetryableError(Exception):
    """标记为不可重试的异常。任何继承自此类或其子类的异常都不会被重试。"""
    pass


class CookieOrAuthError(NonRetryableError):
    """Cookie 失效 / 登录失败 / 认证相关异常 — 应触发硬边界警报。"""
    pass


class BrowserCrashError(NonRetryableError):
    """浏览器崩溃异常 — 应重启浏览器。"""
    pass


_RETRYABLE_EXCEPTIONS: tuple[type[Exception], ...] = (
    asyncio.TimeoutError,
    TimeoutError,
    ConnectionError,
    ConnectionResetError,
    ConnectionAbortedError,
    ConnectionRefusedError,
)


def is_retryable(exc: Exception) -> bool:
    """判断异常是否可重试。

    规则：
    - 继承自 NonRetryableError 的异常 → 不可重试
    - 属于 _RETRYABLE_EXCEPTIONS 元组中的类型 → 可重试
    - 其余异常 → 不可重试
    """
    if isinstance(exc, NonRetryableError):
        return False
    return isinstance(exc, _RETRYABLE_EXCEPTIONS)


def is_http_5xx(exc: Exception) -> bool:
    """判断异常消息是否暗示 HTTP 5xx 响应码。"""
    msg = str(exc).lower()
    return any(f"5{x}" in msg for x in range(0, 10, 1))


def _calc_delay(attempt: int, config: RetryConfig) -> float:
    """计算第 attempt 次重试的等待时间（指数退避）。"""
    return config.base_delay * (config.backoff_factor ** (attempt - 1))


def with_retry(
    fn: Callable[[], Any],
    config: RetryConfig | None = None,
    context: str = "",
) -> Any:
    """通用同步重试包装器。

    使用指数退避策略处理可恢复错误。不可重试的异常直接透传。
    浏览器崩溃 / 页面 crash 会被转换为 BrowserCrashError 透传。

    Args:
        fn: 要执行的同步可调用对象。
        config: 重试配置（默认 RetryConfig()）。
        context: 日志上下文描述，如访问的页面 URL。

    Returns:
        fn 的返回值。

    Raises:
        透传 fn 抛出的任何异常（重试耗尽后抛出最后一次异常）。
    """
    cfg = config or RetryConfig()
    last_exc: Exception | None = None

    for attempt in range(1, cfg.max_retries + 2):  # +1 表示首次执行
        try:
            return fn()
        except Exception as exc:
            last_exc = exc

            # 页面崩溃 / 浏览器断开 — 包装为 BrowserCrashError 透传
            if _looks_like_page_crash(exc):
                raise BrowserCrashError(str(exc)) from exc

            # 不可重试异常 → 直接透传
            if not is_retryable(exc) and not is_http_5xx(exc):
                raise

            if attempt > cfg.max_retries:
                # 重试耗尽
                logger.error(
                    "retry_exhausted",
                    extra={
                        "context": context,
                        "attempt": attempt - 1,
                        "max_retries": cfg.max_retries,
                        "exception_type": type(exc).__name__,
                        "error": str(exc),
                    },
                )
                raise

            # 计算并等待
            delay = _calc_delay(attempt, cfg)
            logger.warn(
                "retry_attempt",
                extra={
                    "context": context,
                    "attempt": attempt,
                    "max_retries": cfg.max_retries,
                    "next_delay_seconds": delay,
                    "exception_type": type(exc).__name__,
                    "error": str(exc),
                },
            )
            time.sleep(delay)

    # 不会到达这里，但满足类型检查
    assert last_exc is not None
    raise last_exc

# ── 速卖通卖家中心页面 (2026-05-31 实测) ────────
# 旧域名 gsp.aliexpress.com 已废弃，新架构统一用 csp.aliexpress.com
# ad.aliexpress.com 需独立登录且返回空页面 — 改用 CSP 内部推广入口
AD_PAGES = [
    "https://csp.aliexpress.com/",  # CSP 首页 (触发 dashboard API)
    "https://csp.aliexpress.com/m_apps/p4p-pages/home?p4p_enter_from=sidebar",  # P4P 站内推广
    "https://csp.aliexpress.com/m_apps/all-in-one-promotion/home",  # 一站式推广
]


# ── 用于判断 Playwright 页面崩溃的辅助函数 ──────────
_PAGE_CRASH_KEYWORDS = [
    "page.crashed",
    "page.worker_terminated",
    "target closed",
    "browser has been disconnected",
    "protocol error",
    "crash",
]


def _looks_like_page_crash(exc: Exception) -> bool:
    """通过异常消息推测是否为页面崩溃/浏览器断开等不可重试错误。"""
    msg = str(exc).lower()
    return any(kw in msg for kw in _PAGE_CRASH_KEYWORDS)


def _run_collection_sync(
    cookies: list[dict],
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
        context = browser_svc.new_context(cookies=cookies)
        page = context.new_page()
        interceptor = AdDataInterceptor()
        interceptor.attach(page)

        retry_cfg = RetryConfig()

        # 逐个访问广告相关页面，等待 API 响应
        for page_url in AD_PAGES:
            try:
                with_retry(
                    lambda url=page_url: _navigate_and_wait(page, url, timeout),
                    config=retry_cfg,
                    context=f"page_goto:{page_url}",
                )
            except NonRetryableError:
                # 不可重试的异常（Cookie 失效、浏览器崩溃等）→ 立即终止全部采集
                raise
            except Exception as exc:
                result["errors"].append(f"页面 {page_url} 访问异常 (重试耗尽): {exc}")

        page.close()
        context.close()

        result["ad_data"] = interceptor.result.ad_data
        result["price_data"] = interceptor.result.price_data
        result["ad_count"] = len(interceptor.result.ad_data)
        result["price_count"] = len(interceptor.result.price_data)
        result["total_responses"] = interceptor.result.total_responses
        result["ad_api_responses"] = interceptor.result.ad_api_responses
        result["success"] = True

        # ── 结构变更检测 ──────────────────────────
        change_report = interceptor.detect_structure_change()
        result["structure_change"] = change_report
        if change_report["detected"]:
            logger.warn(
                "structure_change_detected",
                extra={
                    "confidence": change_report["confidence"],
                    "reason": change_report["reason"],
                    "metrics": change_report["metrics"],
                },
            )
            result["errors"].append(
                f"结构变更检测 ({change_report['confidence']:.0%} 置信度): "
                f"{change_report['reason']}"
            )

    except NonRetryableError as exc:
        # 不可重试异常 — 写入错误列表，不覆盖 success 标记
        result["errors"].append(f"不可恢复的采集异常: {exc}")
    except Exception as exc:
        result["errors"].append(f"采集流程异常: {exc}")
    finally:
        if browser_svc is not None:
            browser_svc.close()
        result["duration_seconds"] = round(time.perf_counter() - t0, 2)

    return result


def _navigate_and_wait(page: Any, url: str, timeout: int) -> None:
    """执行单次页面导航 + 等待 + 滚动。作为 with_retry 的目标函数。"""
    page.goto(
        url,
        wait_until="domcontentloaded",
        timeout=min(30_000, timeout * 1000),
    )
    # 等待额外时间让 XHR/Fetch 请求完成
    page.wait_for_timeout(max(2_000, timeout * 50))
    # 滚动页面触发懒加载
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    page.wait_for_timeout(2_000)


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
        return error_response(ErrorCode.COOKIE_MISSING, details={"action": "请先执行首次登录"})

    # ── 检查全局停止 ──────────────────────────────
    if await is_global_stop_active(db):
        return error_response(ErrorCode.GLOBAL_STOP, details={"action": "请检查警报中心并清除全局停止"})

    # ── 在后台线程执行同步浏览器操作 ──────────────
    loop = asyncio.get_event_loop()
    raw = await loop.run_in_executor(
        None, _run_collection_sync, cookies, headless, timeout
    )

    if not raw.get("success"):
        return error_response(
            ErrorCode.NETWORK_ERROR,
            "数据采集失败: " + "; ".join(raw.get("errors", [])),
        )

    # ── 结构变更检测: 高置信度 → 停止本次写入 ──────
    change_report = raw.get("structure_change", {})
    if change_report.get("detected") and change_report.get("confidence", 0) >= 0.8:
        return error_response(
            ErrorCode.PAGE_CHANGED,
            change_report.get("reason", "速卖通 API 结构可能已变更"),
            details={
                "confidence": change_report.get("confidence"),
                "metrics": change_report.get("metrics", {}),
                "action": "请检查速卖通后台是否改版，更新 URL/字段模式后重试",
            },
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
    }
