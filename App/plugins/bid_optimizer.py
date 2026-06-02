"""出价优化器插件 — 基于关键词推广评分和历史 CPC 推荐出价.

课程 id=393/397: 利用推广评分和关键词表现数据，推荐最优出价.

策略:
  - 五星词: 可用更高出价获取首位
  - 四星词: 中等出价，稳定获取流量
  - 三星词: 保守出价，测试效果
  - 二星以下: 不竞价，先优化商品
"""

from __future__ import annotations

from typing import Any

from App.plugins.base import PluginBase, PluginMetadata


class BidOptimizerPlugin(PluginBase):
    """出价优化器 — 基于推广评分和历史 CPC 推荐最优出价."""

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="bid_optimizer",
            version="1.0.0",
            description="基于推广评分和历史 CPC 的关键词出价优化",
            author="ads_expert",
        )

    async def process(self, db: Any, sku_id: str, context: dict[str, Any]) -> dict[str, Any] | None:
        snapshots_7d = context.get("snapshots_7d", [])
        profit = context.get("profit")
        if not snapshots_7d:
            return None

        current_roi = float(getattr(profit, "current_roi", 0)) if profit else 0
        total_spend = sum(float(s.ad_spend) for s in snapshots_7d)
        total_clicks = sum(s.clicks for s in snapshots_7d)
        avg_cpc_7d = total_spend / total_clicks if total_clicks > 0 else 0.2

        # 五星词策略（推广评分 5）
        promotion_score = context.get("promotion_scores", {}).get("score", 3)
        keyword_match = context.get("keyword_matches", {}).get("match_level", "medium")

        if promotion_score == 5 and keyword_match == "strong":
            # 五星强匹配词: 出价上浮
            new_cpc = round(avg_cpc_7d * 1.15, 4)
            return {
                "decision_type": "adjust_bid",
                "action": {
                    "field": "cpc",
                    "current_value": avg_cpc_7d,
                    "new_value": new_cpc,
                    "change_pct": 0.15,
                },
                "reasoning": f"五星词+强匹配，建议CPC上浮15%至${new_cpc}"
                             f"以提升竞得率。",
                "confidence": 0.85,
                "risk_level": "low" if current_roi > 1.0 else "medium",
                "_plugin": "bid_optimizer",
            }

        # 四星词策略
        if promotion_score == 4:
            if current_roi > 1.0:
                new_cpc = round(avg_cpc_7d * 1.05, 4)
                return {
                    "decision_type": "adjust_bid",
                    "action": {
                        "field": "cpc",
                        "current_value": avg_cpc_7d,
                        "new_value": new_cpc,
                        "change_pct": 0.05,
                    },
                    "reasoning": f"四星词+ROI健康，建议CPC微调至${new_cpc}。",
                    "confidence": 0.80,
                    "risk_level": "low",
                    "_plugin": "bid_optimizer",
                }

        # 三星词: 保守出价
        if promotion_score == 3:
            if current_roi < 0.8:
                new_cpc = round(avg_cpc_7d * 0.85, 4)
                return {
                    "decision_type": "adjust_bid",
                    "action": {
                        "field": "cpc",
                        "current_value": avg_cpc_7d,
                        "new_value": new_cpc,
                        "change_pct": -0.15,
                    },
                    "reasoning": f"三星词+ROI偏低，建议CPC降至${new_cpc}测试效果。",
                    "confidence": 0.75,
                    "risk_level": "medium",
                    "_plugin": "bid_optimizer",
                }

        return None
