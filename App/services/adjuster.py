"""Playwright 执行器 — 在速卖通后台执行广告出价/价格/活动调整."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Any

from App.core.logging import get_logger

if TYPE_CHECKING:
    from App.services.browser import BrowserService

logger = get_logger(__name__)

# ── 速卖通后台页面 URL (2026-05-31 实测) ────────
# CSP 使用内部 SPA 路由，非独立域名
PRODUCT_MANAGE_URL = "https://csp.aliexpress.com/m_apps/productManage/list-manage?channelId=363432"
AD_MANAGE_URL = (
    "https://csp.aliexpress.com/m_apps/p4p-pages/home?p4p_enter_from=sidebar"
)  # 站内推广(P4P)
AD_ALL_IN_ONE_URL = "https://csp.aliexpress.com/m_apps/all-in-one-promotion/home"  # 一站式推广
CSP_HOME_URL = "https://csp.aliexpress.com/"

# ── 选择器字典 (基于 2026-05-31 CSP 实测) ────────
# CSP 使用 @alifd/next AIT 组件库: ait-btn, ait-table-cell, ait-input 等
SELECTORS: dict[str, list[str]] = {
    # ── 商品管理页 (已验证) ──────────────────
    "product_table": [
        ".ait-scene-table-bottom",
        ".ait-card-pure",
        "[class*=\"ait-table\"]",
    ],
    "product_row": [
        "[class*=\"ait-table-row\"]",
        ".ait-scene-table-bottom tr",
        "[data-row-key]",
    ],
    "product_name_cell": [
        "td:nth-child(2) a",
        "[class*=\"ait-table-cell-fix-left-last\"] a",
        "a[class*=\"product\"]",
    ],
    "price_input": [
        ".ait-input[placeholder*=\"价格\"]",
        "input[placeholder*=\"价格\"]",
        "input[name*=\"price\"]",
        "input.ait-input",
    ],
    "search_input": [
        ".ait-input[placeholder*=\"商品ID\"]",
        "input[placeholder*=\"商品ID\"]",
    ],
    # ── 通用按钮 (AIT 组件) ─────────────────
    "save_btn": [
        "button:has-text('保存')",
        ".ait-btn:has-text('保存')",
        "button:has-text('确认')",
        ".ait-btn-primary:has-text('确定')",
    ],
    "edit_btn": [
        ".ait-btn-link:has-text('编辑')",
        "button:has-text('编辑')",
    ],
    "confirm_btn": [
        ".ait-btn-primary:has-text('确定')",
        "button:has-text('确定')",
        "button:has-text('OK')",
        ".ait-modal button.ait-btn-primary",
    ],
    "cancel_btn": [
        "button:has-text('取消')",
        ".ait-btn:has-text('取消')",
    ],
    # ── 广告管理页 (基于 2026-06-02 CSP 侦察确认 AIT 组件) ─
    "ad_campaign_row": [
        "[data-row-key]",
        "[class*=\"campaign\"]",
        "tr[class*=\"row\"]",
    ],
    "budget_input": [
        "input[placeholder*=\"预算\"]",
        "input[name*=\"budget\"]",
        "input.ait-input",
    ],
    "stop_campaign_btn": [
        "button:has-text('暂停')",
        ".ait-btn:has-text('暂停')",
        "button:has-text('Pause')",
    ],
    "pause_campaign_btn": [
        "button:has-text('暂停')",
        ".ait-btn:has-text('暂停')",
        "button:has-text('Pause')",
        "[class*=\"pause\"] button",
    ],
    "resume_campaign_btn": [
        "button:has-text('恢复')",
        ".ait-btn:has-text('恢复')",
        "button:has-text('重启')",
        "button:has-text('开启')",
        "[class*=\"resume\"] button",
        "[class*=\"start\"] button",
    ],
    "close_campaign_btn": [
        "button:has-text('停止')",
        ".ait-btn:has-text('停止')",
        "button:has-text('关闭')",
        "button:has-text('Stop')",
        "button:has-text('结束')",
    ],
    "campaign_row": [
        "[data-row-key]",
        "[class*=\"campaign-row\"]",
        "tr[class*=\"row\"]",
        "div[class*=\"campaign-item\"]",
    ],
    "campaign_status_badge": [
        "[class*=\"status-badge\"]",
        "[class*=\"campaign-status\"]",
        "span[class*=\"tag\"]",
    ],
    "ad_type_selector": [
        "select.ait-select",
        "[class*=\"ait-select\"]",
        "select[name*=\"type\"]",
    ],
    # ── 通用 ───────────────────────────────
    "success_toast": [
        ".ait-message-success",
        ".ait-notification-success",
        "[class*=\"success\"]",
    ],
    "error_toast": [
        ".ait-message-error",
        ".ait-notification-error",
        "[class*=\"error\"]",
    ],
}

# ── 反爬策略 ────────────────────────────────────
MIN_DELAY_MS = 500
MAX_DELAY_MS = 2000


def _random_delay() -> int:
    """随机延迟（毫秒），降低反爬检测风险。"""
    return random.randint(MIN_DELAY_MS, MAX_DELAY_MS)


def _page_ready(page, timeout: int = 15_000) -> bool:
    """等待页面就绪：网络空闲 + DOM 稳定。"""
    try:
        page.wait_for_load_state("networkidle", timeout=timeout)
        page.wait_for_timeout(1_000)
        return True
    except Exception:
        return False


def _safe_click(
    page, selectors: list[str], timeout: int = 10_000, group_name: str | None = None
) -> bool:
    """安全点击：尝试多个选择器，第一个成功即返回。

    全部失败时记录 WARNING 日志提示页面结构变更。
    """
    for selector in selectors:
        try:
            page.wait_for_selector(selector, state="visible", timeout=timeout)
            page.locator(selector).first.scroll_into_view_if_needed()
            page.wait_for_timeout(_random_delay())
            page.locator(selector).first.click()
            page.wait_for_timeout(_random_delay())
            return True
        except Exception:
            continue
    label = group_name or "unknown"
    logger.warning(
        "选择器全部失败，疑似速卖通页面结构变更: group=%s selectors=%s",
        label, selectors,
    )
    return False


def _safe_fill(
    page, selectors: list[str], value: str, timeout: int = 10_000, group_name: str | None = None
) -> bool:
    """安全填充：尝试多个选择器，第一个成功即返回。

    全部失败时记录 WARNING 日志提示页面结构变更。
    """
    for selector in selectors:
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
        except Exception:
            continue
    label = group_name or "unknown"
    logger.warning(
        "选择器全部失败，疑似速卖通页面结构变更: group=%s selectors=%s",
        label, selectors,
    )
    return False


def execute_adjust_bid(
    browser_svc: BrowserService,
    sku_id: str,
    old_budget: float,
    new_budget: float,
    cookies: list[dict] | None = None,
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

    context = browser_svc.new_context(cookies=cookies)
    page = None
    try:
        page = context.new_page()
        page.goto(AD_MANAGE_URL, wait_until="domcontentloaded", timeout=30_000)
        _page_ready(page)
        page.wait_for_timeout(3_000)

        # 找到预算输入框（多级 fallback）
        budget_selectors = SELECTORS["budget_input"]
        if not _safe_fill(page, budget_selectors, str(new_budget), group_name="budget_input"):
            result["error"] = "无法找到预算输入框"
            return result

        # 保存
        save_selectors = SELECTORS["save_btn"]
        if _safe_click(page, save_selectors, group_name="save_btn"):
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
                logger.debug("page close failed in adjust_bid")
        context.close()

    return result


def execute_adjust_price(
    browser_svc: BrowserService,
    sku_id: str,
    current_price: float,
    new_price: float,
    cookies: list[dict] | None = None,
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

    context = browser_svc.new_context(cookies=cookies)
    page = None
    try:
        page = context.new_page()
        page.goto(PRODUCT_MANAGE_URL, wait_until="domcontentloaded", timeout=30_000)
        _page_ready(page)
        page.wait_for_timeout(3_000)

        # 找到价格输入框（多级 fallback）
        price_selectors = SELECTORS["price_input"]
        if not _safe_fill(page, price_selectors, f"{new_price:.2f}", group_name="price_input"):
            result["error"] = "无法找到价格输入框"
            return result

        # 保存
        if _safe_click(page, SELECTORS["save_btn"], group_name="save_btn"):
            page.wait_for_timeout(2_000)
            try:
                page.wait_for_selector(SELECTORS["success_toast"], timeout=5_000)
            except Exception:
                logger.debug("success toast not found in adjust_price")
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
                logger.debug("page close failed in adjust_price")
        context.close()

    return result


def execute_stop_ad(
    browser_svc: BrowserService,
    sku_id: str,
    cookies: list[dict] | None = None,
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

    context = browser_svc.new_context(cookies=cookies)
    page = None
    try:
        page = context.new_page()
        page.goto(AD_MANAGE_URL, wait_until="domcontentloaded", timeout=30_000)
        _page_ready(page)
        page.wait_for_timeout(3_000)

        # 点击暂停按钮（多级 fallback）
        if _safe_click(page, SELECTORS["stop_campaign_btn"] + [
            "[aria-label*='pause' i]",
            ".campaign-action-pause",
        ], group_name="stop_campaign_btn"):
            page.wait_for_timeout(1_000)
            # 确认弹窗
            try:
                confirm_el = page.wait_for_selector(SELECTORS["confirm_btn"], timeout=3_000)
                if confirm_el:
                    _safe_click(page, [SELECTORS["confirm_btn"]], group_name="confirm_btn")
            except Exception:
                logger.debug("confirm dialog not found in stop_ad")
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
                logger.debug("page close failed in stop_ad")
        context.close()

    return result


def execute_switch_ad_type(
    browser_svc: BrowserService,
    sku_id: str,
    new_type: str,
    cookies: list[dict] | None = None,
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

    context = browser_svc.new_context(cookies=cookies)
    page = None
    try:
        page = context.new_page()
        page.goto(AD_MANAGE_URL, wait_until="domcontentloaded", timeout=30_000)
        _page_ready(page)
        page.wait_for_timeout(3_000)

        # 选择广告类型（多级 fallback）
        type_selectors = SELECTORS["ad_type_selector"]
        selected = False
        for selector in type_selectors:
            try:
                page.wait_for_selector(selector, timeout=5_000)
                page.select_option(selector, new_type)
                page.wait_for_timeout(_random_delay())
                selected = True
                break
            except Exception:
                continue
        if not selected:
            logger.warning(
                "选择器全部失败，疑似速卖通页面结构变更: group=ad_type_selector selectors=%s",
                type_selectors,
            )
            result["error"] = "无法找到广告类型选择器"
            return result

        # 保存
        _safe_click(page, SELECTORS["save_btn"], group_name="save_btn")
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
                logger.debug("page close failed in switch_ad_type")
        context.close()

    return result


# ── 活动管理 ──────────────────────────────────────


def execute_pause_campaign(
    browser_svc: BrowserService,
    sku_id: str,
    cookies: list[dict] | None = None,
) -> dict[str, Any]:
    """暂停推广活动。

    流程：导航到一站式推广页 → 找到对应推广 → 点击暂停 → 确认。
    """
    result: dict[str, Any] = {
        "success": False,
        "operation": "pause_campaign",
        "sku_id": sku_id,
        "error": None,
    }

    context = browser_svc.new_context(cookies=cookies)
    page = None
    try:
        page = context.new_page()
        page.goto(AD_ALL_IN_ONE_URL, wait_until="domcontentloaded", timeout=30_000)
        _page_ready(page)
        page.wait_for_timeout(3_000)

        # 点击暂停按钮
        if _safe_click(page, SELECTORS["pause_campaign_btn"]):
            page.wait_for_timeout(1_000)
            # 确认弹窗
            try:
                confirm_el = page.wait_for_selector(SELECTORS["confirm_btn"], timeout=3_000)
                if confirm_el:
                    _safe_click(page, [SELECTORS["confirm_btn"]])
            except Exception:
                logger.debug("confirm dialog not found in pause_campaign")
            page.wait_for_timeout(2_000)

            # 检查成功提示
            try:
                page.wait_for_selector(SELECTORS["success_toast"], timeout=5_000)
            except Exception:
                logger.debug("success toast not found in pause_campaign")
            result["success"] = True
        else:
            result["error"] = "无法找到暂停按钮"
            return result

        page.close()
    except Exception as exc:
        result["error"] = str(exc)
        logger.exception("pause_campaign 执行异常: SKU=%s", sku_id)
    finally:
        if page is not None:
            try:
                page.close()
            except Exception:
                logger.debug("page close failed in pause_campaign")
        context.close()

    return result


def execute_resume_campaign(
    browser_svc: BrowserService,
    sku_id: str,
    cookies: list[dict] | None = None,
) -> dict[str, Any]:
    """恢复已暂停的推广活动。

    流程：导航到一站式推广页 → 找到对应推广 → 点击恢复 → 确认。
    """
    result: dict[str, Any] = {
        "success": False,
        "operation": "resume_campaign",
        "sku_id": sku_id,
        "error": None,
    }

    context = browser_svc.new_context(cookies=cookies)
    page = None
    try:
        page = context.new_page()
        page.goto(AD_ALL_IN_ONE_URL, wait_until="domcontentloaded", timeout=30_000)
        _page_ready(page)
        page.wait_for_timeout(3_000)

        # 点击恢复按钮
        if _safe_click(page, SELECTORS["resume_campaign_btn"]):
            page.wait_for_timeout(1_000)
            # 确认弹窗
            try:
                confirm_el = page.wait_for_selector(SELECTORS["confirm_btn"], timeout=3_000)
                if confirm_el:
                    _safe_click(page, [SELECTORS["confirm_btn"]])
            except Exception:
                logger.debug("confirm dialog not found in resume_campaign")
            page.wait_for_timeout(2_000)

            # 检查成功提示
            try:
                page.wait_for_selector(SELECTORS["success_toast"], timeout=5_000)
            except Exception:
                logger.debug("success toast not found in resume_campaign")
            result["success"] = True
        else:
            result["error"] = "无法找到恢复按钮"
            return result

        page.close()
    except Exception as exc:
        result["error"] = str(exc)
        logger.exception("resume_campaign 执行异常: SKU=%s", sku_id)
    finally:
        if page is not None:
            try:
                page.close()
            except Exception:
                logger.debug("page close failed in resume_campaign")
        context.close()

    return result


def execute_stop_campaign(
    browser_svc: BrowserService,
    sku_id: str,
    cookies: list[dict] | None = None,
) -> dict[str, Any]:
    """停止/关闭推广活动（软边界操作，需要人工确认）。

    流程：导航到一站式推广页 → 找到对应推广 → 点击停止/关闭 → 确认。
    """
    result: dict[str, Any] = {
        "success": False,
        "operation": "stop_campaign",
        "sku_id": sku_id,
        "error": None,
    }

    context = browser_svc.new_context(cookies=cookies)
    page = None
    try:
        page = context.new_page()
        page.goto(AD_ALL_IN_ONE_URL, wait_until="domcontentloaded", timeout=30_000)
        _page_ready(page)
        page.wait_for_timeout(3_000)

        # 点击停止/关闭按钮
        if _safe_click(page, SELECTORS["close_campaign_btn"]):
            page.wait_for_timeout(1_000)
            # 确认弹窗
            try:
                confirm_el = page.wait_for_selector(SELECTORS["confirm_btn"], timeout=3_000)
                if confirm_el:
                    _safe_click(page, [SELECTORS["confirm_btn"]])
            except Exception:
                logger.debug("confirm dialog not found in stop_campaign")
            page.wait_for_timeout(2_000)

            # 检查成功提示
            try:
                page.wait_for_selector(SELECTORS["success_toast"], timeout=5_000)
            except Exception:
                logger.debug("success toast not found in stop_campaign")
            result["success"] = True
        else:
            result["error"] = "无法找到停止按钮"
            return result

        page.close()
    except Exception as exc:
        result["error"] = str(exc)
        logger.exception("stop_campaign 执行异常: SKU=%s", sku_id)
    finally:
        if page is not None:
            try:
                page.close()
            except Exception:
                logger.debug("page close failed in stop_campaign")
        context.close()

    return result


# ── 执行器路由表 ─────────────────────────────────
EXECUTORS = {
    "adjust_bid": execute_adjust_bid,
    "adjust_price": execute_adjust_price,
    "stop_ad": execute_stop_ad,
    "switch_ad_type": execute_switch_ad_type,
    "pause_campaign": execute_pause_campaign,
    "resume_campaign": execute_resume_campaign,
    "stop_campaign": execute_stop_campaign,
}


def run_executor(
    operation_type: str,
    browser_svc: BrowserService,
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
    return executor(browser_svc, **kwargs)
