"""利润计算器 — 从各表聚合数据，计算 profit_analysis 指标."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from App.core.logging import get_logger
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from App.models.base import (
    AdSnapshot,
    LogisticsRate,
    PlatformFee,
    PriceSnapshot,
    Product,
    ProfitAnalysis,
)

logger = get_logger(__name__)


async def _get_product(db: AsyncSession, sku_id: str) -> Product | None:
    result = await db.execute(select(Product).where(Product.sku_id == sku_id))
    return result.scalar_one_or_none()


async def _get_latest_price(db: AsyncSession, sku_id: str) -> float:
    result = await db.execute(
        select(PriceSnapshot.current_price)
        .where(PriceSnapshot.sku_id == sku_id)
        .order_by(PriceSnapshot.snapshot_time.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
    return float(row) if row is not None else 0.0


async def _get_platform_fee_rate(db: AsyncSession, category: str | None) -> float:
    if not category:
        return 0.0
    result = await db.execute(
        select(PlatformFee.fee_rate).where(PlatformFee.category.ilike(f"%{category}%"))
    )
    row = result.scalar_one_or_none()
    if row is None:
        # fallback: get first available fee_rate
        result = await db.execute(select(PlatformFee.fee_rate).limit(1))
        row = result.scalar_one_or_none()
    return float(row) if row is not None else 0.0


async def _get_ad_snapshots_7d(db: AsyncSession, sku_id: str) -> list[AdSnapshot]:
    since = datetime.now(timezone.utc) - timedelta(days=7)
    result = await db.execute(
        select(AdSnapshot)
        .where(AdSnapshot.sku_id == sku_id, AdSnapshot.snapshot_time >= since)
        .order_by(AdSnapshot.snapshot_time.asc())
    )
    return list(result.scalars().all())


async def _compute_logistics_cost(
    db: AsyncSession,
    buyer_region_breakdown: dict | None,
) -> float:
    """按买家地区分布加权计算物流成本。

    如果没有地区分布数据，取所有物流费率的平均值。
    """
    if not buyer_region_breakdown:
        # fallback: average across all rates
        result = await db.execute(select(func.avg(LogisticsRate.cost)))
        avg = result.scalar_one_or_none()
        return float(avg) if avg is not None else 0.0

    # 获取所有物流费率
    result = await db.execute(select(LogisticsRate))
    all_rates = list(result.scalars().all())

    if not all_rates:
        return 0.0

    # 构建 region → cost 映射（取该 region 的第一个费率）
    region_cost: dict[str, float] = {}
    for rate in all_rates:
        region_upper = rate.destination_region.upper()
        if region_upper not in region_cost:
            region_cost[region_upper] = float(rate.cost)

    total_weight = 0.0
    weighted_sum = 0.0

    for region_key, proportion in buyer_region_breakdown.items():
        # 尝试匹配地区
        region_upper = region_key.upper()
        try:
            proportion_value = (
                float(proportion)
                if not isinstance(proportion, (int, float))
                else proportion
            )
        except (ValueError, TypeError):
            proportion_value = 0.0

        cost = region_cost.get(region_upper)
        if cost is None:
            # 模糊匹配
            for stored_region, stored_cost in region_cost.items():
                if region_upper in stored_region or stored_region in region_upper:
                    cost = stored_cost
                    break
        if cost is None:
            # 完全没匹配到，用所有费率的平均值
            cost = sum(region_cost.values()) / len(region_cost) if region_cost else 0.0

        weighted_sum += cost * proportion_value
        total_weight += proportion_value

    if total_weight > 0:
        return weighted_sum / total_weight
    return 0.0


def _compute_roi_7d_trend(snapshots: list[AdSnapshot]) -> list[dict[str, Any]]:
    """计算近 7 天每日 ROI 趋势。"""
    daily: dict[str, dict] = {}
    for snap in snapshots:
        day_key = snap.snapshot_time.strftime("%Y-%m-%d")
        if day_key not in daily:
            daily[day_key] = {"revenue": 0.0, "ad_spend": 0.0}
        daily[day_key]["revenue"] += float(snap.revenue)
        daily[day_key]["ad_spend"] += float(snap.ad_spend)

    trend = []
    for day_key in sorted(daily.keys()):
        data = daily[day_key]
        roi = data["revenue"] / data["ad_spend"] if data["ad_spend"] > 0 else 0.0
        trend.append({
            "date": day_key,
            "revenue": round(data["revenue"], 2),
            "ad_spend": round(data["ad_spend"], 2),
            "roi": round(roi, 4),
        })
    return trend


async def compute_profit(db: AsyncSession, sku_id: str) -> ProfitAnalysis:
    """计算单个 SKU 的利润分析并写入数据库。

    Returns:
        保存后的 ProfitAnalysis 记录
    """
    now = datetime.now(timezone.utc)

    # 1. 商品信息
    product = await _get_product(db, sku_id)
    if product is None:
        raise ValueError(f"SKU '{sku_id}' 不存在")

    cost_price = float(product.cost_price)

    # 2. 最新价格
    current_price = await _get_latest_price(db, sku_id)
    if current_price <= 0:
        current_price = cost_price  # fallback

    # 3. 平台费率
    fee_rate = await _get_platform_fee_rate(db, product.category)
    platform_fee_value = round(current_price * fee_rate, 2)

    # 4. 近 7 天广告数据
    snapshots = await _get_ad_snapshots_7d(db, sku_id)

    total_revenue = sum(float(s.revenue) for s in snapshots)
    total_ad_spend = sum(float(s.ad_spend) for s in snapshots)
    total_orders = sum(s.orders for s in snapshots)

    # 聚合 buyer_region_breakdown
    merged_regions: dict[str, float] = {}
    for s in snapshots:
        if s.buyer_region_breakdown and isinstance(s.buyer_region_breakdown, dict):
            for region, count in s.buyer_region_breakdown.items():
                try:
                    count_val = float(count) if not isinstance(count, (int, float)) else count
                except (ValueError, TypeError):
                    count_val = 0.0
                merged_regions[region] = merged_regions.get(region, 0.0) + count_val

    # 5. 物流成本（加权）
    logistics_cost = await _compute_logistics_cost(db, merged_regions or None)
    # 如果地区数据存在但没匹配到费率，用所有费率的平均值
    if logistics_cost <= 0 and merged_regions:
        result = await db.execute(select(func.avg(LogisticsRate.cost)))
        avg = result.scalar_one_or_none()
        logistics_cost = float(avg) if avg is not None else 0.0

    # 6. 核心指标计算
    true_cost = cost_price + logistics_cost + platform_fee_value

    if current_price > 0:
        gross_margin = (current_price - true_cost) / current_price
    else:
        gross_margin = 0.0

    # 盈亏平衡广告花费（单件利润）× 预估销量
    unit_profit = current_price - true_cost
    if total_orders > 0 and unit_profit > 0:
        breakeven_ad_spend = unit_profit * total_orders
    else:
        breakeven_ad_spend = unit_profit  # 至少保本

    # 当前 ROI
    if total_ad_spend > 0:
        current_roi = total_revenue / total_ad_spend
    else:
        current_roi = 0.0

    # 7 日 ROI 趋势
    roi_trend = _compute_roi_7d_trend(snapshots)

    # 7. 写入数据库
    analysis = ProfitAnalysis(
        sku_id=sku_id,
        calc_time=now,
        logistics_cost=round(logistics_cost, 2),
        platform_fee=platform_fee_value,
        true_cost=round(true_cost, 2),
        gross_margin=round(gross_margin, 4),
        breakeven_ad_spend=round(breakeven_ad_spend, 2),
        current_roi=round(current_roi, 4),
        roi_7d_trend=roi_trend,
    )
    db.add(analysis)
    await db.flush()
    await db.refresh(analysis)

    logger.info(
        f"利润计算完成: SKU={sku_id} price={current_price:.2f} cost={true_cost:.2f} margin={gross_margin * 100:.2f}% roi={current_roi:.2f}"
    )

    return analysis
