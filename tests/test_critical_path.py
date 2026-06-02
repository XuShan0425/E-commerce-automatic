"""Critical path smoke test — simulate 1 SKU full pipeline.

Tests the integrated flow from data acquisition (mocked) through profit
calculation, AI decision input assembly, boundary checking, and result
validation. Designed to run in both Docker and non-Docker environments
without requiring a real database or Claude API key.

Pipeline under test:
  mock data -> profit_calculator.compute_profit (mocked DB queries)
           -> decision_engine._build_input_json
           -> decision_engine._parse_decision_response
           -> boundary_checker.check_boundaries (mocked DB queries)
           -> assert all results are non-zero / structurally valid

Verification:
  python -m pytest tests/test_critical_path.py -x -q
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from unittest import mock

import pytest

from App.models.base import AdSnapshot, Product, ProfitAnalysis
from App.services.boundary_checker import check_boundaries
from App.services.decision_engine import _build_input_json, _parse_decision_response
from App.services.profit_calculator import _compute_roi_7d_trend, compute_profit
from App.services.analysis_pipeline import analyze_single_sku


# ==============================================================
# Fixtures
# ==============================================================


@pytest.fixture
def mock_product() -> Product:
    return Product(
        sku_id="TEST-001",
        name="Smoke Test SKU",
        cost_price=10.00,
        category="Electronics",
    )


@pytest.fixture
def mock_snapshots() -> list[AdSnapshot]:
    now = datetime.now(timezone.utc)
    return [
        AdSnapshot(
            sku_id="TEST-001",
            snapshot_time=now - timedelta(days=i),
            impressions=1000,
            clicks=50 + i * 2,
            ctr=0.05 + i * 0.001,
            orders=5 + i,
            conversion_rate=0.1,
            ad_spend=25.00 + i * 0.5,
            revenue=100.00 + i * 5,
            ad_type="standard",
            buyer_region_breakdown={"US": 0.6, "EU": 0.4},
        )
        for i in range(7)
    ]


@pytest.fixture
def mock_profit() -> ProfitAnalysis:
    obj = ProfitAnalysis(
        sku_id="TEST-001",
        calc_time=datetime.now(timezone.utc),
        logistics_cost=2.50,
        platform_fee=0.50,
        true_cost=13.00,
        gross_margin=0.35,
        breakeven_ad_spend=4.00,
        current_roi=2.5,
        roi_7d_trend=[
            {"date": "2026-05-25", "revenue": 100, "ad_spend": 40, "roi": 2.5},
        ],
    )
    obj.id = 1
    return obj


# ==============================================================
# Pure-function tests (no DB, no AI key)
# ==============================================================


class TestDecisionEnginePure:
    """Pure functions in decision_engine that transform data structures."""

    def test_build_input_json_returns_valid_structure(
        self,
        mock_profit: ProfitAnalysis,
        mock_snapshots: list[AdSnapshot],
    ) -> None:
        """_build_input_json should return a dict matching the CLAUDE.md input spec."""
        result = _build_input_json(
            sku_id="TEST-001",
            cost_price=10.00,
            current_price=15.00,
            logistics_cost=2.50,
            platform_fee_rate=0.05,
            profit=mock_profit,
            snapshots_7d=mock_snapshots,
            latest_price=15.00,
        )

        assert result["sku_id"] == "TEST-001"
        assert result["cost_price"] == 10.00
        assert result["current_price"] == 15.00
        assert result["logistics_cost_weighted"] == 2.50
        assert result["platform_fee_rate"] == 0.05

        # Constraints match CLAUDE.md spec
        c = result["constraints"]
        assert c["max_price_change_pct"] == 0.05
        assert c["price_change_cooldown_hours"] == 24

        # Profit summary values are non-zero
        ps = result["profit_summary"]
        assert ps["true_cost"] > 0
        assert ps["gross_margin"] > 0
        assert ps["breakeven_ad_spend"] > 0
        assert ps["current_roi"] > 0

        # Ad performance summary is populated
        ap = result["ad_performance_7d"]
        assert ap["impressions"] > 0
        assert ap["clicks"] > 0
        assert ap["orders"] > 0
        assert ap["total_ad_spend"] > 0
        assert ap["total_revenue"] > 0

    def test_parse_decision_response_valid_json(self) -> None:
        """A well-formed AI response should parse correctly."""
        raw = json.dumps({
            "decision_type": "adjust_bid",
            "action": {
                "field": "daily_budget",
                "current_value": 5.0,
                "new_value": 6.0,
                "change_pct": 0.2,
            },
            "reasoning": "ROI positive, increase budget",
            "confidence": 0.85,
            "risk_level": "low",
        })
        result = _parse_decision_response(raw)
        assert result["decision_type"] == "adjust_bid"
        assert result["confidence"] > 0
        assert result["risk_level"] == "low"

    def test_parse_decision_response_invalid_json(self) -> None:
        """Unparseable AI response should fall back to no_action."""
        result = _parse_decision_response("not valid json {{{")
        assert result["decision_type"] == "no_action"
        assert result["confidence"] == 0.0
        assert "parse_error" in result

    def test_parse_decision_response_markdown_wrapped(self) -> None:
        """AI responses with ```json fences should still parse."""
        inner = json.dumps({
            "decision_type": "adjust_price",
            "action": {
                "field": "price",
                "current_value": 15.0,
                "new_value": 14.5,
                "change_pct": -0.033,
            },
            "reasoning": "降价提升竞争力",
            "confidence": 0.72,
            "risk_level": "medium",
        })
        raw = f"```json\n{inner}\n```"
        result = _parse_decision_response(raw)
        assert result["decision_type"] == "adjust_price"
        assert result["confidence"] > 0

    def test_compute_roi_7d_trend_populated(
        self,
        mock_snapshots: list[AdSnapshot],
    ) -> None:
        """ROI trend should have one entry per unique day."""
        trend = _compute_roi_7d_trend(mock_snapshots)
        assert len(trend) > 0
        for entry in trend:
            assert "date" in entry
            assert "roi" in entry
            assert entry["revenue"] >= 0
            assert entry["ad_spend"] >= 0

    def test_compute_roi_7d_trend_empty(self) -> None:
        """Empty snapshot list should produce empty trend."""
        assert _compute_roi_7d_trend([]) == []


# ==============================================================
# Profit-calculator test (mocked DB queries)
# ==============================================================


@pytest.mark.asyncio
async def test_compute_profit_returns_non_zero(
    mock_product: Product,
    mock_snapshots: list[AdSnapshot],
) -> None:
    """Profit calculator produces non-zero values when DB helpers return mock data."""
    patches = {
        "_get_product": mock_product,
        "_get_latest_price": 15.00,
        "_get_platform_fee_rate": 0.05,
        "_get_ad_snapshots_7d": mock_snapshots,
        "_compute_logistics_cost": 2.50,
    }

    with mock.patch.multiple(
        "App.services.profit_calculator",
        **{k: mock.AsyncMock(return_value=v) for k, v in patches.items()},
    ):
        mock_db = mock.AsyncMock()
        mock_db.add = mock.MagicMock()
        mock_db.flush = mock.AsyncMock()

        async def _refresh(obj: object) -> None:
            obj.id = 42  # type: ignore[attr-defined]

        mock_db.refresh = mock.AsyncMock(side_effect=_refresh)

        profit = await compute_profit(mock_db, "TEST-001")

        assert profit is not None
        assert profit.id == 42
        # Core financial metrics are non-zero
        assert float(profit.true_cost) > 0
        assert float(profit.gross_margin) > 0
        assert float(profit.current_roi) > 0
        assert float(profit.breakeven_ad_spend) > 0


# ==============================================================
# Boundary-checker tests (mocked DB queries)
# ==============================================================


@pytest.mark.asyncio
async def test_boundary_checker_passes_healthy_sku() -> None:
    """Boundary check passes when cookie is valid and ROI is positive."""
    profit = ProfitAnalysis(
        sku_id="TEST-001",
        calc_time=datetime.now(timezone.utc),
        logistics_cost=2.50,
        platform_fee=0.50,
        true_cost=13.00,
        gross_margin=0.35,
        breakeven_ad_spend=4.00,
        current_roi=2.5,
        roi_7d_trend=[{"date": "2026-05-25", "revenue": 100, "ad_spend": 40, "roi": 2.5}],
    )

    decision = {
        "decision_type": "adjust_bid",
        "action": {
            "field": "daily_budget",
            "current_value": 3.0,
            "new_value": 3.5,
            "change_pct": 0.167,
        },
        "reasoning": "Test",
        "confidence": 0.8,
        "risk_level": "low",
    }

    with mock.patch(
        "App.services.boundary_checker.is_global_stop_active",
        return_value=False,
    ):
        mock_db = mock.AsyncMock()
        config_result = mock.MagicMock()
        config_result.scalar_one_or_none.return_value = None
        valid_cookie = mock.MagicMock()
        valid_cookie.is_valid = True
        cookie_result = mock.MagicMock()
        cookie_result.scalar_one_or_none.return_value = valid_cookie

        async def exec_side_effect(stmt):
            if "cookie_store" in str(stmt).lower():
                return cookie_result
            return config_result

        mock_db.execute = mock.AsyncMock(side_effect=exec_side_effect)

        result = await check_boundaries(mock_db, "TEST-001", decision, profit)

        assert result.passed is True
        assert result.boundary_type is None


@pytest.mark.asyncio
async def test_boundary_checker_blocks_stop_ad() -> None:
    """A stop_ad decision triggers a soft boundary (requires confirmation)."""
    profit = ProfitAnalysis(
        sku_id="TEST-001",
        calc_time=datetime.now(timezone.utc),
        logistics_cost=2.50,
        platform_fee=0.50,
        true_cost=13.00,
        gross_margin=0.35,
        breakeven_ad_spend=4.00,
        current_roi=-0.5,
        roi_7d_trend=[{"date": "2026-05-25", "revenue": 10, "ad_spend": 20, "roi": -0.5}],
    )

    decision = {
        "decision_type": "stop_ad",
        "action": None,
        "reasoning": "ROI negative for 7 days",
        "confidence": 0.9,
        "risk_level": "medium",
    }

    with mock.patch(
        "App.services.boundary_checker.is_global_stop_active",
        return_value=False,
    ):
        mock_db = mock.AsyncMock()
        config_result = mock.MagicMock()
        config_result.scalar_one_or_none.return_value = None
        valid_cookie = mock.MagicMock()
        valid_cookie.is_valid = True
        cookie_result = mock.MagicMock()
        cookie_result.scalar_one_or_none.return_value = valid_cookie

        async def exec_side_effect(stmt):
            if "cookie_store" in str(stmt).lower():
                return cookie_result
            return config_result

        mock_db.execute = mock.AsyncMock(side_effect=exec_side_effect)

        result = await check_boundaries(mock_db, "TEST-001", decision, profit)

        assert result.passed is False
        assert result.boundary_type == "soft"
        assert "关闭推广活动" in result.reason


# ==============================================================
# Full pipeline integration test
# ==============================================================


@pytest.mark.asyncio
async def test_analyze_single_sku_produces_non_zero(
    mock_product: Product,
    mock_profit: ProfitAnalysis,
) -> None:
    """Full pipeline (skip_ai=True) produces non-zero profit results."""
    with (
        mock.patch(
            "App.services.analysis_pipeline._get_product",
            return_value=mock_product,
        ),
        mock.patch(
            "App.services.analysis_pipeline.compute_profit",
            return_value=mock_profit,
        ),
    ):
        mock_db = mock.AsyncMock()
        result = await analyze_single_sku(mock_db, "TEST-001", skip_ai=True)

        assert result["success"] is True
        assert result["error"] is None

        profit = result["profit"]
        assert profit is not None
        assert profit["true_cost"] > 0
        assert profit["gross_margin"] > 0
        assert profit["current_roi"] > 0
        assert profit["breakeven_ad_spend"] > 0
        assert profit["logistics_cost"] >= 0
        assert profit["platform_fee"] >= 0

        decision = result["decision"]
        assert decision["decision_type"] == "no_action"

        boundary = result["boundary"]
        assert boundary["passed"] is True
