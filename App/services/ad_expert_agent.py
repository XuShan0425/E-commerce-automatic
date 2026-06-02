"""广告专家 Agent — 模拟资深速卖通广告运营，输出每日诊断.

职责（不是分析数据，而是模拟资深运营）:
  1. 今日重点处理 SKU（基于巡检结果和 ROI 排序）
  2. 今日预算调整建议（高 ROI 加预算，低 ROI 减预算）
  3. 今日关键词建议（添加/暂停/出价调整）
  4. 今日广告诊断（各计划状态 + 问题）
  5. 今日换品建议（低效品 → 替换品推荐）

流程:
  Step 1: 规则引擎聚合所有分析结果
  Step 2: 按优先级排序
  Step 3: LLM 生成运营日报（纯文本，每日只调一次）
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from App.core.logging import get_logger
from App.models.ads_expert import AIRecommendation, InspectionReport
from App.models.base import Product, ProfitAnalysis

logger = get_logger(__name__)

# LLM System Prompt 用于生成运营日报
DAILY_BRIEFING_SYSTEM_PROMPT = """\
你是一个资深的速卖通广告运营专家，正在查看今日的运营数据汇总。
基于系统提供的结构化分析结果，编写一份简明的"每日运营简报"。

简报要求:
1. 用中文，简洁，每条建议不超过 2 句话
2. 聚焦 actionable 的操作建议，不要理论分析
3. 按重要性排序: 紧急问题 > 优化机会 > 常规维护
4. 每个 SKU 只给一条最核心的建议，不要重复

输出格式: 纯文本 markdown
"""


async def _get_priority_skus(
    db: AsyncSession,
) -> list[dict[str, Any]]:
    """获取今日需优先处理的 SKU 列表.

    排序规则:
      1. 有 critical 巡检发现的 SKU
      2. ROI 最低的活跃 SKU
      3. 高 ROI 可加预算的 SKU
    """
    # 获取所有已追踪商品
    result = await db.execute(select(Product).where(Product.is_tracked.is_(True)))
    products = list(result.scalars().all())
    if not products:
        return []

    priority_list: list[dict[str, Any]] = []

    for product in products:
        sku_id = product.sku_id

        # 获取最新利润分析
        pa_result = await db.execute(
            select(ProfitAnalysis)
            .where(ProfitAnalysis.sku_id == sku_id)
            .order_by(ProfitAnalysis.calc_time.desc())
            .limit(1)
        )
        profit = pa_result.scalar_one_or_none()
        current_roi = float(profit.current_roi) if profit else 0.0

        # 获取未解决的巡检报告
        insp_result = await db.execute(
            select(InspectionReport)
            .where(
                InspectionReport.sku_id == sku_id,
                InspectionReport.is_resolved.is_(False),
            )
            .order_by(InspectionReport.created_at.desc())
            .limit(5)
        )
        inspections = list(insp_result.scalars().all())

        # 计算优先级分数
        priority_score = 0
        urgent_issues: list[str] = []

        for insp in inspections:
            if insp.severity == "critical":
                priority_score += 100
                urgent_issues.append(insp.alert_type)
            elif insp.severity == "warning":
                priority_score += 50
                urgent_issues.append(insp.alert_type)

        # ROI 越低权重越高
        if current_roi < 0:
            priority_score += 80
        elif current_roi < 0.5:
            priority_score += 60
        elif current_roi < 1.0:
            priority_score += 30

        # ROI 健康 + 有巡检建议去加预算也是优先级
        if current_roi > 1.5:
            has_budget_suggestion = any(
                i.alert_type == "budget_suggestion" for i in inspections
            )
            if has_budget_suggestion:
                priority_score += 40

        priority_list.append({
            "sku_id": sku_id,
            "name": product.name,
            "current_roi": round(current_roi, 2),
            "priority_score": priority_score,
            "urgent_issues": urgent_issues,
            "inspection_count": len(inspections),
        })

    # 按优先级降序
    priority_list.sort(key=lambda x: x["priority_score"], reverse=True)
    return priority_list


async def _get_budget_suggestions(
    db: AsyncSession,
) -> list[dict[str, Any]]:
    """获取所有 SKU 的预算调整建议."""
    suggestions: list[dict[str, Any]] = []

    priority_skus = await _get_priority_skus(db)
    for sku in priority_skus:
        roi = sku["current_roi"]
        if roi > 1.5:
            suggestions.append({
                "sku_id": sku["sku_id"],
                "name": sku["name"],
                "action": "increase_budget",
                "reason": f"ROI={roi:.2f}健康，可加预算",
                "priority": (
                    "high"
                    if "budget_suggestion" in sku.get("urgent_issues", [])
                    else "medium"
                ),
            })
        elif roi < 0.5 and roi > 0:
            suggestions.append({
                "sku_id": sku["sku_id"],
                "name": sku["name"],
                "action": "decrease_budget",
                "reason": f"ROI={roi:.2f}偏低，建议控制花费",
                "priority": "medium",
            })

    suggestions.sort(key=lambda s: {"high": 0, "medium": 1, "low": 2}.get(s["priority"], 99))
    return suggestions


async def _get_replace_suggestions(
    db: AsyncSession,
) -> list[dict[str, Any]]:
    """获取换品建议（基于巡检结果）."""
    result = await db.execute(
        select(InspectionReport)
        .where(
            InspectionReport.alert_type == "replace_product",
            InspectionReport.is_resolved.is_(False),
        )
        .order_by(InspectionReport.created_at.desc())
        .limit(10)
    )
    reports = list(result.scalars().all())

    suggestions: list[dict[str, Any]] = []
    for r in reports:
        alternatives = None
        if r.detail_data:
            alternatives = r.detail_data.get("replacement_suggestions")
        suggestions.append({
            "sku_id": r.sku_id,
            "reason": r.reason,
            "suggestion": r.suggestion,
            "alternatives": alternatives,
        })

    return suggestions


def _build_briefing_input(
    priority_skus: list[dict],
    budget_suggestions: list[dict],
    replace_suggestions: list[dict],
) -> str:
    """构建运营日报的输入."""
    lines = ["# 今日运营数据汇总\n"]

    lines.append("## 优先级 SKU")
    for sku in priority_skus[:10]:
        issues = ", ".join(sku["urgent_issues"]) if sku["urgent_issues"] else "无"
        lines.append(
            f"- {sku['name']} (SKU: {sku['sku_id']}) | "
            f"ROI: {sku['current_roi']} | "
            f"紧急问题: {issues}"
        )

    lines.append("\n## 预算调整建议")
    for s in budget_suggestions[:10]:
        lines.append(f"- [{s['priority']}] {s['name']}: {s['reason']}")

    lines.append("\n## 换品建议")
    for s in replace_suggestions[:10]:
        alt_text = ""
        if s.get("alternatives"):
            alt_names = [a.get("name", a["sku_id"]) for a in s["alternatives"]]
            alt_text = f" → 推荐替换: {', '.join(alt_names)}"
        lines.append(f"- {s['sku_id']}: {s['reason']}{alt_text}")

    return "\n".join(lines)


async def generate_daily_briefing(
    db: AsyncSession,
    *,
    use_llm: bool = False,
) -> dict[str, Any]:
    """生成每日运营简报.

    Args:
        db: 数据库会话
        use_llm: 是否使用 LLM 生成自然语言简报（默认使用规则模板）

    Returns:
        {
            "briefing_date": str,
            "priority_skus": [...],
            "budget_suggestions": [...],
            "replace_suggestions": [...],
            "diagnosis": str,       # 自然语言简报
            "summary": {...},       # 汇总指标
        }
    """
    priority_skus = await _get_priority_skus(db)
    budget_suggestions = await _get_budget_suggestions(db)
    replace_suggestions = await _get_replace_suggestions(db)

    # 汇总指标
    total_skus = len(priority_skus)
    critical_count = sum(1 for s in priority_skus if s.get("urgent_issues"))
    roi_healthy = sum(1 for s in priority_skus if s.get("current_roi", 0) > 1.5)
    roi_negative = sum(1 for s in priority_skus if s.get("current_roi", 0) < 0)

    summary = {
        "total_tracked_skus": total_skus,
        "skus_with_critical_issues": critical_count,
        "roi_healthy_skus": roi_healthy,
        "roi_negative_skus": roi_negative,
        "budget_increase_count": sum(
            1 for s in budget_suggestions if s["action"] == "increase_budget"
        ),
        "budget_decrease_count": sum(
            1 for s in budget_suggestions if s["action"] == "decrease_budget"
        ),
        "replace_suggestions_count": len(replace_suggestions),
    }

    # 生成简报
    if use_llm:
        diagnosis = await _llm_briefing(priority_skus, budget_suggestions, replace_suggestions)
    else:
        diagnosis = _template_briefing(
            priority_skus, budget_suggestions, replace_suggestions, summary
        )

    # 持久化到 AIRecommendation 表
    today_date = datetime.now(UTC).strftime("%Y-%m-%d")
    for sku in priority_skus[:5]:
        rec = AIRecommendation(
            sku_id=sku["sku_id"],
            rec_type="priority_sku" if sku.get("urgent_issues") else "diagnosis",
            content={
                "priority_score": sku["priority_score"],
                "current_roi": sku["current_roi"],
                "urgent_issues": sku.get("urgent_issues", []),
            },
            source="ad_expert_agent",
        )
        db.add(rec)

    logger.info(
        "每日运营简报已生成",
        extra={
            "total_skus": total_skus,
            "critical": critical_count,
            "roi_healthy": roi_healthy,
            "roi_negative": roi_negative,
        },
    )

    return {
        "briefing_date": today_date,
        "priority_skus": priority_skus[:10],
        "budget_suggestions": budget_suggestions[:10],
        "replace_suggestions": replace_suggestions[:10],
        "diagnosis": diagnosis,
        "summary": summary,
    }


def _template_briefing(
    priority_skus: list[dict],
    budget_suggestions: list[dict],
    replace_suggestions: list[dict],
    summary: dict,
) -> str:
    """基于模板的自动生成的每日简报."""
    now_str = datetime.now(UTC).strftime("%Y-%m-%d %H:%M")
    lines = ["# 📊 每日运营简报", f"> 生成时间: {now_str} UTC", ""]

    lines.append("## 一、今日概览")
    lines.append(f"- 追踪商品数: {summary['total_tracked_skus']}")
    lines.append(f"- 需紧急处理: {summary['skus_with_critical_issues']} 个")
    lines.append(f"- ROI 健康(>1.5): {summary['roi_healthy_skus']} 个")
    lines.append(f"- ROI 为负: {summary['roi_negative_skus']} 个")
    lines.append("")

    if priority_skus:
        lines.append("## 二、今日优先处理")
        for sku in priority_skus[:5]:
            issues = ", ".join(sku["urgent_issues"]) if sku["urgent_issues"] else "ROI待优化"
            lines.append(f"- **{sku['name']}**: {issues} (ROI={sku['current_roi']})")
        lines.append("")

    if budget_suggestions:
        lines.append("## 三、预算调整")
        for s in budget_suggestions[:5]:
            icon = "↑" if s["action"] == "increase_budget" else "↓"
            lines.append(f"- {icon} **{s['name']}**: {s['reason']}")
        lines.append("")

    if replace_suggestions:
        lines.append("## 四、换品建议")
        for s in replace_suggestions[:5]:
            alt = ""
            if s.get("alternatives"):
                names = [a.get("name", a["sku_id"]) for a in s["alternatives"]]
                alt = f" → 建议替换: {', '.join(names)}"
            lines.append(f"- **{s['sku_id']}**: {s.get('reason', '')}{alt}")
        lines.append("")

    if summary["roi_healthy_skus"] > 0:
        lines.append("## 五、今日可执行操作")
        if budget_suggestions:
            lines.append("- 高 ROI 商品适当增加预算以扩大曝光")
        lines.append("- 检查有紧急问题的 SKU，按巡检建议处理")
        if replace_suggestions:
            lines.append("- 评估换品建议，准备替换低效商品")
        lines.append("")

    return "\n".join(lines)


async def _llm_briefing(
    priority_skus: list[dict],
    budget_suggestions: list[dict],
    replace_suggestions: list[dict],
) -> str:
    """使用 LLM 生成自然语言简报（预留，暂不实现）."""
    try:
        from App.services.ai_client import _call_claude

        input_text = _build_briefing_input(priority_skus, budget_suggestions, replace_suggestions)
        return await _call_claude(
            input_text,
            system_prompt=DAILY_BRIEFING_SYSTEM_PROMPT,
            max_tokens=2048,
            temperature=0.3,
        )
    except Exception as exc:
        logger.warning("LLM 运营简报生成失败，使用模板替代", extra={"error": str(exc)})
        fallback_summary = {
            "total_tracked_skus": len(priority_skus),
            "skus_with_critical_issues": sum(
                1 for s in priority_skus if s.get("urgent_issues")
            ),
            "roi_healthy_skus": sum(
                1 for s in priority_skus if s.get("current_roi", 0) > 1.5
            ),
            "roi_negative_skus": sum(
                1 for s in priority_skus if s.get("current_roi", 0) < 0
            ),
            "budget_increase_count": sum(
                1 for s in budget_suggestions if s["action"] == "increase_budget"
            ),
            "budget_decrease_count": sum(
                1 for s in budget_suggestions if s["action"] == "decrease_budget"
            ),
            "replace_suggestions_count": len(replace_suggestions),
        }
        return _template_briefing(
            priority_skus, budget_suggestions, replace_suggestions, fallback_summary
        )
