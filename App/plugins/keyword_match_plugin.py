"""关键词匹配插件 — 评估关键词适配度并给出关键词策略建议.

课程 id=397: 四种推荐关键词类型（热搜词/高转化词/捡漏词/低成本词）.

根据 match_level 决定:
  - strong: 推荐用于搜索竞价
  - medium: 可用于推广，需持续观测
  - weak: 建议更换关键词
"""

from __future__ import annotations

from typing import Any

from App.plugins.base import PluginBase, PluginMetadata


class KeywordMatchPlugin(PluginBase):
    """关键词匹配插件 — 评估关键词适配度、分类、出建议."""

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="keyword_match_plugin",
            version="1.0.0",
            description="关键词适配度评估与策略建议",
            author="ads_expert",
        )

    async def process(self, db: Any, sku_id: str, context: dict[str, Any]) -> dict[str, Any] | None:
        keyword_matches = context.get("keyword_matches", {})
        match_level = keyword_matches.get("match_level", "medium")

        if match_level == "weak":
            return {
                "decision_type": "no_action",
                "action": None,
                "reasoning": "关键词适配度弱（弱匹配），暂不参与搜索竞价。"
                             "建议更换关键词或优化商品标题使其包含目标关键词。",
                "confidence": 0.90,
                "risk_level": "low",
                "keyword_suggestion": {
                    "action": "replace_keyword",
                    "reason": "weak_match",
                    "suggested_keyword_types": ["hot", "high_conversion"],
                },
                "_plugin": "keyword_match_plugin",
            }

        return None
