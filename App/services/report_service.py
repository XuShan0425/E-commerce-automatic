"""报告生成服务 — ROI 连续为负分析报告 + 推广活动关闭说明."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from App.core.logging import get_logger
from App.models.base import AdSnapshot, Product, ProfitAnalysis
from App.models.report import Report

logger = get_logger(__name__)


async def generate_roi_negative_report(
    db: AsyncSession,
    sku_id: str,
) -> Report:
    """生成 ROI 连续为负分析报告。

    报告包含:
      1. 近 7 天 ROI 趋势图数据
      2. 每日广告花费 vs 收入对比
      3. 各地区转化率分布
      4. AI 推断的可能原因
      5. 建议的人工干预方向

    Args:
        db: 数据库会话
        sku_id: 商品 SKU ID

    Returns:
        保存后的 Report 记录
    """
    # 获取商品信息
    product_result = await db.execute(
        select(Product).where(Product.sku_id == sku_id)
    )
    product = product_result.scalar_one_or_none()
    product_name = product.name if product else sku_id

    # 获取最新的利润分析
    profit_result = await db.execute(
        select(ProfitAnalysis)
        .where(ProfitAnalysis.sku_id == sku_id)
        .order_by(ProfitAnalysis.calc_time.desc())
        .limit(1)
    )
    profit = profit_result.scalar_one_or_none()

    # 获取近 7 天广告快照
    since = datetime.now(UTC)
    snapshot_result = await db.execute(
        select(AdSnapshot)
        .where(AdSnapshot.sku_id == sku_id, AdSnapshot.snapshot_time >= since)
        .order_by(AdSnapshot.snapshot_time.asc())
    )
    snapshots = list(snapshot_result.scalars().all())

    # ── 构建报告内容 ──────────────────────────────

    # 1. ROI 趋势数据
    roi_trend = []
    if profit and profit.roi_7d_trend:
        roi_trend = profit.roi_7d_trend
        if isinstance(roi_trend, dict):
            roi_trend = roi_trend.get("data", [])

    # 2. 每日广告花费 vs 收入对比
    daily_comparison: dict[str, dict[str, float]] = {}
    for snap in snapshots:
        day_key = snap.snapshot_time.strftime("%Y-%m-%d")
        if day_key not in daily_comparison:
            daily_comparison[day_key] = {"ad_spend": 0.0, "revenue": 0.0}
        daily_comparison[day_key]["ad_spend"] += float(snap.ad_spend)
        daily_comparison[day_key]["revenue"] += float(snap.revenue)

    daily_data = [
        {"date": day, "ad_spend": round(v["ad_spend"], 2), "revenue": round(v["revenue"], 2)}
        for day, v in sorted(daily_comparison.items())
    ]

    # 3. 各地区转化率分布
    region_breakdown: dict[str, dict[str, float]] = {}
    for snap in snapshots:
        if snap.buyer_region_breakdown and isinstance(snap.buyer_region_breakdown, dict):
            for region, count in snap.buyer_region_breakdown.items():
                try:
                    count_val = float(count) if not isinstance(count, (int, float)) else count
                except (ValueError, TypeError):
                    count_val = 0.0
                if region not in region_breakdown:
                    region_breakdown[region] = {"orders": 0.0, "impressions": 0.0}
                region_breakdown[region]["orders"] += count_val
                region_breakdown[region]["impressions"] += float(snap.impressions)

    region_data = [
        {
            "region": region,
            "orders": round(data["orders"], 2),
            "impressions": data["impressions"],
            "conversion_rate": round(
                data["orders"] / data["impressions"] * 100, 4
            ) if data["impressions"] > 0 else 0.0,
        }
        for region, data in sorted(region_breakdown.items())
    ]

    # 4 & 5. AI 推断原因和建议
    current_roi = float(profit.current_roi) if profit else 0.0
    gross_margin = float(profit.gross_margin) if profit else 0.0
    total_ad_spend = sum(float(s.ad_spend) for s in snapshots)
    total_revenue = sum(float(s.revenue) for s in snapshots)

    possible_causes = _infer_negative_roi_causes(
        current_roi=current_roi,
        gross_margin=gross_margin,
        total_ad_spend=total_ad_spend,
        total_revenue=total_revenue,
        roi_trend=roi_trend,
        region_data=region_data,
    )

    suggested_actions = _suggest_actions(
        possible_causes=possible_causes,
        current_roi=current_roi,
        gross_margin=gross_margin,
    )

    content: dict[str, Any] = {
        "sku_id": sku_id,
        "product_name": product_name,
        "generated_at": datetime.now(UTC).isoformat(),
        "summary": {
            "current_roi": round(current_roi, 4),
            "total_ad_spend_7d": round(total_ad_spend, 2),
            "total_revenue_7d": round(total_revenue, 2),
            "gross_margin": round(gross_margin, 4),
            "breakeven_ad_spend": round(float(profit.breakeven_ad_spend), 2) if profit else 0.0,
        },
        "roi_trend": roi_trend,
        "daily_spend_vs_revenue": daily_data,
        "region_conversion": region_data,
        "possible_causes": possible_causes,
        "suggested_actions": suggested_actions,
    }

    title = f"ROI 连续为负分析报告 — {product_name} ({sku_id})"

    report = Report(
        sku_id=sku_id,
        report_type="roi_negative",
        title=title,
        content=content,
    )
    db.add(report)
    await db.flush()
    await db.refresh(report)

    logger.info(
        "ROI 负值报告已生成: SKU=%s roi=%.4f spend=%.2f revenue=%.2f",
        sku_id, current_roi, total_ad_spend, total_revenue,
    )
    return report


async def generate_campaign_close_report(
    db: AsyncSession,
    sku_id: str,
    reason: str,
    summary: str | None = None,
) -> Report:
    """生成推广活动关闭说明。

    包含:
      1. 活动完整数据摘要
      2. 关闭理由（数据驱动）
      3. 预计影响（流量减少估算）
      4. 替代方案建议

    Args:
        db: 数据库会话
        sku_id: 商品 SKU ID
        reason: 关闭原因描述
        summary: 可选摘要

    Returns:
        保存后的 Report 记录
    """
    # 获取商品信息
    product_result = await db.execute(
        select(Product).where(Product.sku_id == sku_id)
    )
    product = product_result.scalar_one_or_none()
    product_name = product.name if product else sku_id

    # 获取最新利润分析
    profit_result = await db.execute(
        select(ProfitAnalysis)
        .where(ProfitAnalysis.sku_id == sku_id)
        .order_by(ProfitAnalysis.calc_time.desc())
        .limit(1)
    )
    profit = profit_result.scalar_one_or_none()

    # 获取近 7 天广告快照
    since = datetime.now(UTC)
    snapshot_result = await db.execute(
        select(AdSnapshot)
        .where(AdSnapshot.sku_id == sku_id, AdSnapshot.snapshot_time >= since)
        .order_by(AdSnapshot.snapshot_time.asc())
    )
    snapshots = list(snapshot_result.scalars().all())

    # ── 构建报告内容 ──────────────────────────────

    total_impressions = sum(s.impressions for s in snapshots)
    total_clicks = sum(s.clicks for s in snapshots)
    total_orders = sum(s.orders for s in snapshots)
    total_ad_spend = sum(float(s.ad_spend) for s in snapshots)
    total_revenue = sum(float(s.revenue) for s in snapshots)
    avg_ctr = (
        (sum(s.ctr for s in snapshots) / len(snapshots))
        if snapshots and any(s.ctr for s in snapshots)
        else 0.0
    )
    avg_conversion = (
        (sum(s.conversion_rate for s in snapshots) / len(snapshots))
        if snapshots and any(s.conversion_rate for s in snapshots)
        else 0.0
    )

    # 估算流量影响
    traffic_impact: dict[str, Any] = {
        "estimated_daily_impression_loss": round(total_impressions / max(len(snapshots), 1), 0),
        "estimated_daily_click_loss": round(total_clicks / max(len(snapshots), 1), 0),
        "estimated_daily_order_loss": round(total_orders / max(len(snapshots), 1), 0),
        "estimated_daily_revenue_loss": round(total_revenue / max(len(snapshots), 1), 2),
        "current_ad_spend_saving": round(total_ad_spend / max(len(snapshots), 1), 2),
    }

    # 替代方案建议
    alternatives = _suggest_alternatives(
        current_roi=float(profit.current_roi) if profit else 0.0,
        gross_margin=float(profit.gross_margin) if profit else 0.0,
        avg_conversion=avg_conversion,
    )

    # 活动数据摘要
    campaign_summary: dict[str, Any] = {
        "sku_id": sku_id,
        "product_name": product_name,
        "period_days": len(snapshots),
        "total_impressions": total_impressions,
        "total_clicks": total_clicks,
        "total_orders": total_orders,
        "total_ad_spend": round(total_ad_spend, 2),
        "total_revenue": round(total_revenue, 2),
        "avg_ctr": round(avg_ctr, 4),
        "avg_conversion_rate": round(avg_conversion, 4),
        "current_roi": round(float(profit.current_roi), 4) if profit else 0.0,
        "gross_margin": round(float(profit.gross_margin), 4) if profit else 0.0,
        "breakeven_ad_spend": round(float(profit.breakeven_ad_spend), 2) if profit else 0.0,
    }

    content: dict[str, Any] = {
        "sku_id": sku_id,
        "product_name": product_name,
        "generated_at": datetime.now(UTC).isoformat(),
        "close_reason": reason,
        "summary_text": summary or "",
        "campaign_summary": campaign_summary,
        "traffic_impact": traffic_impact,
        "alternatives": alternatives,
    }

    title = f"推广活动关闭说明 — {product_name} ({sku_id})"

    report = Report(
        sku_id=sku_id,
        report_type="campaign_close",
        title=title,
        content=content,
    )
    db.add(report)
    await db.flush()
    await db.refresh(report)

    logger.info(
        "活动关闭说明已生成: SKU=%s reason=%s impact_daily_orders=%.0f",
        sku_id, reason, traffic_impact["estimated_daily_order_loss"],
    )
    return report


async def get_report(
    db: AsyncSession,
    report_id: int,
) -> Report | None:
    """获取单个报告。"""
    report = await db.get(Report, report_id)
    return report


async def list_reports(
    db: AsyncSession,
    *,
    sku_id: str | None = None,
    report_type: str | None = None,
    limit: int = 50,
) -> list[Report]:
    """查询报告列表，支持按 sku_id 和 report_type 筛选。"""
    stmt = select(Report)
    if sku_id:
        stmt = stmt.where(Report.sku_id == sku_id)
    if report_type:
        stmt = stmt.where(Report.report_type == report_type)
    stmt = stmt.order_by(Report.created_at.desc()).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())


# ── 辅助函数 ──────────────────────────────────


def _infer_negative_roi_causes(
    current_roi: float,
    gross_margin: float,
    total_ad_spend: float,
    total_revenue: float,
    roi_trend: list,
    region_data: list,
) -> list[str]:
    """推断 ROI 连续为负的可能原因。"""
    causes: list[str] = []

    if gross_margin <= 0:
        causes.append(
            "毛利率为负或为零，商品定价低于总成本"
            "（成本 + 物流 + 平台佣金），建议调整定价策略"
        )
    elif gross_margin < 0.1:
        causes.append("毛利率偏低（不足 10%），利润空间狭小导致广告花费容易超出盈亏平衡点")

    if current_roi < 0.5 and total_ad_spend > 0:
        causes.append(f"广告投入产出比严重偏低（ROI={current_roi:.2f}），广告花费远超带来的收入")

    # 检查趋势
    if roi_trend and len(roi_trend) >= 3:
        recent = roi_trend[-3:]
        worsening = all(
            item.get("roi", 0) <= prev.get("roi", 0)
            for item, prev in zip(recent[1:], recent[:-1])
        )
        if worsening:
            causes.append("近 3 天 ROI 持续恶化趋势，需要紧急干预")

    # 检查地区转化
    low_conv_regions = [
        r["region"] for r in region_data
        if r.get("conversion_rate", 100) < 1.0 and r.get("impressions", 0) > 100
    ]
    if low_conv_regions:
        region_str = ", ".join(low_conv_regions[:5])
        causes.append(f"以下地区转化率偏低（<1%）：{region_str}，可能存在受众定位偏差")

    if not causes:
        causes.append("广告花费过高，未能产生足够的回报，建议优化广告定向或降低出价")

    return causes


def _suggest_actions(
    possible_causes: list[str],
    current_roi: float,
    gross_margin: float,
) -> list[str]:
    """根据原因推荐人工干预方向。"""
    actions: list[str] = []

    if gross_margin <= 0:
        actions.append("紧急：重新评估定价策略，确保售价覆盖（成本 + 物流 + 平台佣金）")
    elif gross_margin < 0.1:
        actions.append("考虑优化供应链或调整售价以提升毛利率")

    if current_roi < 0.5:
        actions.append("暂停或大幅降低广告出价，重新评估广告关键词和受众定位")
    elif current_roi < 1.0:
        actions.append("优化广告创意和落地页，提升转化率以改善 ROI")

    actions.append("检查竞争对手定价和广告策略，确认市场环境变化")
    actions.append("分析买家评论和退单数据，排查产品本身的问题")

    return actions


def _suggest_alternatives(
    current_roi: float,
    gross_margin: float,
    avg_conversion: float,
) -> list[dict[str, str]]:
    """推荐关闭后的替代方案。"""
    alternatives: list[dict[str, str]] = []

    if gross_margin > 0:
        alternatives.append({
            "strategy": "降低出价继续投放",
            "description": "将广告出价下调至盈亏平衡点以下，以低成本维持曝光",
        })

    if avg_conversion > 0.01:
        alternatives.append({
            "strategy": "优化后重新投放",
            "description": "针对高转化地区/时段集中投放，减少低效曝光浪费",
        })

    alternatives.append({
        "strategy": "自然流量优化",
        "description": "优化商品标题、主图、详情页，提升自然搜索排名",
    })

    alternatives.append({
        "strategy": "联盟营销",
        "description": "转向联盟营销（affiliate），按成交付费，降低投放风险",
    })

    if gross_margin > 0.2:
        alternatives.append({
            "strategy": "限时折扣",
            "description": "通过短期促销活动提升转化，测试价格弹性后再决定广告策略",
        })

    return alternatives
