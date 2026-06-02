"""TASK-001-4: 测试 decision_engine 模块。

测试 _build_input_json 和 _parse_decision_response 函数。
"""

from __future__ import annotations

import json

from App.services.decision_engine import _build_input_json, _parse_decision_response


class TestBuildInputJson:
    """测试 _build_input_json 函数。"""

    def test_basic_structure(self, sample_profit_analysis, sample_ad_snapshots):
        """验证生成的输入 JSON 包含所有必要字段。"""
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

        # 顶层字段
        assert result["sku_id"] == "test_sku_001"
        assert result["cost_price"] == 5.00
        assert result["current_price"] == 12.00
        assert result["logistics_cost_weighted"] == 2.50
        assert result["platform_fee_rate"] == 0.05

        # profit_summary
        ps = result["profit_summary"]
        assert "true_cost" in ps
        assert "gross_margin" in ps
        assert "breakeven_ad_spend" in ps
        assert "current_roi" in ps

        # ad_performance_7d
        ap = result["ad_performance_7d"]
        assert ap["impressions"] == 3600  # 1200 + 1100 + 1300
        assert ap["clicks"] == 180
        assert ap["orders"] == 18
        assert "total_ad_spend" in ap
        assert "total_revenue" in ap
        assert ap["snapshot_count"] == 3

        # constraints
        constraints = result["constraints"]
        assert constraints["max_price_change_pct"] == 0.05
        assert constraints["price_change_cooldown_hours"] == 24
        expected_max_spend = round(float(sample_profit_analysis.breakeven_ad_spend) * 1.5, 2)
        assert constraints["max_daily_ad_spend"] == expected_max_spend

        # 其他字段
        assert result["current_ad_type"] == "standard"
        assert result["roi_7d_trend"] == sample_profit_analysis.roi_7d_trend

    def test_empty_snapshots(self, sample_profit_analysis):
        """测试无广告快照时的边界情况。"""
        result = _build_input_json(
            sku_id="empty_sku",
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

    def test_all_field_types(self, sample_profit_analysis, sample_ad_snapshots):
        """验证所有字段类型正确。"""
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

        # sku_id 必须为字符串
        assert isinstance(result["sku_id"], str)
        # cost_price 必须为数字
        assert isinstance(result["cost_price"], (int, float))
        # ad_performance 内的计数为整数
        assert isinstance(result["ad_performance_7d"]["impressions"], int)
        # 约束条件
        assert isinstance(result["constraints"]["max_price_change_pct"], float)


class TestParseDecisionResponse:
    """测试 _parse_decision_response 函数。"""

    def test_parse_valid_json(self):
        """验证能正确解析合法的 JSON 响应。"""
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
        assert result["action"]["current_value"] == 3.00
        assert result["action"]["new_value"] == 3.40
        assert result["action"]["change_pct"] == 0.133
        assert result["confidence"] == 0.82
        assert result["risk_level"] == "low"
        assert "近7天" in result["reasoning"]

    def test_parse_with_codeblock(self):
        """验证能正确解析带 ```json 包裹的响应。"""
        raw = """```json
{
    "decision_type": "no_action",
    "action": null,
    "reasoning": "当前表现良好，无需调整",
    "confidence": 0.95,
    "risk_level": "low"
}
```"""
        result = _parse_decision_response(raw)
        assert result["decision_type"] == "no_action"
        assert result["action"] is None
        assert result["confidence"] == 0.95
        assert result["risk_level"] == "low"

    def test_parse_malformed_json(self):
        """验证解析损坏的 JSON 时返回安全的 fallback。"""
        raw = "这不是 JSON{invalid"
        result = _parse_decision_response(raw)

        assert result["decision_type"] == "no_action"
        assert result["confidence"] == 0.0
        assert result["risk_level"] == "high"
        assert result["action"] is None
        assert "parse_error" in result

    def test_parse_invalid_decision_type(self):
        """验证不合法的 decision_type 会被修正为 no_action。"""
        raw = json.dumps({
            "decision_type": "invalid_type_xyz",
            "confidence": 0.5,
            "risk_level": "medium",
        })
        result = _parse_decision_response(raw)
        assert result["decision_type"] == "no_action"

    def test_parse_invalid_risk_level(self):
        """验证不合法的 risk_level 会被修正为 medium。"""
        raw = json.dumps({
            "decision_type": "no_action",
            "confidence": 0.5,
            "risk_level": "extreme",
        })
        result = _parse_decision_response(raw)
        assert result["risk_level"] == "medium"

    def test_parse_all_decision_types(self):
        """验证所有合法的 decision_type 都能被正确识别。"""
        valid_types = [
            "adjust_bid", "adjust_price", "switch_ad_type",
            "stop_ad", "no_action", "requires_confirmation",
        ]
        for dt in valid_types:
            raw = json.dumps({"decision_type": dt, "confidence": 0.5, "risk_level": "low"})
            result = _parse_decision_response(raw)
            assert result["decision_type"] == dt

    def test_parse_all_risk_levels(self):
        """验证所有合法的 risk_level 都能被正确识别。"""
        for rl in ["low", "medium", "high"]:
            raw = json.dumps({"decision_type": "no_action", "confidence": 0.5, "risk_level": rl})
            result = _parse_decision_response(raw)
            assert result["risk_level"] == rl

    def test_parse_missing_fields_defaults(self):
        """验证缺少字段时会使用默认值。"""
        raw = json.dumps({"decision_type": "adjust_bid"})
        result = _parse_decision_response(raw)
        assert result["decision_type"] == "adjust_bid"
        assert result["confidence"] == 0.5  # 默认值
        assert result["reasoning"] == ""  # 默认值
        assert result["risk_level"] == "medium"  # 默认值
        assert result["action"] is None  # 默认值

    def test_parse_with_stop_ad_decision(self):
        """验证 stop_ad 类型的决策解析。"""
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
