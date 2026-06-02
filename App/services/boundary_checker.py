"""边界条件检查器 — 验证 AI 决策是否触发硬/软边界."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from App.core.logging import get_logger
from App.models.alert import Alert
from App.models.base import ProfitAnalysis
from App.models.cookie import CookieStore
from App.models.operation_log import OperationLog
from App.models.system_state import SystemState, is_global_stop_active
from App.services.alert_service import raise_alert

logger = get_logger(__name__)

# ── 默认参数（可通过系统设置覆盖）─────────────────────
_DEFAULT_ROI_NEGATIVE_DAYS = 7        # ROI 连续为负天数阈值
_DEFAULT_MAX_PRICE_CHANGE_PCT = 0.05  # 调价幅度上限
_DEFAULT_MAX_DAILY_SPEND_MULT = 1.5   # 日花费 = 盈亏平衡 × 倍数
_DEFAULT_PRICE_COOLDOWN_HOURS = 24    # 调价冷却时间
_DEFAULT_COLLECTION_ERROR_WINDOW_HOURS = 2  # 采集异常检查时间窗口


@dataclass
class BoundaryResult:
    """边界检查结果。"""
    passed: bool
    boundary_type: str | None = None   # "hard" | "soft"
    reason: str = ""
    details: dict[str, Any] = field(default_factory=dict)


async def _get_boundary_config(db: AsyncSession) -> dict[str, Any]:
    """从系统设置读取可配置的边界参数。

    参数存储在 SystemState 表，key="boundary_config"。
    未设置时返回默认值。
    """
    result = await db.execute(
        select(SystemState).where(SystemState.key == "boundary_config")
    )
    record = result.scalar_one_or_none()
    if record is None:
        return {
            "roi_negative_days": _DEFAULT_ROI_NEGATIVE_DAYS,
            "max_price_change_pct": _DEFAULT_MAX_PRICE_CHANGE_PCT,
            "max_daily_spend_mult": _DEFAULT_MAX_DAILY_SPEND_MULT,
            "price_cooldown_hours": _DEFAULT_PRICE_COOLDOWN_HOURS,
            "collection_error_window_hours": _DEFAULT_COLLECTION_ERROR_WINDOW_HOURS,
        }

    cfg = record.value or {}
    return {
        "roi_negative_days": cfg.get("roi_negative_days", _DEFAULT_ROI_NEGATIVE_DAYS),
        "max_price_change_pct": cfg.get("max_price_change_pct", _DEFAULT_MAX_PRICE_CHANGE_PCT),
        "max_daily_spend_mult": cfg.get("max_daily_spend_mult", _DEFAULT_MAX_DAILY_SPEND_MULT),
        "price_cooldown_hours": cfg.get("price_cooldown_hours", _DEFAULT_PRICE_COOLDOWN_HOURS),
        "collection_error_window_hours": cfg.get(
            "collection_error_window_hours", _DEFAULT_COLLECTION_ERROR_WINDOW_HOURS
        ),
    }


async def _check_cookie_health(
    db: AsyncSession,
) -> tuple[bool, str]:
    """检查速卖通 Cookie 是否有效。

    Returns:
        (is_valid, description)
    """
    result = await db.execute(
        select(CookieStore).where(
            CookieStore.domain == "aliexpress.com",
            CookieStore.is_valid,
        )
    )
    valid_cookie = result.scalar_one_or_none()
    if valid_cookie is not None:
        return True, "Cookie 有效"

    # 检查是否根本没有 cookie
    all_result = await db.execute(
        select(CookieStore).where(CookieStore.domain == "aliexpress.com")
    )
    any_cookie = all_result.scalar_one_or_none()
    if any_cookie is None:
        return False, "速卖通 Cookie 不存在，请先执行首次登录"
    return False, "速卖通 Cookie 已失效"


async def _check_roi_negative(
    db: AsyncSession,
    profit: ProfitAnalysis,
    config: dict[str, Any],
) -> tuple[bool, str]:
    """检查 ROI 是否连续多天为负。

    Returns:
        (is_negative_triggered, description)
    """
    roi_trend = profit.roi_7d_trend or []
    if not isinstance(roi_trend, list):
        return False, ""

    threshold = config.get("roi_negative_days", _DEFAULT_ROI_NEGATIVE_DAYS)
    if len(roi_trend) < threshold:
        return False, ""

    all_negative = all(
        (item.get("roi", 0) if isinstance(item, dict) else 0) < 0
        for item in roi_trend
    )
    if all_negative:
        return True, f"ROI 连续 {len(roi_trend)} 天为负（阈值 {threshold} 天）"
    return False, ""


async def _check_collection_errors(
    db: AsyncSession,
    config: dict[str, Any],
) -> tuple[bool, str, list[dict]]:
    """检查最近采集执行日志是否有异常。

    Returns:
        (has_error, description, error_details)
    """
    window_hours = config.get(
        "collection_error_window_hours", _DEFAULT_COLLECTION_ERROR_WINDOW_HOURS
    )
    since = datetime.now(UTC) - timedelta(hours=window_hours)

    result = await db.execute(
        select(OperationLog)
        .where(
            OperationLog.operation_type == "collection",
            OperationLog.status == "failed",
            OperationLog.executed_at >= since,
        )
        .order_by(OperationLog.executed_at.desc())
        .limit(5)
    )
    failed_logs = list(result.scalars().all())

    if not failed_logs:
        return False, "", []

    errors = []
    for log in failed_logs:
        errors.append({
            "sku_id": log.sku_id,
            "executed_at": log.executed_at.isoformat() if log.executed_at else None,
            "details": log.details,
        })

    return (
        True,
        f"最近 {window_hours} 小时内采集失败 {len(failed_logs)} 次",
        errors,
    )


async def _check_collection_recent_failures(
    db: AsyncSession,
    config: dict[str, Any],
) -> tuple[bool, str, list[dict]]:
    """检查最近采集周期是否有异常（从 alerts 表检查 recent collection failures）。

    Returns:
        (has_error, description, error_details)
    """
    window_hours = config.get(
        "collection_error_window_hours", _DEFAULT_COLLECTION_ERROR_WINDOW_HOURS
    )
    since = datetime.now(UTC) - timedelta(hours=window_hours)

    # 检查最近是否有 collection_error / collection_crash / collection_skipped 警报
    result = await db.execute(
        select(Alert)
        .where(
            Alert.alert_type.in_(["collection_error", "collection_crash"]),
            Alert.created_at >= since,
        )
        .order_by(Alert.created_at.desc())
        .limit(5)
    )
    recent_alerts = list(result.scalars().all())

    if not recent_alerts:
        return False, "", []

    errors = []
    for alert in recent_alerts:
        errors.append({
            "alert_type": alert.alert_type,
            "severity": alert.severity,
            "message": alert.message,
            "created_at": alert.created_at.isoformat() if alert.created_at else None,
        })

    return (
        True,
        f"最近 {window_hours} 小时内采集 {len(recent_alerts)} 个错误警报",
        errors,
    )


async def check_hard_boundaries(
    db: AsyncSession,
    sku_id: str | None = None,
    profit: ProfitAnalysis | None = None,
) -> dict[str, Any]:
    """检查三种硬边界并返回结构化结果。

    这是 TASK-003-3 入口函数，供调度/执行层调用。
    与 check_boundaries() 不同，这是一个独立的预检，不依赖 AI 决策。

    Args:
        db: 数据库会话
        sku_id: 可选，指定 SKU 时检查单 SKU 级边界（ROI）
        profit: 可选，利润分析记录

    Returns:
        {
            "passed": bool,
            "boundary_type": str | None,
            "stop_all": bool,       # 是否停止所有操作
            "stop_sku": bool,       # 是否停止该 SKU
            "skip_cycle": bool,     # 是否跳过本次执行周期
            "reason": str,
            "details": dict,
        }
    """
    config = await _get_boundary_config(db)
    triggers: list[str] = []
    details: dict[str, Any] = {
        "boundary_config": config,
    }

    # ── 硬边界 1: Cookie 失效（stop_all）────────────────
    cookie_valid, cookie_reason = await _check_cookie_health(db)
    if not cookie_valid:
        triggers.append(f"cookie_failed: {cookie_reason}")
        details["cookie_status"] = cookie_reason
        logger.error(
            "硬边界触发: Cookie 失效 — %s",
            cookie_reason,
            extra={"boundary_type": "hard", "stop_all": True, "reason": cookie_reason},
        )
        await raise_alert(
            db,
            "cookie_expired",
            f"Cookie 失效，停止所有操作: {cookie_reason}",
            severity="critical",
            set_global_stop=True,
        )
        return {
            "passed": False,
            "boundary_type": "hard",
            "stop_all": True,
            "stop_sku": False,
            "skip_cycle": False,
            "reason": cookie_reason,
            "details": details,
        }

    # ── 硬边界 2: ROI 连续多天为负（stop_sku）────────────
    if profit is not None:
        roi_triggered, roi_reason = await _check_roi_negative(db, profit, config)
        if roi_triggered:
            triggers.append(f"roi_negative: {roi_reason}")
            details["roi_trend"] = profit.roi_7d_trend
            details["sku_id"] = sku_id

            logger.error(
                "硬边界触发: SKU=%s ROI 连续为负 — %s",
                sku_id,
                roi_reason,
                extra={
                    "boundary_type": "hard",
                    "stop_sku": sku_id,
                    "roi_trend": profit.roi_7d_trend,
                    "reason": roi_reason,
                },
            )
            await raise_alert(
                db,
                "roi_negative",
                f"[{sku_id}] {roi_reason}，已停止该 SKU 广告",
                severity="warning",
            )
            return {
                "passed": False,
                "boundary_type": "hard",
                "stop_all": False,
                "stop_sku": True,
                "skip_cycle": False,
                "reason": roi_reason,
                "details": details,
            }

    # ── 硬边界 3: 采集异常（skip_cycle）──────────────────
    op_has_error, op_reason, op_errors = await _check_collection_errors(db, config)
    alert_has_error, alert_reason, alert_errors = \
        await _check_collection_recent_failures(db, config)

    if op_has_error or alert_has_error:
        full_reason = []
        if op_has_error:
            full_reason.append(op_reason)
            details["collection_operation_errors"] = op_errors
        if alert_has_error:
            full_reason.append(alert_reason)
            details["collection_alert_errors"] = alert_errors

        desc = "; ".join(full_reason)
        triggers.append(f"collection_error: {desc}")

        logger.warning(
            "硬边界触发: 采集异常 — %s",
            desc,
            extra={
                "boundary_type": "hard",
                "skip_cycle": True,
                "collection_errors": details.get("collection_operation_errors", []),
                "collection_alerts": details.get("collection_alert_errors", []),
                "reason": desc,
            },
        )
        await raise_alert(
            db,
            "collection_error",
            f"采集异常，跳过本次执行周期: {desc}",
            severity="warning",
        )
        return {
            "passed": False,
            "boundary_type": "hard",
            "stop_all": False,
            "stop_sku": False,
            "skip_cycle": True,
            "reason": desc,
            "details": details,
        }

    # ── 全部通过 ────────────────────────────────────
    logger.info(
        "硬边界检查通过: sku=%s",
        sku_id or "ALL",
        extra={"boundary_type": "hard", "passed": True},
    )
    return {
        "passed": True,
        "boundary_type": None,
        "stop_all": False,
        "stop_sku": False,
        "skip_cycle": False,
        "reason": "",
        "details": details,
    }


async def check_boundaries(
    db: AsyncSession,
    sku_id: str,
    decision: dict[str, Any],
    profit: ProfitAnalysis,
) -> BoundaryResult:
    """检查 AI 决策是否触发边界条件。

    Args:
        db: 数据库会话
        sku_id: 商品 SKU ID
        decision: AI 生成的决策 dict
        profit: 当前利润分析记录

    Returns:
        BoundaryResult — passed=True 表示可以通过
    """
    reasons: list[str] = []
    details: dict[str, Any] = {}
    config = await _get_boundary_config(db)

    # ── 硬边界 1: ROI 连续 7 天为负 ───────────────
    roi_trend = profit.roi_7d_trend or []
    threshold = config.get("roi_negative_days", _DEFAULT_ROI_NEGATIVE_DAYS)
    if isinstance(roi_trend, list) and len(roi_trend) >= threshold:
        all_negative = all(
            (item.get("roi", 0) if isinstance(item, dict) else 0) < 0
            for item in roi_trend
        )
        if all_negative:
            reasons.append(f"ROI 连续 {len(roi_trend)} 天为负（阈值 {threshold} 天）")
            details["roi_trend"] = roi_trend
            logger.warning(
                "硬边界拦截: SKU=%s roi连续为负",
                sku_id,
                extra={"sku_id": sku_id, "boundary_type": "hard", "roi_trend": roi_trend},
            )
            return BoundaryResult(
                passed=False,
                boundary_type="hard",
                reason="; ".join(reasons),
                details=details,
            )

    # ── 硬边界 2: Cookie 已失效 ───────────────────
    cookie_valid, cookie_reason = await _check_cookie_health(db)
    if not cookie_valid:
        reasons.append(cookie_reason)
        details["cookie_status"] = cookie_reason
        logger.warning(
            "硬边界拦截: SKU=%s %s",
            sku_id,
            cookie_reason,
            extra={"sku_id": sku_id, "boundary_type": "hard", "cookie_status": cookie_reason},
        )
        return BoundaryResult(
            passed=False,
            boundary_type="hard",
            reason="; ".join(reasons),
            details=details,
        )

    # ── 硬边界 3: 全局停止标志 ────────────────────
    if await is_global_stop_active(db):
        reasons.append("全局停止已启用")
        logger.warning(
            "硬边界拦截: SKU=%s 全局停止已启用",
            sku_id,
            extra={"sku_id": sku_id, "boundary_type": "hard", "global_stop": True},
        )
        return BoundaryResult(
            passed=False,
            boundary_type="hard",
            reason="; ".join(reasons),
            details={"global_stop": True},
        )

    # ── 软边界 1: 关闭推广活动需要人工确认 ─────────
    decision_type = decision.get("decision_type", "")
    if decision_type == "stop_ad":
        reasons.append("决定关闭推广活动，需要人工确认")
        logger.info(
            "软边界拦截: SKU=%s stop_ad 待确认",
            sku_id,
            extra={"sku_id": sku_id, "boundary_type": "soft"},
        )
        return BoundaryResult(
            passed=False,
            boundary_type="soft",
            reason="; ".join(reasons),
            details={"decision_type": "stop_ad"},
        )

    # ── 软边界 2: requires_confirmation ──────────
    if decision_type == "requires_confirmation":
        reasons.append("AI 建议需要人工确认的重大操作")
        logger.info(
            "软边界拦截: SKU=%s requires_confirmation 待确认",
            sku_id,
            extra={"sku_id": sku_id, "boundary_type": "soft"},
        )
        return BoundaryResult(
            passed=False,
            boundary_type="soft",
            reason="; ".join(reasons),
            details={"decision": decision},
        )

    # ── 硬边界 4: 日广告花费超限 ───────────────────
    action = decision.get("action") or {}
    breakeven = float(profit.breakeven_ad_spend)
    max_spend_mult = config.get("max_daily_spend_mult", _DEFAULT_MAX_DAILY_SPEND_MULT)
    max_daily_spend = breakeven * max_spend_mult

    if decision_type == "adjust_bid" and action.get("field") == "daily_budget":
        new_value = action.get("new_value", 0)
        if isinstance(new_value, (int, float)) and new_value > max_daily_spend > 0:
            reasons.append(
                f"新预算 ${new_value:.2f} 超出上限 ${max_daily_spend:.2f} "
                f"(盈亏平衡 ${breakeven:.2f} × {max_spend_mult:.0%})"
            )
            details["new_budget"] = new_value
            details["max_allowed"] = max_daily_spend
            logger.warning(
                "硬边界拦截: SKU=%s 预算超限 %.2f > %.2f",
                sku_id,
                new_value,
                max_daily_spend,
                extra={
                    "sku_id": sku_id,
                    "boundary_type": "hard",
                    "new_budget": new_value,
                    "max_allowed": max_daily_spend,
                },
            )
            return BoundaryResult(
                passed=False,
                boundary_type="hard",
                reason="; ".join(reasons),
                details=details,
            )

    # ── 硬边界 5: 调价幅度超过上限 ──────────────────
    max_change = config.get("max_price_change_pct", _DEFAULT_MAX_PRICE_CHANGE_PCT)
    if decision_type == "adjust_price" and action.get("field") == "price":
        change_pct = abs(action.get("change_pct", 0))
        if isinstance(change_pct, (int, float)) and change_pct > max_change:
            reasons.append(
                f"调价幅度 {change_pct:.1%} 超出上限 {max_change:.0%}"
            )
            details["change_pct"] = change_pct
            logger.warning(
                "硬边界拦截: SKU=%s 调价幅度超限 %.1f%% > %.0f%%",
                sku_id,
                change_pct * 100,
                max_change * 100,
                extra={"sku_id": sku_id, "boundary_type": "hard", "change_pct": change_pct},
            )
            return BoundaryResult(
                passed=False,
                boundary_type="hard",
                reason="; ".join(reasons),
                details=details,
            )

    # ── 全部通过 ──────────────────────────────────
    if not reasons:
        logger.info(
            "边界检查通过: SKU=%s decision=%s",
            sku_id,
            decision_type,
            extra={
                "sku_id": sku_id,
                "boundary_type": None,
                "decision_type": decision_type,
                "passed": True,
            },
        )
        return BoundaryResult(passed=True)

    logger.warning(
        "边界检查未通过: SKU=%s reason=%s",
        sku_id,
        "; ".join(reasons),
        extra={"sku_id": sku_id, "reasons": reasons},
    )
    return BoundaryResult(passed=False, reason="; ".join(reasons), details=details)
