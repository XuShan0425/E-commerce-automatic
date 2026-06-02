"""一站推 CPS 插件 — 基于课程知识实现 CPS 模式策略建议.

课程 id=516/517/521:

收费模式:
  - POP品 → 成功加推的下单 GMV
  - 半托品 → 供货价(限时优惠)
  - 计费公式: 推广扣费 = 计费金额基数 × (1 / 设置的 ROI)
  - 归因逻辑: 7 天点击归因

结算:
  - 逐日结算，推广后 2-3 天从回款金自动扣款
  - 欠款达 100 元或累计超 3 天 → 暂停投放

与其它渠道关系: 不互斥，可同时开直通车 + 一站推 + 联盟
"""

from __future__ import annotations

from typing import Any

from App.plugins.base import PluginBase, PluginMetadata


class CpsCampaignPlugin(PluginBase):
    """CPS 推广插件 — 检测是否适合一站式 CPS 投放."""

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="cps_campaign_plugin",
            version="1.0.0",
            description="一站推 CPS 模式适配检测与策略推荐",
            author="ads_expert",
        )

    async def process(self, db: Any, sku_id: str, context: dict[str, Any]) -> dict[str, Any] | None:
        profit = context.get("profit")
        snapshots_7d = context.get("snapshots_7d", [])

        if not profit:
            return None

        current_roi = float(getattr(profit, "current_roi", 0))
        breakeven = float(getattr(profit, "breakeven_ad_spend", 0))

        # 场景: CPC 投放 ROI 偏低 → 推荐 CPS
        if 0 < current_roi < 1.0 and breakeven > 0:
            # CPS 模式: 按成交付费，以 ROI 目标倒推
            # 推荐 ROI 目标 = 当前 ROI × 1.2（略高但可达）
            suggested_roi_target = round(max(current_roi * 1.2, 1.0), 2)
            return {
                "decision_type": "switch_ad_type",
                "action": {
                    "field": "ad_type",
                    "current_value": "standard",
                    "new_value": "cps",
                    "change_pct": 0.0,
                },
                "reasoning": f"当前CPC投放ROI={current_roi:.2f}偏低，建议切换至一站推CPS模式。"
                             f"按成交计费可降低风险，推荐设置ROI目标={suggested_roi_target}。"
                             f"注意: CPS模式下7天点击归因，暂停后仍有归因期费用。",
                "confidence": 0.78,
                "risk_level": "low",
                "_plugin": "cps_campaign_plugin",
                "cps_details": {
                    "suggested_roi_target": suggested_roi_target,
                    "current_roi": round(current_roi, 2),
                    "billing_model": "按成交付费(GMV × 1/ROI)",
                    "attribution_window": "7天点击归因",
                },
            }

        # 场景: 新品/低花费 → CPS 低风险启动
        total_spend = sum(float(s.ad_spend) for s in snapshots_7d)
        if total_spend < 20:
            suggested_roi = 1.5  # 新品建议 ROI 目标 1.5
            return {
                "decision_type": "switch_ad_type",
                "action": {
                    "field": "ad_type",
                    "current_value": "standard",
                    "new_value": "cps",
                    "change_pct": 0.0,
                },
                "reasoning": f"当前广告花费较低（${total_spend:.2f}），建议使用一站推CPS模式。"
                             f"先成交后付费，首单推荐ROI目标={suggested_roi}。"
                             f"注意: 每日预算至少50元，建议连续投放1-2周。",
                "confidence": 0.75,
                "risk_level": "low",
                "_plugin": "cps_campaign_plugin",
                "cps_details": {
                    "suggested_roi_target": suggested_roi,
                    "min_daily_budget": 50,
                    "billing_model": "按成交付费(GMV × 1/ROI)",
                },
            }

        return None
