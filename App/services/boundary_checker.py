"""边界条件检查器 — 验证 AI 决策是否触发硬/软边界."""

from __future__ import annotations

from dataclasses import dataclass, field

from App.core.logging import get_logger
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from App.models.base import ProfitAnalysis
from App.models.cookie import CookieStore
from App.models.system_state import is_global_stop_active

logger = get_logger(__name__)


@dataclass
class BoundaryResult:
    """边界检查结果。"""
    passed: bool
    boundary_type: str | None = None   # "hard" | "soft"
    reason: str = ""
    details: dict[str, Any] = field(default_factory=dict)


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

    # ── 硬边界 1: ROI 连续 7 天为负 ───────────────
    roi_trend = profit.roi_7d_trend or []
    if isinstance(roi_trend, list) and len(roi_trend) >= 7:
        all_negative = all(
            (item.get("roi", 0) if isinstance(item, dict) else 0) < 0
            for item in roi_trend
        )
        if all_negative:
            reasons.append(f"ROI 连续 {len(roi_trend)} 天为负")
            details["roi_trend"] = roi_trend
            return BoundaryResult(
                passed=False,
                boundary_type="hard",
                reason="; ".join(reasons),
                details=details,
            )

    # ── 硬边界 2: Cookie 已失效 ───────────────────
    cookie_result = await db.execute(
        select(CookieStore).where(
            CookieStore.domain == "aliexpress.com",
            CookieStore.is_valid == True,
        )
    )
    valid_cookie = cookie_result.scalar_one_or_none()
    if valid_cookie is None:
        # 检查是否根本没有 cookie
        all_result = await db.execute(
            select(CookieStore).where(CookieStore.domain == "aliexpress.com")
        )
        any_cookie = all_result.scalar_one_or_none()
        if any_cookie is None:
            reasons.append("速卖通 Cookie 不存在，请先执行首次登录")
            return BoundaryResult(
                passed=False,
                boundary_type="hard",
                reason="; ".join(reasons),
                details={"cookie_status": "missing"},
            )
        else:
            reasons.append("速卖通 Cookie 已失效")
            return BoundaryResult(
                passed=False,
                boundary_type="hard",
                reason="; ".join(reasons),
                details={"cookie_status": "invalid"},
            )

    # ── 硬边界 3: 全局停止标志 ────────────────────
    if await is_global_stop_active(db):
        reasons.append("全局停止已启用")
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
        return BoundaryResult(
            passed=False,
            boundary_type="soft",
            reason="; ".join(reasons),
            details={"decision_type": "stop_ad"},
        )

    # ── 软边界 2: requires_confirmation ──────────
    if decision_type == "requires_confirmation":
        reasons.append("AI 建议需要人工确认的重大操作")
        return BoundaryResult(
            passed=False,
            boundary_type="soft",
            reason="; ".join(reasons),
            details={"decision": decision},
        )

    # ── 硬边界 4: 日广告花费超限 ───────────────────
    action = decision.get("action") or {}
    breakeven = float(profit.breakeven_ad_spend)
    max_daily_spend = breakeven * 1.5

    if decision_type == "adjust_bid" and action.get("field") == "daily_budget":
        new_value = action.get("new_value", 0)
        if isinstance(new_value, (int, float)) and new_value > max_daily_spend > 0:
            reasons.append(
                f"新预算 ${new_value:.2f} 超出上限 ${max_daily_spend:.2f} "
                f"(盈亏平衡 ${breakeven:.2f} × 150%)"
            )
            details["new_budget"] = new_value
            details["max_allowed"] = max_daily_spend
            return BoundaryResult(
                passed=False,
                boundary_type="hard",
                reason="; ".join(reasons),
                details=details,
            )

    # ── 硬边界 5: 调价幅度超过 5% ──────────────────
    if decision_type == "adjust_price" and action.get("field") == "price":
        change_pct = abs(action.get("change_pct", 0))
        if isinstance(change_pct, (int, float)) and change_pct > 0.05:
            reasons.append(
                f"调价幅度 {change_pct:.1%} 超出上限 5%"
            )
            details["change_pct"] = change_pct
            return BoundaryResult(
                passed=False,
                boundary_type="hard",
                reason="; ".join(reasons),
                details=details,
            )

    # ── 通过 ──────────────────────────────────────
    if not reasons:
        logger.info("边界检查通过: SKU=%s decision=%s", sku_id, decision_type)
        return BoundaryResult(passed=True)

    logger.warning("边界检查未通过: SKU=%s reason=%s", sku_id, "; ".join(reasons))
    return BoundaryResult(passed=False, reason="; ".join(reasons), details=details)
