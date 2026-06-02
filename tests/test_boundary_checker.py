"""TASK-001-4: 测试 boundary_checker 模块。

测试 check_boundaries 函数在各种边界条件下的行为。
"""

from __future__ import annotations

from unittest import mock

import pytest

from App.services.boundary_checker import BoundaryResult, check_boundaries


def _make_config_result() -> mock.MagicMock:
    """创建返回 None 的 mock 结果（_get_boundary_config 默认值）。"""
    r = mock.MagicMock()
    r.scalar_one_or_none.return_value = None
    return r


def _make_cookie_result(is_valid: bool = True) -> mock.MagicMock:
    """创建 cookie 查询结果 mock。"""
    r = mock.MagicMock()
    r.scalar_one_or_none.return_value = mock.MagicMock(is_valid=is_valid)
    return r


class TestCheckBoundaries:
    """测试 check_boundaries 函数。"""

    @pytest.mark.asyncio
    async def test_passed(self, mock_db, sample_profit_analysis):
        """验证当决策正常时，边界检查通过。"""
        mock_config_result = _make_config_result()
        mock_cookie_result = _make_cookie_result()
        mock_global_stop_result = mock.MagicMock()
        mock_global_stop_result.scalar_one_or_none.return_value = None

        async def execute_side_effect(stmt):
            if "cookie_store" in str(stmt).lower():
                return mock_cookie_result
            return mock_config_result

        mock_db.execute = mock.AsyncMock(side_effect=execute_side_effect)
        with mock.patch(
            "App.services.boundary_checker.is_global_stop_active",
            return_value=False,
        ):
            decision = {
                "decision_type": "adjust_bid",
                "action": {"field": "daily_budget", "current_value": 3.00, "new_value": 3.40},
                "confidence": 0.82,
                "risk_level": "low",
            }
            result = await check_boundaries(mock_db, "test_sku", decision, sample_profit_analysis)

        assert result.passed is True
        assert result.boundary_type is None

    @pytest.mark.asyncio
    async def test_hard_boundary_roi_negative_7d(self, mock_db, negative_roi_analysis):
        """验证 ROI 连续 7 天为负时触发硬边界。"""
        decision = {"decision_type": "no_action", "confidence": 0.5, "risk_level": "low"}

        mock_config_result = _make_config_result()
        mock_cookie_result = _make_cookie_result()

        async def execute_side_effect(stmt):
            if "cookie_store" in str(stmt).lower():
                return mock_cookie_result
            return mock_config_result

        mock_db.execute = mock.AsyncMock(side_effect=execute_side_effect)

        with mock.patch(
            "App.services.boundary_checker.is_global_stop_active",
            return_value=False,
        ):
            result = await check_boundaries(mock_db, "bad_sku", decision, negative_roi_analysis)

        assert result.passed is False
        assert result.boundary_type == "hard"
        assert "ROI 连续" in result.reason

    @pytest.mark.asyncio
    async def test_hard_boundary_budget_exceeded(self, mock_db, sample_profit_analysis):
        """验证日广告花费超出上限时触发硬边界。"""
        mock_config_result = _make_config_result()
        mock_cookie_result = _make_cookie_result()

        async def execute_side_effect(stmt):
            if "cookie_store" in str(stmt).lower():
                return mock_cookie_result
            return mock_config_result

        mock_db.execute = mock.AsyncMock(side_effect=execute_side_effect)

        with mock.patch(
            "App.services.boundary_checker.is_global_stop_active",
            return_value=False,
        ):
            decision = {
                "decision_type": "adjust_bid",
                "action": {
                    "field": "daily_budget",
                    "current_value": 3.00,
                    "new_value": 100.0,
                    "change_pct": 0.5,
                },
                "confidence": 0.7,
                "risk_level": "medium",
            }
            result = await check_boundaries(
                mock_db, "test_sku", decision, sample_profit_analysis
            )

        assert result.passed is False
        assert result.boundary_type == "hard"
        assert "超出上限" in result.reason
        assert result.details.get("new_budget") == 100.0

    @pytest.mark.asyncio
    async def test_hard_boundary_price_change_exceeded(self, mock_db, sample_profit_analysis):
        """验证调价幅度超过 5% 时触发硬边界。"""
        mock_config_result = _make_config_result()
        mock_cookie_result = _make_cookie_result()

        async def execute_side_effect(stmt):
            if "cookie_store" in str(stmt).lower():
                return mock_cookie_result
            return mock_config_result

        mock_db.execute = mock.AsyncMock(side_effect=execute_side_effect)

        with mock.patch(
            "App.services.boundary_checker.is_global_stop_active",
            return_value=False,
        ):
            decision = {
                "decision_type": "adjust_price",
                "action": {
                    "field": "price",
                    "current_value": 10.00,
                    "new_value": 8.00,
                    "change_pct": -0.20,  # 20% 降幅，超过 5%
                },
                "confidence": 0.6,
                "risk_level": "medium",
            }
            result = await check_boundaries(
                mock_db, "test_sku", decision, sample_profit_analysis
            )

        assert result.passed is False
        assert result.boundary_type == "hard"
        assert "超出上限" in result.reason
        assert result.details.get("change_pct") == 0.20

    @pytest.mark.asyncio
    async def test_soft_boundary_stop_ad(self, mock_db, sample_profit_analysis):
        """验证关闭推广活动触发软边界。"""
        mock_config_result = _make_config_result()
        mock_cookie_result = _make_cookie_result()

        async def execute_side_effect(stmt):
            if "cookie_store" in str(stmt).lower():
                return mock_cookie_result
            return mock_config_result

        mock_db.execute = mock.AsyncMock(side_effect=execute_side_effect)

        with mock.patch(
            "App.services.boundary_checker.is_global_stop_active",
            return_value=False,
        ):
            decision = {
                "decision_type": "stop_ad",
                "action": {"field": "daily_budget", "current_value": 5.00, "new_value": 0.00},
                "confidence": 0.9,
                "risk_level": "high",
            }
            result = await check_boundaries(mock_db, "test_sku", decision, sample_profit_analysis)

        assert result.passed is False
        assert result.boundary_type == "soft"
        assert "关闭推广活动" in result.reason

    @pytest.mark.asyncio
    async def test_soft_boundary_requires_confirmation(self, mock_db, sample_profit_analysis):
        """验证 requires_confirmation 触发软边界。"""
        mock_config_result = _make_config_result()
        mock_cookie_result = _make_cookie_result()

        async def execute_side_effect(stmt):
            if "cookie_store" in str(stmt).lower():
                return mock_cookie_result
            return mock_config_result

        mock_db.execute = mock.AsyncMock(side_effect=execute_side_effect)

        with mock.patch(
            "App.services.boundary_checker.is_global_stop_active",
            return_value=False,
        ):
            decision = {
                "decision_type": "requires_confirmation",
                "action": None,
                "confidence": 0.4,
                "risk_level": "high",
            }
            result = await check_boundaries(
                mock_db, "test_sku", decision, sample_profit_analysis
            )

        assert result.passed is False
        assert result.boundary_type == "soft"
        assert "人工确认" in result.reason

    @pytest.mark.asyncio
    async def test_hard_boundary_cookie_missing(self, mock_db, sample_profit_analysis):
        """验证 Cookie 不存在时触发硬边界。"""
        mock_config_result = _make_config_result()
        mock_cookie_result = _make_cookie_result(is_valid=False)
        mock_cookie_result.scalar_one_or_none.return_value = None

        async def execute_side_effect(stmt):
            if "cookie_store" in str(stmt).lower():
                return mock_cookie_result
            return mock_config_result

        mock_db.execute = mock.AsyncMock(side_effect=execute_side_effect)

        decision = {"decision_type": "adjust_bid", "confidence": 0.5, "risk_level": "low"}

        result = await check_boundaries(mock_db, "test_sku", decision, sample_profit_analysis)

        assert result.passed is False
        assert result.boundary_type == "hard"
        assert "Cookie 不存在" in result.reason or "Cookie" in result.reason

    def test_boundary_result_defaults(self):
        """验证 BoundaryResult 的默认值。"""
        result = BoundaryResult(passed=True)
        assert result.passed is True
        assert result.boundary_type is None
        assert result.reason == ""
        assert result.details == {}

        result2 = BoundaryResult(passed=False, boundary_type="hard", reason="test")
        assert result2.passed is False
        assert result2.boundary_type == "hard"
        assert result2.reason == "test"
