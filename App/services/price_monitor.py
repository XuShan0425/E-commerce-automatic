"""价格监控服务 — 检测价格变动、触发警报."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from App.core.logging import get_logger
from App.models.base import PriceSnapshot
from App.schemas.price_snapshot import PriceChangeResult
from App.services.alert_service import raise_alert

logger = get_logger(__name__)

# ── 默认阈值 ──────────────────────────────────────
DEFAULT_PRICE_CHANGE_THRESHOLD = 0.10  # 10%


async def get_price_history(
    db: AsyncSession,
    sku_id: str,
    limit: int = 30,
) -> list[PriceSnapshot]:
    """查询指定 SKU 的价格快照历史（按时间倒序）。"""
    result = await db.execute(
        select(PriceSnapshot)
        .where(PriceSnapshot.sku_id == sku_id)
        .order_by(PriceSnapshot.snapshot_time.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_latest_price_per_sku(db: AsyncSession) -> list[PriceSnapshot]:
    """查询所有 SKU 的最新价格快照。

    使用子查询按 sku_id 分组取最大 snapshot_time。
    """
    subq = (
        select(
            PriceSnapshot.sku_id,
            func.max(PriceSnapshot.snapshot_time).label("max_time"),
        )
        .group_by(PriceSnapshot.sku_id)
        .subquery()
    )

    result = await db.execute(
        select(PriceSnapshot)
        .join(
            subq,
            func.concat(PriceSnapshot.sku_id, PriceSnapshot.snapshot_time)
            == func.concat(subq.c.sku_id, subq.c.max_time),
        )
        .order_by(PriceSnapshot.sku_id)
    )
    return list(result.scalars().all())


async def detect_price_change(
    db: AsyncSession,
    sku_id: str,
    threshold: float = DEFAULT_PRICE_CHANGE_THRESHOLD,
    *,
    alert_on_significant: bool = False,
) -> PriceChangeResult | None:
    """检测某 SKU 的最新价格相比前一条记录的变动。

    Args:
        db: 数据库会话
        sku_id: 商品 SKU ID
        threshold: 视为显著变动的阈值（小数，默认 0.10 即 10%）
        alert_on_significant: 当检测到显著变动时是否发出警报

    Returns:
        如果历史记录足够（>=2条），返回 PriceChangeResult；
        否则返回 None。
    """
    # 获取最近两条记录
    result = await db.execute(
        select(PriceSnapshot)
        .where(PriceSnapshot.sku_id == sku_id)
        .order_by(PriceSnapshot.snapshot_time.desc())
        .limit(2)
    )
    rows = list(result.scalars().all())

    if len(rows) < 2:
        return None

    current = float(rows[0].current_price)
    previous = float(rows[1].current_price)

    if previous == 0:
        return None

    change_pct = (current - previous) / previous
    abs_change = abs(change_pct)

    is_significant = abs_change >= threshold
    if change_pct > 0:
        direction = "up"
    elif change_pct < 0:
        direction = "down"
    else:
        direction = "unchanged"

    # 可选：发送警报
    if is_significant and alert_on_significant:
        direction_label = "上涨" if direction == "up" else "下跌"
        pct_label = f"{abs_change * 100:.1f}%"
        await raise_alert(
            db,
            alert_type="price_change",
            message=(
                f"SKU {sku_id} 价格{direction_label} {pct_label}："
                f"${previous:.2f} → ${current:.2f}"
            ),
            severity="warning" if direction == "down" else "info",
        )

    return PriceChangeResult(
        sku_id=sku_id,
        previous_price=round(previous, 2),
        current_price=round(current, 2),
        change_pct=round(change_pct, 4),
        is_significant=is_significant,
        direction=direction,
    )
