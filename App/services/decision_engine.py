"""AI 决策引擎 — 规则优先，LLM 补充.

升级后架构:
  Step 1: 规则引擎判断（推广评分 / 关键词适配 / ROI阈值 / 出价模式识别）
  Step 2: 规则通过 → 模式匹配 → 生成结构出价建议
  Step 3: LLM 补充分析（仅当规则引擎 confidence < 阈值或需要解释性推理时）

课程知识来源:
  - id=396 自己投（搜索+推荐/出价模式）
  - id=389/390 全店智投（新品孵化/订单最大化/支付金额最大化）
  - id=516/517 一站推（CPS/ROI设置）
  - id=392 冲第一模式
  - id=393 出价智能化（手动/成本控制/跑量优先）
  - id=394 抢位助手Pro
  - id=395 推荐资源位溢价
  - id=397 推广评分体系
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from App.core.logging import get_logger
from App.models.base import AdSnapshot, Product, ProfitAnalysis
from App.services.ai_client import _call_claude
from App.services.feedback_service import format_history_for_prompt
from App.services.promotion_score_engine import compute_promotion_score

logger = get_logger(__name__)

# ── 课程常量 ─────────────────────────────────────────

# 自己投出价模式
BID_MODE_MANUAL = "manual_bid"
BID_MODE_COST_CONTROL = "cost_control"
BID_MODE_VOLUME_FIRST = "volume_first"

# 自己投渠道
CHANNEL_SEARCH = "search_only"
CHANNEL_RECOMMEND = "recommend_only"
CHANNEL_BOTH = "search_recommend"

# 广告产品线
PRODUCT_LINE_ZIJITOU = "zijitou"        # 自己投
PRODUCT_LINE_QUANDIAN = "quandian"       # 全店智投
PRODUCT_LINE_YIZHANTUI = "yizhantui"    # 一站推
PRODUCT_LINE_LIANMENG = "lianmeng"      # 联盟营销

# 全店智投策略组
STRATEGY_NEW_PRODUCT = "new_product_incubation"
STRATEGY_ORDER_MAX = "order_maximization"
STRATEGY_REVENUE_MAX = "revenue_maximization"

# ROI 阈值
ROI_HIGH = 1.5     # > 1.5 → 维持
ROI_MEDIUM = 0.8   # 0.8-1.5 → 优化出价
ROI_LOW = 0.5      # < 0.5 → 检查并调整

# 置信度阈值
CONFIDENCE_THRESHOLD = 0.85  # 规则引擎高于此值不调 LLM

# 有效决策类型（与旧版兼容）
VALID_DECISION_TYPES = {
    "adjust_bid", "adjust_price", "switch_ad_type",
    "stop_ad", "no_action", "requires_confirmation",
}

VALID_RISK_LEVELS = {"low", "medium", "high"}


# ── Step 1: 出价模式检测 ────────────────────────────


def _detect_bid_mode(
    current_roi: float,
    total_ad_spend_7d: float,
    avg_cpc: float | None = None,
    is_new_sku: bool = False,
) -> str:
    """基于课程知识检测适合的出价模式.

    课程 id=393/396:
      - 跑量优先: 大促/流量波动大/新商品/放量阶段
      - 成本控制: ROI优化/稳定期
      - 手动出价: 精细化运营/特定关键词控制

    Returns: "manual_bid" | "cost_control" | "volume_first"
    """
    if is_new_sku or total_ad_spend_7d < 10:
        return BID_MODE_VOLUME_FIRST  # 新品/低花费 → 先跑量

    if current_roi < ROI_MEDIUM:
        return BID_MODE_COST_CONTROL  # ROI不高 → 成本控制

    if current_roi > ROI_HIGH:
        return BID_MODE_VOLUME_FIRST  # ROI健康可跑量

    return BID_MODE_MANUAL


def _detect_campaign_product_line(
    sku_count: int,
    sku_age_days: int | None,
    has_own_bid_history: bool,
) -> str:
    """检测适合的广告产品线.

    课程 id=389/396/516:
      - 自己投: 精细运营/有特定投放需求
      - 全店智投: 全店覆盖/自动化/新品多
      - 一站推: CPS模式/低风险
    """
    if sku_count > 10 and sku_age_days and sku_age_days < 30:
        return PRODUCT_LINE_QUANDIAN  # 多SKU新品 → 全店智投

    if has_own_bid_history:
        return PRODUCT_LINE_ZIJITOU  # 有手动出价历史 → 自己投

    return PRODUCT_LINE_YIZHANTUI  # 默认 → 一站推


def _detect_store_wide_strategy(
    current_roi: float,
    total_orders_7d: int,
    is_new_product: bool = False,
    is_top_seller: bool = False,
) -> str:
    """检测全店智投策略组.

    课程 id=389:
      - 新品孵化: 新品/测试阶段
      - 订单最大化: 潜力品/成长阶段
      - 支付金额最大化: 爆品/高GMV
    """
    if is_new_product:
        return STRATEGY_NEW_PRODUCT
    if is_top_seller or (current_roi > ROI_HIGH and total_orders_7d > 50):
        return STRATEGY_REVENUE_MAX
    return STRATEGY_ORDER_MAX


def _suggest_cpc_bid(
    current_roi: float,
    avg_cpc_7d: float | None,
    breakeven_ad_spend: float,
    bid_mode: str,
) -> float | None:
    """根据出价模式推荐CPC出价.

    - 手动出价: 基于历史CPC × ROI调整系数
    - 成本控制: 基于目标CPC
    - 跑量优先: 不限制CPC
    """
    if bid_mode == BID_MODE_VOLUME_FIRST:
        return None  # 跑量优先不设CPC上限

    if avg_cpc_7d is None:
        return None

    # 成本控制: 如ROI低则降价，ROI高则可加价
    if bid_mode == BID_MODE_COST_CONTROL:
        if current_roi < ROI_MEDIUM:
            return round(avg_cpc_7d * 0.9, 4)  # 降10%
        if current_roi > ROI_HIGH:
            return round(avg_cpc_7d * 1.05, 4)  # 最多加5%
        return round(avg_cpc_7d, 4)

    # 手动出价: 基于ROI微调
    if current_roi < ROI_MEDIUM:
        return round(avg_cpc_7d * 0.95, 4)
    if current_roi > ROI_HIGH:
        return round(avg_cpc_7d * 1.03, 4)
    return round(avg_cpc_7d, 4)


# ── Step 2: 规则引擎决策 ────────────────────────────


async def _rule_based_decision(
    db: AsyncSession,
    sku_id: str,
    cost_price: float,
    current_price: float,
    logistics_cost: float,
    platform_fee_rate: float,
    profit: ProfitAnalysis,
    snapshots_7d: list[AdSnapshot],
    product_category: str | None,
    product_name: str | None,
) -> dict[str, Any]:
    """规则优先决策引擎.

    Returns:
        {"decision": dict, "confidence": float, "applied_rules": list[str]}
        confidence < CONFIDENCE_THRESHOLD 时由 LLM 补充.
    """
    applied_rules: list[str] = []
    current_roi = float(profit.current_roi)
    breakeven = float(profit.breakeven_ad_spend)

    # ── 汇总 7 天数据 ───────────────────────────────
    total_clicks = sum(s.clicks for s in snapshots_7d)
    total_orders = sum(s.orders for s in snapshots_7d)
    total_ad_spend = sum(float(s.ad_spend) for s in snapshots_7d)
    avg_cvr = (total_orders / total_clicks * 100) if total_clicks > 0 else 0.0
    avg_cpc_7d = (total_ad_spend / total_clicks) if total_clicks > 0 else None
    ad_type = snapshots_7d[-1].ad_type if snapshots_7d else "unknown"

    # ── 判断广告产品线 ───────────────────────────────
    campaign_line = _detect_campaign_product_line(
        sku_count=1,
        sku_age_days=None,
        has_own_bid_history=bool(snapshots_7d),
    )

    # ── 出价模式 ────────────────────────────────────
    bid_mode = _detect_bid_mode(
        current_roi, total_ad_spend,
        avg_cpc=avg_cpc_7d,
        is_new_sku=total_ad_spend < 10,
    )

    # ── 规则 1: 检查投放资格（推广评分）────────────────
    # 如果有关键词数据，检查评分
    if product_category and product_name:
        sample_keyword = product_name.split()[:3]
        if sample_keyword:
            kw = " ".join(sample_keyword)
            promo = await compute_promotion_score(db, sku_id, kw, persist=True)
            if promo["score"] < 3:
                applied_rules.append(f"promotion_score_{promo['score']}星")
                return {
                    "decision": {
                        "decision_type": "no_action",
                        "action": {
                            "field": "ad_type",
                            "current_value": ad_type,
                            "new_value": ad_type,
                            "change_pct": 0.0,
                        },
                        "reasoning": f"推广评分 {promo['score']}星（{promo['level']}），"
                                     f"不满足主搜推广位竞价资格（需3星以上）。建议优化商品标题和类目匹配度。",
                        "confidence": 0.95,
                        "risk_level": "low",
                        "_campaign_line": campaign_line,
                        "_bid_mode": bid_mode,
                    },
                    "confidence": 0.95,
                    "applied_rules": applied_rules,
                }

    # ── 规则 2: ROI 连续严重为负 ────────────────────
    roi_trend = profit.roi_7d_trend or []
    if isinstance(roi_trend, list) and len(roi_trend) >= 5:
        negative_days = sum(1 for d in roi_trend
                           if (d.get("roi", 0) if isinstance(d, dict) else 0) < 0)
        if negative_days >= 5:
            applied_rules.append("roi_negative_5d")
            return {
                "decision": {
                    "decision_type": "stop_ad",
                    "action": {
                        "field": "ad_type",
                        "current_value": "enabled",
                        "new_value": "disabled",
                        "change_pct": -1.0,
                    },
                    "reasoning": f"近{len(roi_trend)}天中{negative_days}天ROI为负，"
                                 f"当前ROI={current_roi:.2f}，建议暂停广告止损。",
                    "confidence": 0.95,
                    "risk_level": "high",
                    "_campaign_line": campaign_line,
                    "_bid_mode": bid_mode,
                },
                "confidence": 0.95,
                "applied_rules": applied_rules,
            }

    # ── 规则 3: ROI 健康 → 维持 ─────────────────────
    if current_roi > ROI_HIGH:
        suggested_bid = _suggest_cpc_bid(
            current_roi, avg_cpc_7d, breakeven, bid_mode
        )
        action: dict[str, Any] | None = None
        decision_type = "no_action"

        if suggested_bid and avg_cpc_7d and suggested_bid != round(avg_cpc_7d, 4):
            decision_type = "adjust_bid"
            change_pct = round((suggested_bid - avg_cpc_7d) / avg_cpc_7d, 4) if avg_cpc_7d else 0
            action = {
                "field": "daily_budget" if bid_mode == BID_MODE_VOLUME_FIRST else "cpc",
                "current_value": avg_cpc_7d,
                "new_value": suggested_bid,
                "change_pct": change_pct,
            }

        if decision_type == "no_action" and bid_mode == BID_MODE_VOLUME_FIRST:
            # 跑量优先：维持预算
            pass

        applied_rules.append(f"roi_healthy_{current_roi:.2f}")
        reasoning = (
            f"当前ROI={current_roi:.2f}，高于健康线{ROI_HIGH}，表现良好无需大幅调整。"
            f"建议采用{bind_mode_label(bid_mode)}出价模式。"
            f"{'可适度增加预算扩大曝光。' if bid_mode == BID_MODE_VOLUME_FIRST else ''}"
            f"{'当前CPC合理，维持。' if action is None else f'建议微调CPC至${suggested_bid:.4f}。'}"
        )

        return {
            "decision": {
                "decision_type": decision_type,
                "action": action,
                "reasoning": reasoning,
                "confidence": 0.90,
                "risk_level": "low",
                "_campaign_line": campaign_line,
                "_bid_mode": bid_mode,
            },
            "confidence": 0.90,
            "applied_rules": applied_rules,
        }

    # ── 规则 4: ROI 中等 → 优化出价 ─────────────────
    if current_roi >= ROI_MEDIUM:
        suggested_bid = _suggest_cpc_bid(
            current_roi, avg_cpc_7d, breakeven, bid_mode
        )

        if suggested_bid and avg_cpc_7d:
            change_pct = round((suggested_bid - avg_cpc_7d) / avg_cpc_7d, 4) if avg_cpc_7d else 0
            applied_rules.append(f"roi_medium_{current_roi:.2f}_optimize_bid")
            return {
                "decision": {
                    "decision_type": "adjust_bid",
                    "action": {
                        "field": "cpc",
                        "current_value": avg_cpc_7d,
                        "new_value": suggested_bid,
                        "change_pct": change_pct,
                    },
                    "reasoning": f"当前ROI={current_roi:.2f}，处于优化区间[{ROI_MEDIUM},{ROI_HIGH}]。"
                                 f"建议{bind_mode_label(bid_mode)}出价模式下"
                                 f"{'优化CPC' if change_pct < 0 else '微调CPC'}。"
                                 f"转化率={avg_cvr:.2f}%，建议持续监控。",
                    "confidence": 0.85,
                    "risk_level": "medium" if change_pct < 0 else "low",
                    "_campaign_line": campaign_line,
                    "_bid_mode": bid_mode,
                },
                "confidence": 0.85,
                "applied_rules": applied_rules,
            }

    # ── 规则 5: ROI 较低 → 检查 + 调整 ──────────────
    applied_rules.append(f"roi_low_{current_roi:.2f}")
    if current_roi > 0:
        # ROI 正但低: 降低出价
        if avg_cpc_7d:
            new_cpc = round(avg_cpc_7d * 0.85, 4)
            change_pct = -0.15
            return {
                "decision": {
                    "decision_type": "adjust_bid",
                    "action": {
                        "field": "cpc",
                        "current_value": avg_cpc_7d,
                        "new_value": new_cpc,
                        "change_pct": change_pct,
                    },
                    "reasoning": f"当前ROI={current_roi:.2f}偏低，建议降低CPC至${new_cpc:.4f}"
                                 f"以控制成本。同时检查商品Listing质量（主图/标题/价格）。",
                    "confidence": 0.80,
                    "risk_level": "medium",
                    "_campaign_line": campaign_line,
                    "_bid_mode": BID_MODE_COST_CONTROL,
                },
                "confidence": 0.80,
                "applied_rules": applied_rules,
            }

        # ROI 为 0（无支出但有收入）
        return {
            "decision": {
                "decision_type": "no_action",
                "action": None,
                "reasoning": f"当前ROI={current_roi:.2f}，近7天广告花费=${total_ad_spend:.2f}较低。"
                             f"建议先积累数据再做决策，或考虑切换至{PRODUCT_LINE_YIZHANTUI}CPS模式降低风险。",
                "confidence": 0.75,
                "risk_level": "low",
                "_campaign_line": campaign_line,
                "_bid_mode": bid_mode,
            },
            "confidence": 0.75,
            "applied_rules": applied_rules,
        }

    # ── ROI 为负但不到 stop 阈值 ────────────────────
    if current_roi < -ROI_MEDIUM:
        return {
            "decision": {
                "decision_type": "requires_confirmation",
                "action": {
                    "field": "ad_type",
                    "current_value": ad_type,
                    "new_value": "paused",
                    "change_pct": -1.0,
                },
                "reasoning": f"当前ROI={current_roi:.2f}处于亏损状态，AI建议暂停广告，"
                             f"需要人工确认后执行。请检查商品成本和定价策略。",
                "confidence": 0.85,
                "risk_level": "high",
                "_campaign_line": campaign_line,
                "_bid_mode": bid_mode,
            },
            "confidence": 0.85,
            "applied_rules": applied_rules,
        }

    # ── 默认: 规则无法决定，低置信度 ─────────────────
    return {
        "decision": {
            "decision_type": "no_action",
            "action": None,
            "reasoning": "规则引擎无法确定最优操作，需要LLM补充分析。",
            "confidence": 0.40,
            "risk_level": "medium",
            "_campaign_line": campaign_line,
            "_bid_mode": bid_mode,
        },
        "confidence": 0.40,
        "applied_rules": applied_rules,
    }


# ── Step 3: LLM 补充决策 ───────────────────────────


DECISION_SYSTEM_PROMPT = """\
你是一个速卖通(AliExpress)广告优化专家。规则引擎已经给出了初步分析结果，\
但置信度不够高，需要你结合经验补充分析。

## 你收到的输入

1. 该 SKU 的完整广告数据（同规则引擎的输入）
2. 规则引擎已经用过的规则（避免重复判断）
3. 规则引擎给出的初步建议（供参考）
4. 近 7 天操作历史（反馈闭环）

## 你的任务

验证或调整规则引擎的建议，增加置信度。
如果认可规则引擎的判断，直接确认即可。
如果有不同意见，给出你的建议和理由。

## 决策类型

| 类型 | 适用场景 |
|------|---------|
| adjust_bid | ROI 为正但可优化，调整广告出价/预算 |
| adjust_price | 当前定价不合理，需要调整售价 |
| switch_ad_type | 当前广告类型效果不佳，尝试其他类型 |
| stop_ad | ROI 持续为负，建议暂停广告止损 |
| no_action | 当前表现良好，无需调整 |
| requires_confirmation | 涉及重大操作，需要人工确认后再执行 |

## 出价模式（供你参考）

- manual_bid: 手动出价，精细化控制每次点击出价
- cost_control: 成本控制，设置目标CPC，95%计划在±10%范围
- volume_first: 跑量优先，仅限制总预算，不限制单次点击出价

## 输出格式

严格遵守以下 JSON 格式，不包含其他内容：
{
  "decision_type": "adjust_bid | adjust_price | switch_ad_type | stop_ad | no_action | requires_confirmation",
  "action": {
    "field": "daily_budget | price | cpc | ad_type",
    "current_value": 3.00,
    "new_value": 3.40,
    "change_pct": 0.133
  },
  "reasoning": "用中文简要说明决策理由",
  "confidence": 0.82,
  "risk_level": "low | medium | high"
}
"""


def bind_mode_label(mode: str) -> str:
    """出价模式中文标签."""
    labels = {
        BID_MODE_MANUAL: "手动出价",
        BID_MODE_COST_CONTROL: "成本控制",
        BID_MODE_VOLUME_FIRST: "跑量优先",
    }
    return labels.get(mode, mode)


def product_line_label(line: str) -> str:
    """广告产品线中文标签."""
    labels = {
        PRODUCT_LINE_ZIJITOU: "自己投",
        PRODUCT_LINE_QUANDIAN: "全店智投",
        PRODUCT_LINE_YIZHANTUI: "一站推",
        PRODUCT_LINE_LIANMENG: "联盟营销",
    }
    return labels.get(line, line)


# ── 向后兼容 ──────────────────────────────────────────


def _parse_decision_response(raw: str) -> dict[str, Any]:
    """解析 LLM 返回的决策 JSON（兼容旧版测试和调用方）。

    新版 decision_engine 已使用规则引擎优先策略，此函数保留
    供外部测试和需要直接从 LLM 响应解析的场景使用。
    """
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
        logger.error("决策 JSON 解析失败", extra={"error": str(exc)})
        return {
            "decision_type": "no_action",
            "action": None,
            "reasoning": f"AI 返回无法解析，已回退到 no_action。原始响应: {raw[:200]}",
            "confidence": 0.0,
            "risk_level": "high",
            "parse_error": str(exc),
        }

    if result.get("decision_type") not in VALID_DECISION_TYPES:
        result["decision_type"] = "no_action"
    if result.get("risk_level") not in VALID_RISK_LEVELS:
        result["risk_level"] = "medium"
    result.setdefault("confidence", 0.5)
    result.setdefault("reasoning", "")
    result.setdefault("action", None)

    return result


def _build_input_json(
    sku_id: str,
    cost_price: float,
    current_price: float,
    logistics_cost: float,
    platform_fee_rate: float,
    profit: ProfitAnalysis,
    snapshots_7d: list[AdSnapshot],
    latest_price: float,
    rule_result: dict[str, Any] | None = None,
    decision_history: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """构建 AI 分析输入 JSON."""
    total_impressions = sum(s.impressions for s in snapshots_7d)
    total_clicks = sum(s.clicks for s in snapshots_7d)
    total_orders = sum(s.orders for s in snapshots_7d)
    total_ad_spend = sum(float(s.ad_spend) for s in snapshots_7d)
    total_revenue = sum(float(s.revenue) for s in snapshots_7d)
    avg_ctr = (total_clicks / total_impressions * 100) if total_impressions > 0 else 0.0
    avg_cvr = (total_orders / total_clicks * 100) if total_clicks > 0 else 0.0
    ad_type = snapshots_7d[-1].ad_type if snapshots_7d else "unknown"

    inp = {
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

    if decision_history:
        inp["decision_history"] = decision_history

    if rule_result:
        inp["rule_engine_result"] = {
            "decision": rule_result.get("decision", {}),
            "confidence": rule_result.get("confidence", 0),
            "applied_rules": rule_result.get("applied_rules", []),
        }

    return inp


def _normalize_decision(raw: dict[str, Any], rule_fallback: dict[str, Any]) -> dict[str, Any]:
    """标准化决策输出，确保字段完整性."""
    cleaned = raw if isinstance(raw, dict) else {}

    for key in ("decision_type", "action", "reasoning", "confidence", "risk_level"):
        cleaned.setdefault(key, rule_fallback.get(key))

    if cleaned.get("decision_type") not in VALID_DECISION_TYPES:
        cleaned["decision_type"] = rule_fallback.get("decision_type", "no_action")

    if cleaned.get("risk_level") not in VALID_RISK_LEVELS:
        cleaned["risk_level"] = rule_fallback.get("risk_level", "medium")

    cleaned.setdefault("confidence", 0.5)
    cleaned.setdefault("reasoning", "")
    cleaned.setdefault("action", None)

    return cleaned


async def generate_decision(
    db: AsyncSession,
    sku_id: str,
    cost_price: float,
    current_price: float,
    logistics_cost: float,
    platform_fee_rate: float,
    profit: ProfitAnalysis,
    snapshots_7d: list[AdSnapshot],
    decision_history: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """生成单个 SKU 的广告决策.

    新流程:
      1. 规则引擎优先判断
      2. 置信度高 → 直接返回规则结果
      3. 置信度低 → LLM 以规则结果为上下文做补充分析

    返回格式与旧版兼容:
      {decision_type, action, reasoning, confidence, risk_level}
      额外字段: _campaign_line, _bid_mode (供后续分析使用)
    """
    # 获取商品类别/名称（供规则引擎使用）
    prod_result = await db.execute(select(Product).where(Product.sku_id == sku_id))
    product = prod_result.scalar_one_or_none()
    product_category = product.category if product else None
    product_name = product.name if product else None

    # ── Step 1: 规则引擎 ─────────────────────────────
    rule_result = await _rule_based_decision(
        db, sku_id, cost_price, current_price, logistics_cost,
        platform_fee_rate, profit, snapshots_7d,
        product_category, product_name,
    )

    rule_confidence = rule_result.get("confidence", 0)
    rule_decision = rule_result.get("decision", {})
    applied_rules = rule_result.get("applied_rules", [])

    # ── Step 2: 检查是否需要 LLM 补充 ─────────────────
    decision = rule_decision
    if rule_confidence >= CONFIDENCE_THRESHOLD:
        logger.info(
            "规则引擎决策通过 (confidence=%.2f ≥ %.2f)",
            rule_confidence, CONFIDENCE_THRESHOLD,
            extra={
                "sku_id": sku_id,
                "applied_rules": applied_rules,
                "decision_type": decision.get("decision_type"),
                "bid_mode": decision.get("_bid_mode"),
                "campaign_line": decision.get("_campaign_line"),
            },
        )
    else:
        # ── Step 3: LLM 补充分析 ─────────────────────
        logger.info(
            "规则引擎置信度不足 (confidence=%.2f), 调用 LLM 补充分析",
            rule_confidence,
            extra={"sku_id": sku_id, "applied_rules": applied_rules},
        )

        try:
            input_data = _build_input_json(
                sku_id, cost_price, current_price, logistics_cost,
                platform_fee_rate, profit, snapshots_7d, current_price,
                rule_result=rule_result,
                decision_history=decision_history,
            )

            prompt = json.dumps(input_data, ensure_ascii=False, indent=2)
            if decision_history:
                history_text = format_history_for_prompt(decision_history)
                if history_text:
                    prompt += "\n\n" + history_text

            raw_response = await _call_claude(
                prompt,
                system_prompt=DECISION_SYSTEM_PROMPT,
                max_tokens=2048,
                temperature=0.3,
                sku_id=sku_id,
            )

            try:
                llm_decision = json.loads(raw_response)
            except json.JSONDecodeError:
                llm_decision = rule_decision  # fallback

            decision = _normalize_decision(llm_decision, rule_decision)

            # 保留规则引擎的元数据
            decision["_campaign_line"] = rule_decision.get("_campaign_line")
            decision["_bid_mode"] = rule_decision.get("_bid_mode")
            decision["_applied_rules"] = applied_rules

        except Exception as exc:
            logger.warning(
                "LLM 补充分析失败，使用规则引擎结果",
                extra={"sku_id": sku_id, "error": str(exc)},
            )
            decision = rule_decision

    decision["_generated_at"] = datetime.now(UTC).isoformat()
    decision["_sku_id"] = sku_id

    logger.info(
        "决策完成",
        extra={
            "sku_id": sku_id,
            "decision_type": decision.get("decision_type"),
            "risk_level": decision.get("risk_level"),
            "confidence": decision.get("confidence", 0),
            "bid_mode": decision.get("_bid_mode"),
            "campaign_line": decision.get("_campaign_line"),
            "rule_based": rule_confidence >= CONFIDENCE_THRESHOLD,
        },
    )

    return decision
