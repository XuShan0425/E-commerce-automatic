"""ROI 优化器插件 — 基于速卖通课程知识优化 ROI.

课程 id=393/396: 根据 ROI 水平动态调整出价策略和预算分配.

策略:
  - ROI > 1.5: 跑量优先，可加预算
  - ROI 0.8-1.5: 成本控制，优化 CPC
  - ROI < 0.8: 检查 + 调整策略
  - ROI 连续为负: 建议暂停
"""

from __future__ import annotations

from typing import Any

from App.plugins.base import PluginBase, PluginMetadata


class RoiOptimizerPlugin(PluginBase):
    """ROI 优化器 — 根据 ROI 水平给出出价和预算建议."""

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="roi_optimizer",
            version="1.0.0",
            description="基于 ROI 水平的出价和预算优化建议",
            author="ads_expert",
        )

    async def process(self, db: Any, sku_id: str, context: dict[str, Any]) -> dict[str, Any] | None:
        profit = context.get("profit")
        snapshots_7d = context.get("snapshots_7d", [])
        if not profit or not snapshots_7d:
            return None

        current_roi = float(getattr(profit, "current_roi", 0))
        breakeven = float(getattr(profit, "breakeven_ad_spend", 0))
        total_spend = sum(float(s.ad_spend) for s in snapshots_7d)
        total_clicks = sum(s.clicks for s in snapshots_7d)
        avg_cpc_7d = total_spend / total_clicks if total_clicks > 0 else None

        # ROI > 1.5: 健康，可跑量
        if current_roi > 1.5:
            daily_limit = round(breakeven * 1.5, 2)
            return {
                "decision_type": "adjust_bid",
                "action": {
                    "field": "daily_budget",
                    "current_value": daily_limit,
                    "new_value": round(daily_limit * 1.2, 2),  # +20%
                    "change_pct": 0.20,
                },
                "reasoning": f"ROI={current_roi:.2f}表现健康，建议增加20%预算至"
                             f"${round(daily_limit * 1.2, 2)}以扩大曝光。",
                "confidence": 0.88,
                "risk_level": "low",
                "_plugin": "roi_optimizer",
            }

        # ROI 0.8-1.5: 优化 CPC
        if current_roi >= 0.8 and avg_cpc_7d:
            new_cpc = round(avg_cpc_7d * 0.9, 4)
            return {
                "decision_type": "adjust_bid",
                "action": {
                    "field": "cpc",
                    "current_value": avg_cpc_7d,
                    "new_value": new_cpc,
                    "change_pct": -0.10,
                },
                "reasoning": f"ROI={current_roi:.2f}处于优化区间，建议降低CPC至"
                             f"${new_cpc}以控制成本。",
                "confidence": 0.82,
                "risk_level": "medium",
                "_plugin": "roi_optimizer",
            }

        return None
