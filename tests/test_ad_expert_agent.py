"""Tests for ad_expert_agent.py — 广告专家 Agent."""
from __future__ import annotations

from App.services.ad_expert_agent import (
    _template_briefing,
)


def _make_priority_sku(sku_id="SKU001", name="Test Product", roi=1.2,
                       urgent_issues=None, priority_score=50):
    return {
        "sku_id": sku_id,
        "name": name,
        "current_roi": roi,
        "priority_score": priority_score,
        "urgent_issues": urgent_issues or [],
        "inspection_count": len(urgent_issues or []),
    }


class TestTemplateBriefing:
    def test_basic_briefing_output(self):
        priority = [_make_priority_sku(roi=-0.5, urgent_issues=["roi_anomaly"])]
        budget = []
        replace = []
        summary = {
            "total_tracked_skus": 1,
            "skus_with_critical_issues": 1,
            "roi_healthy_skus": 0,
            "roi_negative_skus": 1,
            "budget_increase_count": 0,
            "budget_decrease_count": 0,
            "replace_suggestions_count": 0,
        }
        result = _template_briefing(priority, budget, replace, summary)
        assert "ROI=-0.5" in result or "roi" in result.lower()
        assert "今日概览" in result

    def test_empty_priority_no_error(self):
        result = _template_briefing([], [], [], {
            "total_tracked_skus": 0,
            "skus_with_critical_issues": 0,
            "roi_healthy_skus": 0,
            "roi_negative_skus": 0,
            "budget_increase_count": 0,
            "budget_decrease_count": 0,
            "replace_suggestions_count": 0,
        })
        assert isinstance(result, str)
        assert len(result) > 0

    def test_budget_suggestions_included(self):
        priority = [_make_priority_sku(roi=2.0)]
        budget = [{
            "sku_id": "SKU001", "name": "Test", "action": "increase_budget",
            "reason": "ROI=2.00健康", "priority": "high",
        }]
        result = _template_briefing(priority, budget, [], {
            "total_tracked_skus": 1,
            "skus_with_critical_issues": 0,
            "roi_healthy_skus": 1,
            "roi_negative_skus": 0,
            "budget_increase_count": 1,
            "budget_decrease_count": 0,
            "replace_suggestions_count": 0,
        })
        assert "increase_budget" in result or "预算" in result
