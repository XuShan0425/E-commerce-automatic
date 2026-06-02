"""反馈闭环服务 — 查询操作日志并汇总决策历史。

职责:
  1. 查询 SKU 近 N 天的操作日志
  2. 汇总决策历史（操作类型、新旧值、执行状态、前后 ROI 对比）
  3. 为 AI 决策引擎提供结构化历史上下文

典型用法:
  history = await get_decision_history(db, "sku-123")
  # → { "has_history": True, "recent_decisions": [...], "summary": {...} }
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from App.core.logging import get_logger
from App.models.base import ProfitAnalysis
from App.models.operation_log import OperationLog

logger = get_logger(__name__)

# ── 默认参数 ──────────────────────────────────
_DEFAULT_HISTORY_DAYS = 7  # 回溯天数


async def get_decision_history(
    db: AsyncSession,
    sku_id: str,
    *,
    days: int = _DEFAULT_HISTORY_DAYS,
) -> dict[str, Any]:
    """查询 SKU 近 N 天的操作历史，汇总为 AI 可用的决策上下文。

    Args:
        db: 数据库会话
        sku_id: 商品 SKU ID
        days: 回溯天数（默认 7 天）

    Returns:
        {
            "has_history": bool,          # 是否有历史记录
            "recent_decisions": [         # 最近决策列表（按时间倒序）
                {
                    "operation_type": "adjust_bid",
                    "status": "success",
                    "field_name": "daily_budget",
                    "old_value": 3.00,
                    "new_value": 3.40,
                    "change_pct": 0.133,
                    "ai_reasoning": "...",
                    "ai_confidence": 0.82,
                    "executed_at": "2026-06-01T10:00:00Z",
                    "roi_before": 1.5,     # 操作前 ROI
                    "roi_after": 1.8,      # 操作后 ROI
                    "roi_delta": 0.3,      # ROI 变化量
                },
                ...
            ],
            "summary": {                   # 汇总统计
                "total_operations": 3,
                "success_count": 2,
                "failed_count": 0,
                "pending_count": 0,
                "rejected_count": 0,
                "operation_types": {"adjust_bid": 2, "no_action": 1},
                "avg_confidence": 0.78,
            },
        }
    """
    since = datetime.now(UTC) - timedelta(days=days)

    # ── 查询操作日志 ──────────────────────────
    result = await db.execute(
        select(OperationLog)
        .where(
            OperationLog.sku_id == sku_id,
            OperationLog.executed_at >= since,
        )
        .order_by(OperationLog.executed_at.desc())
        .limit(50)
    )
    logs = list(result.scalars().all())

    if not logs:
        return {
            "has_history": False,
            "recent_decisions": [],
            "summary": {
                "total_operations": 0,
                "success_count": 0,
                "failed_count": 0,
                "pending_count": 0,
                "rejected_count": 0,
                "operation_types": {},
                "avg_confidence": 0.0,
            },
        }

    # ── 查询同时期的利润分析记录（用于 ROI 对比）──
    profit_result = await db.execute(
        select(ProfitAnalysis)
        .where(
            ProfitAnalysis.sku_id == sku_id,
            ProfitAnalysis.calc_time >= since,
        )
        .order_by(ProfitAnalysis.calc_time.asc())
    )
    profit_records = list(profit_result.scalars().all())

    # ── 为每条操作匹配 ROI 变化 ────────────────
    recent_decisions: list[dict[str, Any]] = []

    for log in logs:
        executed_at = log.executed_at
        if executed_at is None:
            continue

        # 查找操作前的最近利润分析记录
        roi_before = _find_nearest_roi(profit_records, executed_at, before=True)
        # 查找操作后的最近利润分析记录
        roi_after = _find_nearest_roi(profit_records, executed_at, before=False)

        roi_delta = None
        if roi_before is not None and roi_after is not None:
            roi_delta = round(roi_after - roi_before, 4)

        # 计算 change_pct（如果提供了 old/new value）
        change_pct = None
        if log.old_value and log.new_value and log.old_value > 0:
            change_pct = round(
                (float(log.new_value) - float(log.old_value)) / float(log.old_value),
                4,
            )

        entry: dict[str, Any] = {
            "operation_type": log.operation_type,
            "status": log.status,
            "field_name": log.field_name,
            "old_value": float(log.old_value) if log.old_value else None,
            "new_value": float(log.new_value) if log.new_value else None,
            "change_pct": change_pct,
            "ai_reasoning": log.ai_reasoning or "",
            "ai_confidence": float(log.ai_confidence) if log.ai_confidence else None,
            "executed_at": executed_at.isoformat() if executed_at else None,
            "roi_before": roi_before,
            "roi_after": roi_after,
            "roi_delta": roi_delta,
        }
        recent_decisions.append(entry)

    # ── 汇总统计 ──────────────────────────────
    total = len(logs)
    success_count = sum(1 for log_entry in logs if log_entry.status == "success")
    failed_count = sum(1 for log_entry in logs if log_entry.status == "failed")
    pending_count = sum(1 for log_entry in logs if log_entry.status == "pending_confirmation")
    rejected_count = sum(1 for log_entry in logs if log_entry.status == "rejected")

    op_types: dict[str, int] = {}
    confidences: list[float] = []
    for log_entry in logs:
        op_types[log_entry.operation_type] = op_types.get(log_entry.operation_type, 0) + 1
        if log_entry.ai_confidence is not None:
            confidences.append(float(log_entry.ai_confidence))

    avg_confidence = round(sum(confidences) / len(confidences), 4) if confidences else 0.0

    summary = {
        "total_operations": total,
        "success_count": success_count,
        "failed_count": failed_count,
        "pending_count": pending_count,
        "rejected_count": rejected_count,
        "operation_types": op_types,
        "avg_confidence": avg_confidence,
    }

    logger.info(
        "决策历史查询完成: SKU=%s total=%d success=%d failed=%d",
        sku_id,
        total,
        success_count,
        failed_count,
    )

    return {
        "has_history": True,
        "recent_decisions": recent_decisions,
        "summary": summary,
    }


def _find_nearest_roi(
    profit_records: list[ProfitAnalysis],
    reference_time: datetime,
    *,
    before: bool = True,
) -> float | None:
    """在利润分析记录中查找离 reference_time 最近的 ROI 值。

    Args:
        profit_records: 按时间升序排列的利润分析记录
        reference_time: 参考时间点
        before: True 查找之前最近, False 查找之后最近

    Returns:
        ROI 值，如果找不到则返回 None
    """
    if not profit_records:
        return None

    if before:
        # 查找 reference_time 之前最近的记录
        for record in reversed(profit_records):
            if record.calc_time <= reference_time:
                return float(record.current_roi)
        # 如果没有之前的记录，返回最早的记录
        return float(profit_records[0].current_roi)
    else:
        # 查找 reference_time 之后最近的记录
        for record in profit_records:
            if record.calc_time >= reference_time:
                return float(record.current_roi)
        # 如果没有之后的记录，返回最新的记录
        return float(profit_records[-1].current_roi)


def format_history_for_prompt(history: dict[str, Any]) -> str:
    """将决策历史格式化为 AI prompt 可读的文本块。

    Args:
        history: get_decision_history() 返回的结果

    Returns:
        格式化后的文本（空历史时返回空字符串）
    """
    if not history.get("has_history"):
        return ""

    lines: list[str] = ["## 近期操作历史（反馈闭环）", ""]
    decisions = history.get("recent_decisions", [])

    if not decisions:
        return ""

    # 汇总行
    summary = history.get("summary", {})
    lines.append(
        f"过去 7 天共有 {summary.get('total_operations', 0)} 次操作，"
        f"成功 {summary.get('success_count', 0)} 次，"
        f"失败 {summary.get('failed_count', 0)} 次，"
        f"待确认 {summary.get('pending_count', 0)} 次。"
    )
    lines.append("")

    # 详细记录（最多显示 10 条）
    for decision in decisions[:10]:
        op_type = decision.get("operation_type", "?")
        status = decision.get("status", "?")
        old_val = decision.get("old_value")
        new_val = decision.get("new_value")
        roi_delta = decision.get("roi_delta")
        confidence = decision.get("ai_confidence")
        reasoning = decision.get("ai_reasoning", "")

        parts = [f"- **{op_type}** (状态: {status})"]
        if old_val is not None and new_val is not None:
            parts.append(f"值变化: {old_val} → {new_val}")
        if roi_delta is not None:
            arrow = "↑" if roi_delta > 0 else "↓"
            parts.append(f"ROI 变化: {roi_delta:+.4f} {arrow}")
        if confidence is not None:
            parts.append(f"置信度: {confidence:.0%}")
        if reasoning:
            parts.append(f"理由: {reasoning[:100]}")

        lines.append("，".join(parts))

    lines.append("")
    lines.append("（以上历史数据供参考，请基于当前数据做出最优决策）")
    lines.append("")

    return "\n".join(lines)
