"""Tests for TASK-003-4 soft boundary checker."""

from __future__ import annotations

from unittest import mock

import pytest

from App.services.boundary_checker import (
    _compute_estimated_traffic_impact,
    _format_snapshots_summary,
    _safe_avg_roi,
    check_soft_boundaries,
    generate_closure_report,
)


class TestHelpers:
    """Tests for private helper functions."""

    def test_safe_avg_roi_empty(self):
        assert _safe_avg_roi(None) == 0.0
        assert _safe_avg_roi([]) == 0.0
        assert _safe_avg_roi("not_a_list") == 0.0

    def test_safe_avg_roi_dict_items(self):
        trend = [{"roi": 1.0}, {"roi": 2.0}, {"roi": 3.0}]
        assert _safe_avg_roi(trend) == 2.0

    def test_safe_avg_roi_scalar_items(self):
        trend = [1.0, 2.0, 3.0]
        assert _safe_avg_roi(trend) == 2.0

    def test_safe_avg_roi_mixed_items(self):
        trend = [{"roi": 1.0}, 2.0, {"roi": 3.0}]
        assert _safe_avg_roi(trend) == 2.0

    def test_format_snapshots_summary_empty(self):
        result = _format_snapshots_summary(None)
        assert result["total_impressions"] == 0
        assert result["total_clicks"] == 0
        assert result["days_of_data"] == 0

    def test_format_snapshots_summary_normal(self):
        snapshots = [
            {"impressions": 100, "clicks": 5, "ctr": 0.05, "orders": 2,
             "conversion_rate": 0.02, "ad_spend": 10.0, "revenue": 50.0},
            {"impressions": 200, "clicks": 8, "ctr": 0.04, "orders": 3,
             "conversion_rate": 0.015, "ad_spend": 15.0, "revenue": 80.0},
        ]
        result = _format_snapshots_summary(snapshots)
        assert result["total_impressions"] == 300
        assert result["total_clicks"] == 13
        assert result["total_orders"] == 5
        assert result["total_ad_spend"] == 25.0
        assert result["total_revenue"] == 130.0
        assert result["days_of_data"] == 2
        assert result["avg_ctr"] == 0.045
        assert result["avg_conversion_rate"] == 0.0175

    def test_compute_traffic_impact_no_trend(self):
        impact = _compute_estimated_traffic_impact({}, {"action": {}})
        assert impact["estimated_traffic_loss_pct"] == 0.50

    def test_compute_traffic_impact_low_roi(self):
        profit = {"roi_7d_trend": [{"roi": 0.3}, {"roi": 0.2}]}
        impact = _compute_estimated_traffic_impact(profit, {"action": {}})
        # avg_roi=0.25 < 0.5 => 30%
        assert impact["estimated_traffic_loss_pct"] == 0.30

    def test_compute_traffic_impact_medium_roi(self):
        profit = {"roi_7d_trend": [{"roi": 0.8}, {"roi": 0.7}]}
        impact = _compute_estimated_traffic_impact(profit, {"action": {}})
        # avg_roi=0.75, 0.5 <= avg_roi < 1.0 => 40%
        assert impact["estimated_traffic_loss_pct"] == 0.40

    def test_compute_traffic_impact_high_roi(self):
        profit = {"roi_7d_trend": [{"roi": 2.5}, {"roi": 3.0}]}
        impact = _compute_estimated_traffic_impact(profit, {"action": {}})
        # avg_roi=2.75 >= 2.0 => 70%
        assert impact["estimated_traffic_loss_pct"] == 0.70


class TestGenerateClosureReport:
    """Tests for generate_closure_report."""

    @pytest.mark.asyncio
    @mock.patch("App.services.boundary_checker.logger")
    async def test_basic_report_structure(self, mock_logger):
        """Verify report has all required sections per CLAUDE.md spec."""
        decision = {
            "decision_type": "stop_ad",
            "reasoning": "广告 ROI 连续下降，建议暂停投放",
            "confidence": 0.85,
            "risk_level": "medium",
            "action": {"field": "ad_type", "current_value": "standard", "new_value": "stopped"},
        }
        snapshots = [
            {"impressions": 100, "clicks": 5, "ctr": 0.05, "orders": 1,
             "conversion_rate": 0.01, "ad_spend": 20.0, "revenue": 30.0},
        ]

        mock_db = mock.AsyncMock()
        report = await generate_closure_report(
            mock_db, "SKU-001", decision, profit=None, snapshots_7d=snapshots,
        )

        # Verify top-level structure
        assert report["sku_id"] == "SKU-001"
        assert report["report_type"] == "campaign_closure"
        assert "generated_at" in report

        # Verify decision summary
        assert report["decision_summary"]["decision_type"] == "stop_ad"
        assert report["decision_summary"]["confidence"] == 0.85

        # 1. 活动的完整数据摘要
        assert "data_summary" in report
        assert report["data_summary"]["total_impressions"] == 100
        assert report["data_summary"]["total_ad_spend"] == 20.0

        # 2. 关闭理由（数据驱动）
        assert "closure_reasons" in report
        assert "广告 ROI 连续下降" in report["closure_reasons"][0]

        # 3. 预计影响（流量减少估算）
        assert "estimated_impact" in report
        assert "estimated_traffic_loss_pct" in report["estimated_impact"]

        # 4. 替代方案建议
        assert "alternatives" in report
        assert len(report["alternatives"]) > 0

    @pytest.mark.asyncio
    @mock.patch("App.services.boundary_checker.logger")
    async def test_report_with_negative_roi_includes_roi_reason(self, mock_logger):
        """When ROI is negative, the report should include that as a closure reason."""
        decision = {
            "decision_type": "stop_ad",
            "reasoning": "",
            "confidence": 0.9,
            "action": {},
        }
        profit = {
            "current_roi": -0.5,
            "gross_margin": 0.15,
            "breakeven_ad_spend": 10.0,
        }

        mock_db = mock.AsyncMock()
        report = await generate_closure_report(
            mock_db, "SKU-002", decision, profit=profit, snapshots_7d=None,
        )

        # Should include ROI-based closure reason
        roi_reasons = [r for r in report["closure_reasons"] if "ROI" in r]
        assert len(roi_reasons) > 0

        # Should include margin-based data
        assert report["profit_data"]["current_roi"] == -0.5

    @pytest.mark.asyncio
    @mock.patch("App.services.boundary_checker.logger")
    async def test_report_empty_reasoning(self, mock_logger):
        """When reasoning is empty, report should still generate reasonable alternatives."""
        decision = {
            "decision_type": "stop_ad",
            "reasoning": "",
            "confidence": 0.7,
            "action": {},
        }

        mock_db = mock.AsyncMock()
        report = await generate_closure_report(
            mock_db, "SKU-003", decision, profit=None, snapshots_7d=None,
        )

        assert len(report["closure_reasons"]) > 0
        assert len(report["alternatives"]) > 0

    @pytest.mark.asyncio
    @mock.patch("App.services.boundary_checker.logger")
    async def test_report_with_negative_margin(self, mock_logger):
        """When gross margin is negative, report should include margin reason."""
        decision = {
            "decision_type": "stop_ad",
            "reasoning": "毛利率为负",
            "confidence": 0.95,
            "action": {},
        }
        profit = {
            "current_roi": 0.5,
            "gross_margin": -0.05,
            "breakeven_ad_spend": 5.0,
        }

        mock_db = mock.AsyncMock()
        report = await generate_closure_report(
            mock_db, "SKU-004", decision, profit=profit, snapshots_7d=None,
        )

        margin_reasons = [r for r in report["closure_reasons"] if "毛利率" in r]
        assert len(margin_reasons) > 0

        alternatives_with_cost = [a for a in report["alternatives"] if "供应链" in a]
        assert len(alternatives_with_cost) > 0


class TestCheckSoftBoundaries:
    """Tests for check_soft_boundaries function."""

    @pytest.mark.asyncio
    @mock.patch("App.services.boundary_checker.logger")
    async def test_stop_ad_triggers_soft_boundary(self, mock_logger):
        """stop_ad decision should trigger soft boundary and generate report."""
        decision = {
            "decision_type": "stop_ad",
            "reasoning": "ROI 太低，建议停止",
            "confidence": 0.8,
            "action": {},
        }

        mock_db = mock.AsyncMock()
        result = await check_soft_boundaries(mock_db, "SKU-001", decision)

        assert result["passed"] is False
        assert result["boundary_type"] == "soft"
        assert "关闭推广活动" in result["reason"]
        assert result["closure_report"] is not None
        assert result["closure_report"]["sku_id"] == "SKU-001"

    @pytest.mark.asyncio
    @mock.patch("App.services.boundary_checker.logger")
    async def test_requires_confirmation_triggers_soft_boundary(self, mock_logger):
        """requires_confirmation decision should trigger soft boundary."""
        decision = {
            "decision_type": "requires_confirmation",
            "reasoning": "建议大幅调整出价策略",
            "confidence": 0.6,
            "risk_level": "high",
            "action": {},
        }

        mock_db = mock.AsyncMock()
        result = await check_soft_boundaries(mock_db, "SKU-002", decision)

        assert result["passed"] is False
        assert result["boundary_type"] == "soft"
        assert "人工确认" in result["reason"]
        # requires_confirmation should NOT generate closure report
        assert result["closure_report"] is None

    @pytest.mark.asyncio
    @mock.patch("App.services.boundary_checker.logger")
    async def test_no_action_passes_soft_boundary(self, mock_logger):
        """no_action decision should pass soft boundary check without report."""
        decision = {
            "decision_type": "no_action",
            "reasoning": "现状良好，无需调整",
            "confidence": 0.9,
            "action": {},
        }

        mock_db = mock.AsyncMock()
        result = await check_soft_boundaries(mock_db, "SKU-003", decision)

        assert result["passed"] is True
        assert result["boundary_type"] is None
        assert result["closure_report"] is None

    @pytest.mark.asyncio
    @mock.patch("App.services.boundary_checker.logger")
    async def test_adjust_bid_passes_soft_boundary(self, mock_logger):
        """adjust_bid decision (without requires_confirmation) should pass."""
        decision = {
            "decision_type": "adjust_bid",
            "reasoning": "建议提高预算",
            "confidence": 0.85,
            "action": {"field": "daily_budget", "current_value": 10.0, "new_value": 12.0},
        }

        mock_db = mock.AsyncMock()
        result = await check_soft_boundaries(mock_db, "SKU-004", decision)

        assert result["passed"] is True
        assert result["boundary_type"] is None


class TestClosureReportIntegration:
    """Integration-style tests: verify report fields match CLAUDE.md spec."""

    CLAUDE_MD_REQUIRED_SECTIONS = [
        "data_summary",
        "closure_reasons",
        "estimated_impact",
        "alternatives",
    ]

    @pytest.mark.asyncio
    @mock.patch("App.services.boundary_checker.logger")
    async def test_report_contains_all_required_sections(self, mock_logger):
        """CLAUDE.md requires: 数据摘要, 关闭理由, 预计影响, 替代方案."""
        decision = {
            "decision_type": "stop_ad",
            "reasoning": "test",
            "confidence": 0.8,
            "action": {},
        }
        snapshots = [
            {"impressions": 500, "clicks": 25, "ctr": 0.05, "orders": 5,
             "conversion_rate": 0.01, "ad_spend": 100.0, "revenue": 200.0},
        ]
        profit = {"current_roi": 0.5, "gross_margin": 0.2}

        mock_db = mock.AsyncMock()
        report = await generate_closure_report(
            mock_db, "SKU-010", decision, profit=profit, snapshots_7d=snapshots,
        )

        for section in self.CLAUDE_MD_REQUIRED_SECTIONS:
            assert section in report, f"Missing required section: {section}"

        # data_summary should have campaign KPIs
        ds = report["data_summary"]
        assert "total_impressions" in ds
        assert "total_clicks" in ds
        assert "total_orders" in ds
        assert "total_ad_spend" in ds
        assert "total_revenue" in ds

        # estimated_impact should have traffic loss
        ei = report["estimated_impact"]
        assert "estimated_traffic_loss_pct" in ei
        assert "explanation" in ei

        # alternatives should be a non-empty list
        assert isinstance(report["alternatives"], list)
        assert len(report["alternatives"]) > 0
