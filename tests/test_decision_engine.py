"""Tests for decision_engine.py — _build_input_json and _parse_decision_response.

Tests _build_input_json() and _parse_decision_response() — no DB dependency.
"""

from __future__ import annotations

import json

from App.services.decision_engine import _build_input_json, _parse_decision_response


class TestBuildInputJson:
    """Tests for _build_input_json."""

    def test_basic_structure(self, sample_profit_analysis, sample_ad_snapshots):
        """Verify the output dict has all required keys."""
        result = _build_input_json(
            sku_id="test_sku_001",
            cost_price=5.00,
            current_price=12.00,
            logistics_cost=2.50,
            platform_fee_rate=0.05,
            profit=sample_profit_analysis,
            snapshots_7d=sample_ad_snapshots,
            latest_price=12.00,
        )

        assert result["sku_id"] == "test_sku_001"
        assert result["cost_price"] == 5.00
        assert result["current_price"] == 12.00
        assert result["logistics_cost_weighted"] == 2.50
        assert result["platform_fee_rate"] == 0.05

        # profit_summary
        ps = result["profit_summary"]
        assert ps["true_cost"] == 8.10
        assert ps["gross_margin"] == 0.325
        assert ps["breakeven_ad_spend"] == 3.90
        assert ps["current_roi"] == 2.5

        # ad_performance_7d
        ap = result["ad_performance_7d"]
        assert ap["impressions"] == 3600  # 1200+1100+1300
        assert ap["clicks"] == 180  # 60+55+65
        assert ap["orders"] == 18  # 6+5+7
        assert ap["snapshot_count"] == 3
        assert ap["total_ad_spend"] == 75.0  # 25+22+28
        assert ap["total_revenue"] == 440.0  # 150+130+160

        # constraints
        cons = result["constraints"]
        assert cons["max_price_change_pct"] == 0.05
        assert cons["price_change_cooldown_hours"] == 24
        assert cons["max_daily_ad_spend"] == 5.85  # 3.90 * 1.5

    def test_empty_snapshots(self, sample_profit_analysis):
        """Verify empty snapshots produce safe defaults."""
        result = _build_input_json(
            sku_id="test_sku_001",
            cost_price=5.00,
            current_price=12.00,
            logistics_cost=2.50,
            platform_fee_rate=0.05,
            profit=sample_profit_analysis,
            snapshots_7d=[],
            latest_price=12.00,
        )

        ap = result["ad_performance_7d"]
        assert ap["impressions"] == 0
        assert ap["clicks"] == 0
        assert ap["orders"] == 0
        assert ap["avg_ctr_pct"] == 0.0
        assert ap["avg_cvr_pct"] == 0.0
        assert ap["snapshot_count"] == 0
        assert result["current_ad_type"] == "unknown"

    def test_correct_ad_type_from_latest_snapshot(
        self, sample_ad_snapshots, sample_profit_analysis,
    ):
        """Verify ad_type is taken from the last snapshot."""
        sample_ad_snapshots[-1].ad_type = "promotion"
        result = _build_input_json(
            sku_id="x", cost_price=1, current_price=2,
            logistics_cost=0.5, platform_fee_rate=0.05,
            profit=sample_profit_analysis,
            snapshots_7d=sample_ad_snapshots,
            latest_price=2,
        )
        assert result["current_ad_type"] == "promotion"

    def test_all_field_types(self, sample_profit_analysis, sample_ad_snapshots):
        """Verify all field types are correct."""
        result = _build_input_json(
            sku_id="type_test",
            cost_price=5.00,
            current_price=12.00,
            logistics_cost=2.50,
            platform_fee_rate=0.05,
            profit=sample_profit_analysis,
            snapshots_7d=sample_ad_snapshots,
            latest_price=12.00,
        )

        assert isinstance(result["sku_id"], str)
        assert isinstance(result["cost_price"], (int, float))
        assert isinstance(result["ad_performance_7d"]["impressions"], int)
        assert isinstance(result["constraints"]["max_price_change_pct"], float)


class TestParseDecisionResponse:
    """Tests for _parse_decision_response."""

    def test_valid_json(self):
        """Verify valid JSON is parsed correctly."""
        raw = json.dumps({
            "decision_type": "adjust_bid",
            "action": {
                "field": "daily_budget",
                "current_value": 3.00,
                "new_value": 3.40,
                "change_pct": 0.133,
            },
            "reasoning": "近7天点击率上升，建议提升预算",
            "confidence": 0.82,
            "risk_level": "low",
        })
        result = _parse_decision_response(raw)

        assert result["decision_type"] == "adjust_bid"
        assert result["action"]["field"] == "daily_budget"
        assert result["confidence"] == 0.82
        assert result["risk_level"] == "low"
        assert "近7天" in result["reasoning"]

    def test_markdown_wrapped_json(self):
        """Verify markdown code block wrapping is stripped."""
        raw = "```json\n{\"decision_type\": \"no_action\", \"confidence\": 0.9, \"risk_level\": \"low\"}\n```"
        result = _parse_decision_response(raw)
        assert result["decision_type"] == "no_action"
        assert result["confidence"] == 0.9

    def test_malformed_json_returns_fallback(self):
        """Verify malformed JSON returns a safe fallback no_action."""
        raw = "this is not json at all"
        result = _parse_decision_response(raw)
        assert result["decision_type"] == "no_action"
        assert result["confidence"] == 0.0
        assert result["risk_level"] == "high"
        assert "parse_error" in result
        assert result["action"] is None

    def test_invalid_decision_type_normalized(self):
        """Verify an unrecognized decision_type is normalized to no_action."""
        raw = json.dumps({"decision_type": "invalid_type_xyz", "confidence": 0.5, "risk_level": "medium"})
        result = _parse_decision_response(raw)
        assert result["decision_type"] == "no_action"

    def test_invalid_risk_level_normalized(self):
        """Verify an unrecognized risk_level is normalized to 'medium'."""
        raw = json.dumps({"decision_type": "no_action", "confidence": 0.5, "risk_level": "extreme"})
        result = _parse_decision_response(raw)
        assert result["risk_level"] == "medium"

    def test_all_valid_decision_types(self):
        """Verify all valid decision_types are recognized."""
        valid_types = [
            "adjust_bid", "adjust_price", "switch_ad_type",
            "stop_ad", "no_action", "requires_confirmation",
        ]
        for dt in valid_types:
            raw = json.dumps({"decision_type": dt, "confidence": 0.5, "risk_level": "low"})
            result = _parse_decision_response(raw)
            assert result["decision_type"] == dt

    def test_all_valid_risk_levels(self):
        """Verify all valid risk_levels are recognized."""
        for rl in ["low", "medium", "high"]:
            raw = json.dumps({"decision_type": "no_action", "confidence": 0.5, "risk_level": rl})
            result = _parse_decision_response(raw)
            assert result["risk_level"] == rl

    def test_missing_fields_get_defaults(self):
        """Verify missing optional fields get sensible defaults."""
        raw = json.dumps({"decision_type": "adjust_price"})
        result = _parse_decision_response(raw)
        assert result["decision_type"] == "adjust_price"
        assert result["confidence"] == 0.5
        assert result["reasoning"] == ""
        assert result["action"] is None
        assert result["risk_level"] == "medium"

    def test_extra_whitespace_handling(self):
        """Verify leading/trailing whitespace is stripped."""
        raw = '  \n  {"decision_type": "switch_ad_type", "confidence": 0.6, "risk_level": "high"}  \n'
        result = _parse_decision_response(raw)
        assert result["decision_type"] == "switch_ad_type"
        assert result["confidence"] == 0.6

    def test_stop_ad_decision(self):
        """Verify stop_ad decision with full action details."""
        raw = json.dumps({
            "decision_type": "stop_ad",
            "action": {
                "field": "daily_budget",
                "current_value": 5.00,
                "new_value": 0.00,
                "change_pct": -1.0,
            },
            "reasoning": "ROI 持续为负，建议暂停广告止损",
            "confidence": 0.90,
            "risk_level": "high",
        })
        result = _parse_decision_response(raw)
        assert result["decision_type"] == "stop_ad"
        assert result["action"]["new_value"] == 0.0
        assert result["action"]["change_pct"] == -1.0
        assert result["risk_level"] == "high"
