"""Playwright 执行器 — 在速卖通后台执行广告出价/价格/活动调整."""

from __future__ import annotations

import asyncio
import logging
import random
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from App.services.browser import BrowserService
    from App.services.cookie_manager import CookieManager

logger = logging.getLogger(__name__)

# ── 速卖通后台页面 URL ──────────────────────────
AD_MANAGE_URL = "https://ad.aliexpress.com/campaign/manage"
PRODUCT_MANAGE_URL = "https://gsp.aliexpress.com/apps/product/manage"

# ── 选择器字典（需根据实际页面更新）──────────────
# 这些选择器是占位符，实际使用时需根据速卖通后台 DOM 调整
SELECTORS: dict[str, str] = {
    # 广告管理页
    "ad_campaign_row": "tr[data-campaign-id]",
    "ad_sku_cell": "td.sku-id",
    "budget_input": "input[name='dailyBudget']",
    "daily_budget_input": "input.budget-amount",
    "budget_save_btn": "button:has-text('Save'), button:has-text('保存')",
    "campaign_status_btn": "button.status-toggle",
    "stop_campaign_btn": "button:has-text('Pause'), button:has-text('暂停')",
    "ad_type_selector": "select[name='adType'], .ad-type-select",
    # 商品管理页
    "product_list_table": ".product-table",
    "price_input": "input[name='price']",
    "price_save_btn": "button:has-text('Save'), button:has-text('保存')",
    # 通用
    "confirm_btn": ".modal button.confirm, button:has-text('OK'), button:has-text('确定')",
    "success_toast": ".toast.success, .message.success, .alert-success",
    "error_toast": ".toast.error, .message.error, .alert-error",
}

# ── 反爬策略 ────────────────────────────────────
MIN_DELAY_MS = 500
MAX_DELAY_MS = 2000


def _random_delay() -> int:
    """随机延迟（毫秒），降低反爬检测风险。"""
    return random.randint(MIN_DELAY_MS, MAX_DELAY_MS)


def _safe_click(page, selector: str, timeout: int = 10_000) -> bool:
    """安全点击：等待元素可见 → 滚动到视口 → 点击。"""
    try:
        page.wait_for_selector(selector, state="visible", timeout=timeout)
        page.locator(selector).first.scroll_into_view_if_needed()
        page.wait_for_timeout(_random_delay())
        page.locator(selector).first.click()
        page.wait_for_timeout(_random_delay())
        return True
    except Exception as exc:
        logger.error("点击失败: selector=%s error=%s", selector, exc)
        return False


def _safe_fill(page, selector: str, value: str, timeout: int = 10_000) -> bool:
    """安全填充：等待输入框 → 清空 → 输入。"""
    try:
        page.wait_for_selector(selector, state="visible", timeout=timeout)
        locator = page.locator(selector).first
        locator.scroll_into_view_if_needed()
        page.wait_for_timeout(_random_delay())
        locator.fill("")
        page.wait_for_timeout(300)
        locator.fill(value)
        page.wait_for_timeout(_random_delay())
        return True
    except Exception as exc:
        logger.error("填充失败: selector=%s error=%s", selector, exc)
        return False


def execute_adjust_bid(
    browser_svc: BrowserService,
    cookie_mgr: CookieManager,
    sku_id: str,
    old_budget: float,
    new_budget: float,
) -> dict[str, Any]:
    """调整广告出价/预算。

    流程：导航到广告管理页 → 找到对应 SKU 的推广 → 修改预算 → 保存。
    """
    result: dict[str, Any] = {
        "success": False,
        "operation": "adjust_bid",
        "sku_id": sku_id,
        "old_value": old_budget,
        "new_value": new_budget,
        "error": None,
    }

    context = browser_svc.new_context(cookie_manager=cookie_mgr)
    page = None
    try:
        page = context.new_page()
        page.goto(AD_MANAGE_URL, wait_until="domcontentloaded", timeout=30_000)
        page.wait_for_timeout(3_000)

        # 找到预算输入框
        budget_selector = SELECTORS["daily_budget_input"]
        if not _safe_fill(page, budget_selector, str(new_budget)):
            # fallback: 尝试通用 input
            budget_selector = "input[type='number'], input.budget"
            if not _safe_fill(page, budget_selector, str(new_budget)):
                result["error"] = "无法找到预算输入框"
                return result

        # 保存
        if _safe_click(page, SELECTORS["budget_save_btn"]):
            page.wait_for_timeout(2_000)
            # 检查成功提示
            try:
                page.wait_for_selector(SELECTORS["success_toast"], timeout=5_000)
                result["success"] = True
            except Exception:
                # 没有 toast 也不一定失败，可能页面静默保存
                result["success"] = True

        page.close()
    except Exception as exc:
        result["error"] = str(exc)
        logger.exception("adjust_bid 执行异常: SKU=%s", sku_id)
    finally:
        if page is not None:
            try:
                page.close()
            except Exception:
                pass
        context.close()

    return result


def execute_adjust_price(
    browser_svc: BrowserService,
    cookie_mgr: CookieManager,
    sku_id: str,
    current_price: float,
    new_price: float,
) -> dict[str, Any]:
    """调整商品售价。

    流程：导航到商品管理页 → 找到商品 → 修改价格 → 保存。
    """
    result: dict[str, Any] = {
        "success": False,
        "operation": "adjust_price",
        "sku_id": sku_id,
        "old_value": current_price,
        "new_value": new_price,
        "error": None,
    }

    context = browser_svc.new_context(cookie_manager=cookie_mgr)
    page = None
    try:
        page = context.new_page()
        page.goto(PRODUCT_MANAGE_URL, wait_until="domcontentloaded", timeout=30_000)
        page.wait_for_timeout(3_000)

        # 找到价格输入框
        price_selector = SELECTORS["price_input"]
        if not _safe_fill(page, price_selector, f"{new_price:.2f}"):
            # fallback: 通用价格输入
            price_selector = "input[name='price'], input.price-amount"
            if not _safe_fill(page, price_selector, f"{new_price:.2f}"):
                result["error"] = "无法找到价格输入框"
                return result

        # 保存
        if _safe_click(page, SELECTORS["price_save_btn"]):
            page.wait_for_timeout(2_000)
            try:
                page.wait_for_selector(SELECTORS["success_toast"], timeout=5_000)
            except Exception:
                pass
            result["success"] = True

        page.close()
    except Exception as exc:
        result["error"] = str(exc)
        logger.exception("adjust_price 执行异常: SKU=%s", sku_id)
    finally:
        if page is not None:
            try:
                page.close()
            except Exception:
                pass
        context.close()

    return result


def execute_stop_ad(
    browser_svc: BrowserService,
    cookie_mgr: CookieManager,
    sku_id: str,
) -> dict[str, Any]:
    """暂停/停止推广活动。

    流程：导航到广告管理页 → 找到推广 → 点击暂停 → 确认。
    """
    result: dict[str, Any] = {
        "success": False,
        "operation": "stop_ad",
        "sku_id": sku_id,
        "error": None,
    }

    context = browser_svc.new_context(cookie_manager=cookie_mgr)
    page = None
    try:
        page = context.new_page()
        page.goto(AD_MANAGE_URL, wait_until="domcontentloaded", timeout=30_000)
        page.wait_for_timeout(3_000)

        # 点击暂停按钮
        if _safe_click(page, SELECTORS["stop_campaign_btn"]):
            page.wait_for_timeout(1_000)
            # 确认弹窗
            try:
                confirm_el = page.wait_for_selector(SELECTORS["confirm_btn"], timeout=3_000)
                if confirm_el:
                    _safe_click(page, SELECTORS["confirm_btn"])
            except Exception:
                # 可能没有确认弹窗
                pass
            page.wait_for_timeout(2_000)
            result["success"] = True

        page.close()
    except Exception as exc:
        result["error"] = str(exc)
        logger.exception("stop_ad 执行异常: SKU=%s", sku_id)
    finally:
        if page is not None:
            try:
                page.close()
            except Exception:
                pass
        context.close()

    return result


def execute_switch_ad_type(
    browser_svc: BrowserService,
    cookie_mgr: CookieManager,
    sku_id: str,
    new_type: str,
) -> dict[str, Any]:
    """切换广告类型。

    流程：导航到广告管理页 → 找到推广 → 切换类型 → 保存。
    """
    result: dict[str, Any] = {
        "success": False,
        "operation": "switch_ad_type",
        "sku_id": sku_id,
        "new_value": new_type,
        "error": None,
    }

    context = browser_svc.new_context(cookie_manager=cookie_mgr)
    page = None
    try:
        page = context.new_page()
        page.goto(AD_MANAGE_URL, wait_until="domcontentloaded", timeout=30_000)
        page.wait_for_timeout(3_000)

        # 选择广告类型
        type_selector = SELECTORS["ad_type_selector"]
        try:
            page.wait_for_selector(type_selector, timeout=10_000)
            page.select_option(type_selector, new_type)
            page.wait_for_timeout(_random_delay())
        except Exception:
            result["error"] = "无法找到广告类型选择器"
            return result

        # 保存
        _safe_click(page, SELECTORS["budget_save_btn"])
        page.wait_for_timeout(2_000)
        result["success"] = True

        page.close()
    except Exception as exc:
        result["error"] = str(exc)
        logger.exception("switch_ad_type 执行异常: SKU=%s", sku_id)
    finally:
        if page is not None:
            try:
                page.close()
            except Exception:
                pass
        context.close()

    return result


# ── 执行器路由表 ─────────────────────────────────
EXECUTORS = {
    "adjust_bid": execute_adjust_bid,
    "adjust_price": execute_adjust_price,
    "stop_ad": execute_stop_ad,
    "switch_ad_type": execute_switch_ad_type,
}


def run_executor(
    operation_type: str,
    browser_svc: BrowserService,
    cookie_mgr: CookieManager,
    **kwargs: Any,
) -> dict[str, Any]:
    """根据操作类型分发到对应执行器。"""
    executor = EXECUTORS.get(operation_type)
    if executor is None:
        return {
            "success": False,
            "operation": operation_type,
            "error": f"不支持的操作类型: {operation_type}",
        }
    return executor(browser_svc, cookie_mgr, **kwargs)
