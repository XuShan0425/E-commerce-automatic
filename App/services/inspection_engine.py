"""小易巡检引擎 — 自动巡检 SKU 广告表现异常并输出建议.

课程来源: learning.aliexpress.com 课程 id=415 "智能投助手小易巡检盯盘"

巡检场景:
  1. 流量洞察 — 曝光/点击异常
  2. 成本洞察 — CPC/花费异常
  3. 曝光监控 — 曝光骤降检测
  4. 效果预警 — ROI/转化率预警

六大功能:
  1. 提示气泡（最新巡检结果）
  2. 智能助手菜单栏
  3. 巡检结果卡片（每页最多4个计划）
  4. 换品建议（自动识别效果不佳商品，推荐优质替代品）
  5. 预算建议（预算即将耗尽且效果好的计划）
  6. 巡检盯盘配置（开关各场景）
"""

from __future__ import annotations

import statistics
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from App.core.logging import get_logger
from App.models.ads_expert import InspectionReport
from App.models.base import AdSnapshot, Product

logger = get_logger(__name__)

# ── 阈值常量（可配置）───────────────────────────────

EXPOSURE_DROP_THRESHOLD = 0.40       # 曝光下降≥40%触发
CTR_DROP_THRESHOLD = 0.30            # CTR下降≥30%触发
CVR_DROP_THRESHOLD = 0.25            # CVR下降≥25%触发
ROI_NEGATIVE_DAYS = 3                # ROI连续3天<1.0触发
SPEND_SURGE_THRESHOLD = 0.80         # 花费超过预算80%
SPEND_DROP_THRESHOLD = 0.50          # 花费骤降50%+
REPLACE_ROI_THRESHOLD = 0.5          # 连续5天ROI<0.5触发换品建议
REPLACE_DAYS = 5                     # 连续天数阈值
BUDGET_EXHAUST_THRESHOLD = 0.85      # 预算消耗≥85%时建议加预算

# ── 巡检类型 ────────────────────────────────────────

INSPECTION_TYPES = [
    "exposure_anomaly",
    "click_anomaly",
    "roi_anomaly",
    "spend_anomaly",
    "conversion_anomaly",
    "replace_product",
    "budget_suggestion",
]


# ── 辅助函数 ────────────────────────────────────────


async def _get_recent_snapshots(
    db: AsyncSession, sku_id: str, days: int = 10
) -> list[AdSnapshot]:
    """获取最近 N 天的广告快照."""
    since = datetime.now(UTC) - timedelta(days=days)
    result = await db.execute(
        select(AdSnapshot)
        .where(AdSnapshot.sku_id == sku_id, AdSnapshot.snapshot_time >= since)
        .order_by(AdSnapshot.snapshot_time.asc())
    )
    return list(result.scalars().all())


def _split_recent_vs_previous(
    snapshots: list[AdSnapshot], recent_days: int = 3
) -> tuple[list[AdSnapshot], list[AdSnapshot]]:
    """将快照分为近期(recent_days天)和之前两部分."""
    if not snapshots:
        return [], []

    cutoff = datetime.now(UTC) - timedelta(days=recent_days)
    recent = [s for s in snapshots if s.snapshot_time >= cutoff]
    previous = [s for s in snapshots if s.snapshot_time < cutoff]
    return recent, previous


def _aggregate_metrics(snapshots: list[AdSnapshot]) -> dict[str, float]:
    """聚合快照的核心指标."""
    if not snapshots:
        return {
            "impressions": 0, "clicks": 0, "orders": 0,
            "ad_spend": 0.0, "revenue": 0.0, "ctr": 0.0,
            "cvr": 0.0, "cpc": 0.0, "roi": 0.0,
        }

    imp = sum(s.impressions for s in snapshots)
    clk = sum(s.clicks for s in snapshots)
    ord_ = sum(s.orders for s in snapshots)
    spd = sum(float(s.ad_spend) for s in snapshots)
    rev = sum(float(s.revenue) for s in snapshots)

    return {
        "impressions": imp,
        "clicks": clk,
        "orders": ord_,
        "ad_spend": round(spd, 2),
        "revenue": round(rev, 2),
        "ctr": round(clk / imp, 4) if imp > 0 else 0.0,
        "cvr": round(ord_ / clk, 4) if clk > 0 else 0.0,
        "cpc": round(spd / clk, 4) if clk > 0 else 0.0,
        "roi": round(rev / spd, 4) if spd > 0 else 0.0,
    }


def _get_daily_roi_data(snapshots: list[AdSnapshot]) -> list[dict[str, Any]]:
    """获取每日ROI数据列表."""
    daily: list[dict[str, Any]] = []
    for s in snapshots:
        spd = float(s.ad_spend)
        rev = float(s.revenue)
        daily.append({
            "date": s.snapshot_time.strftime("%Y-%m-%d") if s.snapshot_time else "?",
            "roi": round(rev / spd, 4) if spd > 0 else 0.0,
            "ad_spend": round(spd, 2),
            "revenue": round(rev, 2),
        })
    return daily


# ── 巡检检查器 ──────────────────────────────────────


async def _check_exposure_anomaly(
    recent: list[AdSnapshot], previous: list[AdSnapshot],
) -> dict[str, Any] | None:
    """曝光异常检测: 近3天曝光 vs 前7天均值，下降≥40%."""
    recent_agg = _aggregate_metrics(recent)
    prev_agg = _aggregate_metrics(previous)

    if prev_agg["impressions"] == 0 or recent_agg["impressions"] == 0:
        return None

    # 计算日均曝光
    recent_daily = recent_agg["impressions"] / max(len(recent), 1)
    prev_daily = prev_agg["impressions"] / max(len(previous), 1)

    if prev_daily == 0:
        return None

    drop_ratio = (prev_daily - recent_daily) / prev_daily
    if drop_ratio >= EXPOSURE_DROP_THRESHOLD:
        return {
            "alert_type": "exposure_anomaly",
            "severity": "warning" if drop_ratio < 0.6 else "critical",
            "reason": f"曝光量异常下降{drop_ratio:.0%}（近3天日均{recent_daily:.0f} vs "
                      f"前期日均{prev_daily:.0f}）",
            "suggestion": "检查关键词排名是否下降、竞品是否加大投放、"
                          "商品是否受到平台处罚或搜索排名调整。建议重商品Listing优化。",
            "detail_data": {
                "drop_ratio": round(drop_ratio, 4),
                "recent_daily_impressions": round(recent_daily, 0),
                "previous_daily_impressions": round(prev_daily, 0),
            },
        }
    return None


async def _check_click_anomaly(
    recent: list[AdSnapshot], previous: list[AdSnapshot],
) -> dict[str, Any] | None:
    """点击异常检测: 近3天CTR vs 前7天均值，下降≥30%."""
    recent_agg = _aggregate_metrics(recent)
    prev_agg = _aggregate_metrics(previous)

    if prev_agg["ctr"] == 0 or recent_agg["ctr"] == 0:
        return None

    if prev_agg["ctr"] > 0:
        ctr_drop = (prev_agg["ctr"] - recent_agg["ctr"]) / prev_agg["ctr"]
        if ctr_drop >= CTR_DROP_THRESHOLD:
            return {
                "alert_type": "click_anomaly",
                "severity": "warning",
                "reason": f"CTR异常下降{ctr_drop:.0%}（近3天{recent_agg['ctr']:.2%} vs "
                          f"前期{prev_agg['ctr']:.2%}）",
                "suggestion": "检查主图是否需优化、标题是否匹配用户搜索意图、"
                              "广告创意是否过时。建议A/B测试主图。",
                "detail_data": {
                    "ctr_drop": round(ctr_drop, 4),
                    "recent_ctr": recent_agg["ctr"],
                    "previous_ctr": prev_agg["ctr"],
                },
            }
    return None


async def _check_roi_anomaly(
    snapshots: list[AdSnapshot],
) -> dict[str, Any] | None:
    """ROI异常检测: ROI连续3天<1.0."""
    daily_roi = _get_daily_roi_data(snapshots)
    if len(daily_roi) < ROI_NEGATIVE_DAYS:
        return None

    recent_days = daily_roi[-ROI_NEGATIVE_DAYS:]
    all_below = all(d["roi"] < 1.0 for d in recent_days)

    if all_below:
        avg_roi = statistics.mean(d["roi"] for d in recent_days)
        return {
            "alert_type": "roi_anomaly",
            "severity": "warning" if avg_roi >= 0.5 else "critical",
            "reason": (
                f"ROI连续{ROI_NEGATIVE_DAYS}天低于1.0"
                f"（近{ROI_NEGATIVE_DAYS}天平均ROI={avg_roi:.2f}）"
            ),
            "suggestion": "检查商品定价是否有竞争力、广告出价是否过高、"
                          "关键词是否匹配。建议降低出价或暂停广告重新评估策略。",
            "detail_data": {
                "avg_roi": round(avg_roi, 4),
                "negative_days": ROI_NEGATIVE_DAYS,
                "daily_roi": recent_days,
            },
        }
    return None


async def _check_spend_anomaly(
    recent: list[AdSnapshot], previous: list[AdSnapshot],
    breakeven_ad_spend: float | None = None,
) -> dict[str, Any] | None:
    """花费异常检测: 花费超预算80% 或 骤降50%+."""
    recent_agg = _aggregate_metrics(recent)
    prev_agg = _aggregate_metrics(previous)

    findings: list[str] = []

    # 花费超额
    if breakeven_ad_spend and breakeven_ad_spend > 0:
        daily_spend = recent_agg["ad_spend"] / max(len(recent), 1)
        daily_limit = breakeven_ad_spend * 1.5
        if daily_spend > daily_limit * SPEND_SURGE_THRESHOLD:
            findings.append(
                f"日花费${daily_spend:.2f}已达上限${daily_limit:.2f}的"
                f"{daily_spend / daily_limit:.0%}"
            )

    # 花费骤降
    if prev_agg["ad_spend"] > 0 and recent_agg["ad_spend"] > 0:
        prev_daily = prev_agg["ad_spend"] / max(len(previous), 1)
        recent_daily = recent_agg["ad_spend"] / max(len(recent), 1)
        if prev_daily > 0:
            spend_drop = (prev_daily - recent_daily) / prev_daily
            if spend_drop >= SPEND_DROP_THRESHOLD:
                findings.append(
                    f"日均花费下降{spend_drop:.0%}（近3天${recent_daily:.2f} vs "
                    f"前期${prev_daily:.2f}）"
                )

    if findings:
        return {
            "alert_type": "spend_anomaly",
            "severity": "warning",
            "reason": "; ".join(findings),
            "suggestion": "检查广告计划是否被暂停、预算是否耗尽、"
                          "竞价是否失败（出价低于竞争对手范围）。",
            "detail_data": {
                "findings": findings,
                "recent_ad_spend": recent_agg["ad_spend"],
                "previous_ad_spend": prev_agg["ad_spend"],
            },
        }
    return None


async def _check_conversion_anomaly(
    recent: list[AdSnapshot], previous: list[AdSnapshot],
) -> dict[str, Any] | None:
    """转化异常检测: 近3天CVR vs 前7天均值，下降≥25%."""
    recent_agg = _aggregate_metrics(recent)
    prev_agg = _aggregate_metrics(previous)

    if prev_agg["cvr"] == 0 or recent_agg["cvr"] == 0:
        return None

    if prev_agg["cvr"] > 0:
        cvr_drop = (prev_agg["cvr"] - recent_agg["cvr"]) / prev_agg["cvr"]
        if cvr_drop >= CVR_DROP_THRESHOLD:
            return {
                "alert_type": "conversion_anomaly",
                "severity": "warning" if cvr_drop < 0.5 else "critical",
                "reason": f"转化率异常下降{cvr_drop:.0%}（近3天{recent_agg['cvr']:.2%} vs "
                          f"前期{prev_agg['cvr']:.2%}）",
                "suggestion": "检查商品详情页质量、评价和评分是否下降、"
                              "竞争对手是否降价、价格是否高于竞品。",
                "detail_data": {
                    "cvr_drop": round(cvr_drop, 4),
                    "recent_cvr": recent_agg["cvr"],
                    "previous_cvr": prev_agg["cvr"],
                },
            }
    return None


async def _check_replace_product(
    db: AsyncSession, sku_id: str, snapshots: list[AdSnapshot],
) -> dict[str, Any] | None:
    """SKU换品建议: 连续N天ROI<阈值，且有同类替代品."""
    daily_roi = _get_daily_roi_data(snapshots)
    if len(daily_roi) < REPLACE_DAYS:
        return None

    recent_days = daily_roi[-REPLACE_DAYS:]
    all_below = all(d["roi"] < REPLACE_ROI_THRESHOLD for d in recent_days)

    if all_below:
        # 寻找同类替代品
        result = await db.execute(select(Product).where(Product.sku_id == sku_id))
        current = result.scalar_one_or_none()
        replacement_suggestion = None
        if current and current.category:
            alt_result = await db.execute(
                select(Product)
                .where(
                    Product.category == current.category,
                    Product.sku_id != sku_id,
                    Product.is_tracked.is_(True),
                )
                .limit(3)
            )
            alternatives = list(alt_result.scalars().all())
            if alternatives:
                replacement_suggestion = [
                    {"sku_id": a.sku_id, "name": a.name}
                    for a in alternatives
                ]

        avg_roi = statistics.mean(d["roi"] for d in recent_days)
        return {
            "alert_type": "replace_product",
            "severity": "critical",
            "reason": (
                f"连续{REPLACE_DAYS}天ROI低于{REPLACE_ROI_THRESHOLD}"
                f"（近{REPLACE_DAYS}天平均ROI={avg_roi:.2f}），"
                f"建议替换商品。"
            ),
            "suggestion": "推荐替换为该类目下表现更优的已追踪商品。",
            "detail_data": {
                "avg_roi": round(avg_roi, 4),
                "consecutive_days": REPLACE_DAYS,
                "daily_roi": recent_days,
                "replacement_suggestions": replacement_suggestion,
            },
        }
    return None


async def _check_budget_suggestion(
    recent: list[AdSnapshot], breakeven_ad_spend: float | None = None,
) -> dict[str, Any] | None:
    """预算建议: ROI健康的计划预算将耗尽时建议增加预算."""
    if breakeven_ad_spend is None or breakeven_ad_spend <= 0:
        return None

    recent_agg = _aggregate_metrics(recent)
    if recent_agg["roi"] < ROI_HEALTHY_THRESHOLD:
        return None

    daily_spend = recent_agg["ad_spend"] / max(len(recent), 1)
    daily_limit = breakeven_ad_spend * 1.5

    if daily_limit > 0 and daily_spend / daily_limit >= BUDGET_EXHAUST_THRESHOLD:
        suggested_budget = round(daily_limit * 1.3, 2)  # 建议增加30%
        return {
            "alert_type": "budget_suggestion",
            "severity": "info",
            "reason": f"ROI={recent_agg['roi']:.2f}表现良好，预算消耗已达"
                      f"{daily_spend / daily_limit:.0%}，可能即将耗尽。",
            "suggestion": f"建议将日预算从${daily_limit:.2f}增至${suggested_budget:.2f}"
                          f"（+30%），以充分利用当前高ROI窗口。",
            "detail_data": {
                "current_budget": daily_limit,
                "suggested_budget": suggested_budget,
                "current_roi": recent_agg["roi"],
                "spend_ratio": round(daily_spend / daily_limit, 4),
            },
        }
    return None


ROI_HEALTHY_THRESHOLD = 1.2  # ROI健康线（用于预算建议）


# ── 主巡检函数 ──────────────────────────────────────


async def inspect_single_sku(
    db: AsyncSession,
    sku_id: str,
    *,
    breakeven_ad_spend: float | None = None,
    persist: bool = True,
) -> list[dict[str, Any]]:
    """对单个 SKU 执行全量巡检.

    Args:
        db: 数据库会话
        sku_id: 商品 SKU ID
        breakeven_ad_spend: 盈亏平衡广告花费（可选）
        persist: 是否将结果保存到 inspection_reports 表

    Returns:
        巡检结果列表，每个元素是一个巡检发现
    """
    snapshots = await _get_recent_snapshots(db, sku_id, days=10)
    recent, previous = _split_recent_vs_previous(snapshots, recent_days=3)

    checks = [
        _check_exposure_anomaly(recent, previous),
        _check_click_anomaly(recent, previous),
        _check_roi_anomaly(snapshots),
        _check_spend_anomaly(recent, previous, breakeven_ad_spend),
        _check_conversion_anomaly(recent, previous),
        _check_replace_product(db, sku_id, snapshots),
        _check_budget_suggestion(recent, breakeven_ad_spend),
    ]

    findings: list[dict[str, Any]] = []
    for check in checks:
        result = await check if hasattr(check, "__await__") else check
        if result:
            findings.append(result)

    # 持久化
    if persist and findings:
        for f in findings:
            report = InspectionReport(
                sku_id=sku_id,
                alert_type=f["alert_type"],
                severity=f.get("severity", "info"),
                reason=f.get("reason", ""),
                suggestion=f.get("suggestion"),
                detail_data=f.get("detail_data"),
            )
            db.add(report)

    logger.info(
        "巡检完成",
        extra={
            "sku_id": sku_id,
            "findings_count": len(findings),
            "alert_types": [f["alert_type"] for f in findings],
        },
    )

    return findings


async def inspect_all_skus(
    db: AsyncSession,
    *,
    persist: bool = True,
) -> list[dict[str, Any]]:
    """对所有已追踪 SKU 执行巡检."""
    result = await db.execute(
        select(Product).where(Product.is_tracked.is_(True))
    )
    products = list(result.scalars().all())

    all_findings: list[dict[str, Any]] = []
    for product in products:
        findings = await inspect_single_sku(db, product.sku_id, persist=persist)
        all_findings.extend(findings)

    # 按严重程度排序: critical → warning → info
    severity_order = {"critical": 0, "warning": 1, "info": 2}
    all_findings.sort(key=lambda f: severity_order.get(f.get("severity", "info"), 99))

    logger.info(
        "全店巡检完成",
        extra={
            "sku_count": len(products),
            "total_findings": len(all_findings),
        },
    )

    return all_findings


def get_severity_label(severity: str) -> str:
    """严重程度中文标签."""
    return {"critical": "严重", "warning": "警告", "info": "提示"}.get(severity, severity)


def get_alert_type_label(alert_type: str) -> str:
    """巡检类型中文标签."""
    labels = {
        "exposure_anomaly": "曝光异常",
        "click_anomaly": "点击异常",
        "roi_anomaly": "ROI异常",
        "spend_anomaly": "花费异常",
        "conversion_anomaly": "转化异常",
        "replace_product": "换品建议",
        "budget_suggestion": "预算建议",
    }
    return labels.get(alert_type, alert_type)
