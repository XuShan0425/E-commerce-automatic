"""资源位溢价插件 — 基于课程知识实现推荐资源位/抢位助手溢价策略.

课程 id=394 (抢位助手Pro全新升级):
  - APP 推广首位: APP端关键词搜索结果页第一个推广位置
  - PC 推广首位: PC端右侧列第一个
  - APP/PC 推广首页: 搜索结果页第一页推广位置

课程 id=395 (推荐资源位溢价):
  - 分场景溢价: 按类目/ROI/转化率动态推荐溢价倍数

提价警示: 当出价低于竞争对手出价范围时，系统提示
"""

from __future__ import annotations

from typing import Any

from App.plugins.base import PluginBase, PluginMetadata

# 默认资源位溢价系数
_PREMIUM_SEARCH_FIRST = 1.3       # APP/PC 首位溢价
_PREMIUM_SEARCH_PAGE = 1.15       # APP/PC 首页溢价（1-3位）
_PREMIUM_RECOMMENDATION = 1.2     # 推荐资源位溢价


class PremiumSlotPlugin(PluginBase):
    """资源位溢价插件 — 根据 ROI/转化率动态推荐溢价."""

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="premium_slot_plugin",
            version="1.0.0",
            description="资源位溢价倍数推荐 — 抢位助手Pro + 推荐资源位溢价",
            author="ads_expert",
        )

    async def process(self, db: Any, sku_id: str, context: dict[str, Any]) -> dict[str, Any] | None:
        profit = context.get("profit")
        snapshots_7d = context.get("snapshots_7d", [])

        if not profit or not snapshots_7d:
            return None

        current_roi = float(getattr(profit, "current_roi", 0))
        total_clicks = sum(s.clicks for s in snapshots_7d)
        total_orders = sum(s.orders for s in snapshots_7d)
        conversion_rate = total_orders / total_clicks if total_clicks > 0 else 0

        # ── 推荐搜索首位溢价 ─────────────────────────
        if current_roi > 1.5 and conversion_rate > 0.03:
            return {
                "decision_type": "adjust_bid",
                "action": {
                    "field": "search_premium",
                    "current_value": 0.0,
                    "new_value": _PREMIUM_SEARCH_FIRST,
                    "change_pct": _PREMIUM_SEARCH_FIRST - 1.0,
                },
                "reasoning": f"ROI={current_roi:.2f}+转化率={conversion_rate:.2%}双高，"
                             f"建议使用抢位助手Pro，APP/PC首位溢价{_PREMIUM_SEARCH_FIRST:.0%}。"
                             f"注意监控出价是否低于竞争范围。",
                "confidence": 0.85,
                "risk_level": "medium",
                "_plugin": "premium_slot_plugin",
                "premium_details": {
                    "search_first_premium": _PREMIUM_SEARCH_FIRST,
                    "search_page_premium": _PREMIUM_SEARCH_PAGE,
                    "recommendation_premium": _PREMIUM_RECOMMENDATION,
                    "current_roi": round(current_roi, 2),
                    "conversion_rate": round(conversion_rate, 4),
                },
            }

        # ── 推荐资源位溢价 ─────────────────────────
        if current_roi > 1.0 and conversion_rate > 0.02:
            return {
                "decision_type": "adjust_bid",
                "action": {
                    "field": "recommendation_premium",
                    "current_value": 0.0,
                    "new_value": _PREMIUM_RECOMMENDATION,
                    "change_pct": _PREMIUM_RECOMMENDATION - 1.0,
                },
                "reasoning": f"ROI={current_roi:.2f}+转化率={conversion_rate:.2%}表现良好，"
                             f"建议推荐资源位溢价{_PREMIUM_RECOMMENDATION:.0%}获取更多推荐流量。",
                "confidence": 0.80,
                "risk_level": "medium",
                "_plugin": "premium_slot_plugin",
                "premium_details": {
                    "recommendation_premium": _PREMIUM_RECOMMENDATION,
                    "current_roi": round(current_roi, 2),
                    "conversion_rate": round(conversion_rate, 4),
                },
            }

        return None
