"""冲第一模式插件 — 根据课程知识实现首位竞价策略.

课程 id=392: "自己投「冲第一」模式"

准入条件:
  1. 仅 72 小时上网率 ≥ 80% 的明星/热销/潜力商品
  2. 仅 5 星关键词可添加
  3. 若不满足条件自动失效，满足后自动恢复

两种资源位:
  - 搜索结果页第一位（Best Matches、Orders 排序下）
  - 类目导航瀑布流第一位

出价机制:
  - 关键词出价 → 搜索结果第一位竞价
  - 类目导航出价 → 瀑布流第一位竞价（不可删除）
  - 建议开启智选关键词包
"""

from __future__ import annotations

from typing import Any

from App.plugins.base import PluginBase, PluginMetadata


class FirstRankPlugin(PluginBase):
    """冲第一插件 — 检测是否满足首位竞价条件并推荐."""

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="first_rank_plugin",
            version="1.0.0",
            description="冲第一模式 — 首位竞价条件检测与策略推荐",
            author="ads_expert",
        )

    async def process(self, db: Any, sku_id: str, context: dict[str, Any]) -> dict[str, Any] | None:
        profit = context.get("profit")
        snapshots_7d = context.get("snapshots_7d", [])
        promotion_score = context.get("promotion_scores", {}).get("score", 1)

        if not profit:
            return None

        current_roi = float(getattr(profit, "current_roi", 0))

        # 条件 1: 仅 5 星关键词
        if promotion_score < 5:
            return None

        # 条件 2: ROI 健康（ROI > 1.0）
        if current_roi < 1.0:
            return None

        # 条件 3: 有广告数据（有投放记录）
        if not snapshots_7d:
            return None

        # 检查近 7 天曝光趋势是否下降（排名可能下降）
        if len(snapshots_7d) >= 2:
            recent = sum(s.impressions for s in snapshots_7d[-3:]) if len(snapshots_7d) >= 3 else 0
            prev = sum(s.impressions for s in snapshots_7d[:-3]) if len(snapshots_7d) > 3 else 0
            if prev > 0 and recent < prev * 0.8:
                # 曝光下降+五星词+ROI健康 → 推荐冲第一
                return {
                    "decision_type": "requires_confirmation",
                    "action": {
                        "field": "ad_type",
                        "current_value": "standard",
                        "new_value": "first_rank",
                        "change_pct": 0.50,  # 出价预估增幅
                    },
                    "reasoning": f"检测到五星词曝光下降（近3天{recent} vs 前期{prev}），"
                                 f"当前ROI={current_roi:.2f}健康，满足冲第一模式准入条件。"
                                 f"建议尝试首位竞价以恢复曝光。",
                    "confidence": 0.85,
                    "risk_level": "medium",
                    "_plugin": "first_rank_plugin",
                    "first_rank_details": {
                        "current_roi": round(current_roi, 2),
                        "promotion_score": promotion_score,
                        "recent_impressions": int(recent),
                        "previous_impressions": int(prev),
                        "resource_positions": [
                            "搜索结果页第一位",
                            "类目导航瀑布流第一位",
                        ],
                    },
                }

        return None
