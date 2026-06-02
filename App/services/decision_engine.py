"""AI 决策引擎 — 构建 prompt → 调用 LLM → 解析广告决策."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from App.core.logging import get_logger
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from App.models.base import AdSnapshot, PriceSnapshot, ProfitAnalysis
from App.services.ai_client import _call_claude

logger = get_logger(__name__)

DECISION_SYSTEM_PROMPT = """\
你是一个速卖通(AliExpress)广告优化专家。你会收到单个 SKU 的完整数据，
需要根据数据给出最优的广告决策。

## 决策类型

| 类型 | 适用场景 |
|------|---------|
| adjust_bid | ROI 为正但可优化，调整广告出价/预算 |
| adjust_price | 当前定价不合理，需要调整售价 |
| switch_ad_type | 当前广告类型效果不佳，尝试其他类型 |
| stop_ad | ROI 持续为负，建议暂停广告止损 |
| no_action | 当前表现良好，无需调整 |
| requires_confirmation | 涉及重大操作，需要人工确认后再执行 |

## 约束条件

- 单次调价幅度不能超过 5%
- 调价频率为 24 小时最多一次
- 日广告花费上限 = 盈亏平衡广告花费 × 150%
- 如果 ROI 连续 7 天为负，必须 stop_ad
- 如果当前 ROI > 1.5，不建议大幅调整

## 风险等级判断

- low: 小幅度优化，几乎无风险
- medium: 有明确数据支撑的调整
- high: 数据不充分或影响较大

## 输出格式

严格输出以下 JSON 格式，不要包含任何其他内容：
{
  "decision_type": "adjust_bid | adjust_price | switch_ad_type | stop_ad | no_action | requires_confirmation",
  "action": {
    "field": "daily_budget | price | ad_type",
    "current_value": 3.00,
    "new_value": 3.40,
    "change_pct": 0.133
  },
  "reasoning": "用中文简要说明决策理由，引用关键数据",
  "confidence": 0.82,
  "risk_level": "low | medium | high"
}
"""


def _build_input_json(
    sku_id: str,
    cost_price: float,
    current_price: float,
    logistics_cost: float,
    platform_fee_rate: float,
    profit: ProfitAnalysis,
    snapshots_7d: list[AdSnapshot],
    latest_price: float,
) -> dict[str, Any]:
    """构建 AI 分析输入 JSON（符合 CLAUDE.md 规范）。"""
    # 汇总 7 天广告数据摘要
    total_impressions = sum(s.impressions for s in snapshots_7d)
    total_clicks = sum(s.clicks for s in snapshots_7d)
    total_orders = sum(s.orders for s in snapshots_7d)
    total_ad_spend = sum(float(s.ad_spend) for s in snapshots_7d)
    total_revenue = sum(float(s.revenue) for s in snapshots_7d)
    avg_ctr = (total_clicks / total_impressions * 100) if total_impressions > 0 else 0.0
    avg_cvr = (total_orders / total_clicks * 100) if total_clicks > 0 else 0.0

    # 广告类型（取最近一次的快照类型）
    ad_type = snapshots_7d[-1].ad_type if snapshots_7d else "unknown"

    return {
        "sku_id": sku_id,
        "cost_price": cost_price,
        "current_price": current_price,
        "logistics_cost_weighted": round(logistics_cost, 2),
        "platform_fee_rate": round(platform_fee_rate, 4),
        "profit_summary": {
            "true_cost": float(profit.true_cost),
            "gross_margin": float(profit.gross_margin),
            "breakeven_ad_spend": float(profit.breakeven_ad_spend),
            "current_roi": float(profit.current_roi),
        },
        "ad_performance_7d": {
            "impressions": total_impressions,
            "clicks": total_clicks,
            "orders": total_orders,
            "avg_ctr_pct": round(avg_ctr, 2),
            "avg_cvr_pct": round(avg_cvr, 2),
            "total_ad_spend": round(total_ad_spend, 2),
            "total_revenue": round(total_revenue, 2),
            "snapshot_count": len(snapshots_7d),
        },
        "current_ad_type": ad_type,
        "roi_7d_trend": profit.roi_7d_trend or [],
        "constraints": {
            "max_daily_ad_spend": round(float(profit.breakeven_ad_spend) * 1.5, 2),
            "max_price_change_pct": 0.05,
            "price_change_cooldown_hours": 24,
        },
    }


def _parse_decision_response(raw: str) -> dict[str, Any]:
    """解析 LLM 返回的决策 JSON。"""
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        first_nl = cleaned.find("\n")
        if first_nl != -1:
            cleaned = cleaned[first_nl + 1:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
    cleaned = cleaned.strip()

    try:
        result = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        logger.error("决策 JSON 解析失败: %s", exc)
        logger.debug("原始响应: %s", raw)
        # 返回一个安全的 fallback
        return {
            "decision_type": "no_action",
            "action": None,
            "reasoning": f"AI 返回无法解析，已回退到 no_action。原始响应: {raw[:200]}",
            "confidence": 0.0,
            "risk_level": "high",
            "parse_error": str(exc),
        }

    # 规范化字段
    valid_types = {"adjust_bid", "adjust_price", "switch_ad_type", "stop_ad", "no_action", "requires_confirmation"}
    if result.get("decision_type") not in valid_types:
        result["decision_type"] = "no_action"

    valid_risks = {"low", "medium", "high"}
    if result.get("risk_level") not in valid_risks:
        result["risk_level"] = "medium"

    result.setdefault("confidence", 0.5)
    result.setdefault("reasoning", "")
    result.setdefault("action", None)

    return result


async def generate_decision(
    db: AsyncSession,
    sku_id: str,
    cost_price: float,
    current_price: float,
    logistics_cost: float,
    platform_fee_rate: float,
    profit: ProfitAnalysis,
    snapshots_7d: list[AdSnapshot],
) -> dict[str, Any]:
    """生成单个 SKU 的广告决策。

    Args:
        db: 数据库会话
        sku_id: 商品 SKU ID
        cost_price: 成本价
        current_price: 当前售价
        logistics_cost: 加权物流成本
        platform_fee_rate: 平台佣金费率
        profit: 已计算的 ProfitAnalysis 记录
        snapshots_7d: 近 7 天广告快照

    Returns:
         决策 dict，包含 decision_type / action / reasoning / confidence / risk_level
    """

    input_data = _build_input_json(
        sku_id, cost_price, current_price, logistics_cost,
        platform_fee_rate, profit, snapshots_7d, current_price,
    )

    prompt = json.dumps(input_data, ensure_ascii=False, indent=2)

    logger.info("正在为 SKU '%s' 生成广告决策...", sku_id)
    raw_response = await _call_claude(
        prompt,
        system_prompt=DECISION_SYSTEM_PROMPT,
        max_tokens=2048,
        temperature=0.3,
        sku_id=sku_id,
    )

    decision = _parse_decision_response(raw_response)
    decision["_generated_at"] = datetime.now(timezone.utc).isoformat()
    decision["_sku_id"] = sku_id

    logger.info(
        "决策完成: SKU=%s type=%s risk=%s confidence=%.2f",
        sku_id, decision.get("decision_type"),
        decision.get("risk_level"), decision.get("confidence", 0),
    )

    return decision
