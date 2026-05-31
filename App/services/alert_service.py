"""警报通知服务 — 写入警报、设置全局停止、邮件通知."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from App.models.alert import Alert
from App.models.system_state import SystemState
from App.services.email_notifier import send_alert_email


async def raise_alert(
    db: AsyncSession,
    alert_type: str,
    message: str,
    severity: str = "warning",
    *,
    set_global_stop: bool = False,
) -> Alert:
    """写入一条警报记录。critical 级别自动发送邮件并设置全局停止。"""
    alert = Alert(
        alert_type=alert_type,
        severity=severity,
        message=message,
    )
    db.add(alert)
    await db.flush()

    if severity == "critical" or set_global_stop:
        await _set_global_stop(db, enabled=True)

    await db.refresh(alert)

    # ── 发送邮件通知 ──────────────────────────────
    await send_alert_email(alert)

    return alert


async def resolve_alert(db: AsyncSession, alert_id: int) -> Alert | None:
    """标记警报为已处理。"""
    result = await db.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalar_one_or_none()
    if alert is None:
        return None
    alert.is_resolved = True
    alert.resolved_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(alert)
    return alert


async def get_active_alerts(db: AsyncSession, limit: int = 50) -> list[Alert]:
    """获取所有未处理警报，按时间倒序。"""
    result = await db.execute(
        select(Alert)
        .where(Alert.is_resolved == False)
        .order_by(Alert.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def _set_global_stop(db: AsyncSession, enabled: bool) -> None:
    """设置全局停止标志。"""
    result = await db.execute(
        select(SystemState).where(SystemState.key == "global_stop")
    )
    record = result.scalar_one_or_none()
    value = {"enabled": enabled, "reason": "alert_triggered", "updated_at": datetime.now(timezone.utc).isoformat()}
    if record is not None:
        record.value = value  # type: ignore[assignment]
    else:
        record = SystemState(key="global_stop", value=value)  # type: ignore[arg-type]
        db.add(record)
    await db.flush()


async def clear_global_stop(db: AsyncSession) -> None:
    """清除全局停止标志（所有警报处理完毕后手动调用）。"""
    await _set_global_stop(db, enabled=False)
