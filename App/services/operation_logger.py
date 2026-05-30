"""操作日志服务 — 写入和查询操作记录."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from App.models.operation_log import OperationLog

logger = logging.getLogger(__name__)


async def log_operation(
    db: AsyncSession,
    sku_id: str,
    operation_type: str,
    *,
    field_name: str | None = None,
    old_value: float | None = None,
    new_value: float | None = None,
    ai_confidence: float | None = None,
    ai_reasoning: str | None = None,
    status: str = "success",
    details: dict[str, Any] | None = None,
) -> OperationLog:
    """写入一条操作日志。

    Args:
        db: 数据库会话
        sku_id: 商品 SKU ID
        operation_type: 操作类型 (adjust_bid / adjust_price / switch_ad_type / stop_ad / no_action)
        field_name: 被修改的字段 (daily_budget / price / ad_type)
        old_value: 旧值
        new_value: 新值
        ai_confidence: AI 置信度
        ai_reasoning: AI 推理说明
        status: 执行状态 (success / failed / pending_confirmation / rejected)
        details: 额外详情 (JSON)

    Returns:
        保存后的 OperationLog 记录
    """
    log = OperationLog(
        sku_id=sku_id,
        operation_type=operation_type,
        field_name=field_name,
        old_value=old_value,
        new_value=new_value,
        ai_confidence=ai_confidence,
        ai_reasoning=ai_reasoning,
        status=status,
        executed_at=datetime.now(timezone.utc),
        details=details or {},
    )
    db.add(log)
    await db.flush()
    await db.refresh(log)
    logger.info("操作日志: SKU=%s type=%s status=%s", sku_id, operation_type, status)
    return log


async def update_log_status(
    db: AsyncSession,
    log_id: int,
    status: str,
    *,
    error_details: dict[str, Any] | None = None,
) -> OperationLog | None:
    """更新操作日志状态。"""
    log = await db.get(OperationLog, log_id)
    if log is None:
        return None
    log.status = status
    if error_details:
        existing = log.details or {}
        existing.update(error_details)
        log.details = existing
    await db.flush()
    await db.refresh(log)
    return log


async def get_pending_operations(
    db: AsyncSession,
    limit: int = 50,
) -> list[OperationLog]:
    """获取所有待确认的操作（软边界暂停的决策）。"""
    result = await db.execute(
        select(OperationLog)
        .where(OperationLog.status == "pending_confirmation")
        .order_by(OperationLog.executed_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_logs(
    db: AsyncSession,
    *,
    sku_id: str | None = None,
    status: str | None = None,
    operation_type: str | None = None,
    limit: int = 100,
) -> list[OperationLog]:
    """查询操作日志，支持多条件筛选。"""
    stmt = select(OperationLog)
    if sku_id:
        stmt = stmt.where(OperationLog.sku_id == sku_id)
    if status:
        stmt = stmt.where(OperationLog.status == status)
    if operation_type:
        stmt = stmt.where(OperationLog.operation_type == operation_type)
    stmt = stmt.order_by(OperationLog.executed_at.desc()).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())


def _format_log_message(log: OperationLog) -> str:
    """格式化操作日志为人类可读的消息（符合 CLAUDE.md 规范）。

    示例：2026-05-30 14:32 | 蓝牙耳机 | 调整出价 | $2.80→$2.94 | 置信度82% | 成功
    """
    parts = [
        log.executed_at.strftime("%Y-%m-%d %H:%M") if log.executed_at else "?",
        log.sku_id,
    ]

    type_names = {
        "adjust_bid": "调整出价",
        "adjust_price": "调整价格",
        "switch_ad_type": "切换广告类型",
        "stop_ad": "停止推广",
        "no_action": "无操作",
    }
    parts.append(type_names.get(log.operation_type, log.operation_type))

    if log.old_value is not None and log.new_value is not None:
        parts.append(f"${log.old_value:.2f}→${log.new_value:.2f}")

    if log.ai_confidence is not None:
        parts.append(f"置信度{log.ai_confidence:.0%}")

    status_names = {
        "success": "成功",
        "failed": "失败",
        "pending_confirmation": "待确认",
        "rejected": "已拒绝",
    }
    parts.append(status_names.get(log.status, log.status))

    return " | ".join(parts)
