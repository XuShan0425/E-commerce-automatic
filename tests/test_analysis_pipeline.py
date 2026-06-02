"""TASK-002-1: Tests for analysis_pipeline.py error handling paths.

Tests analyze_single_sku() with mocked DB for error scenarios.
"""

from __future__ import annotations

from unittest import mock

import pytest

from App.services.analysis_pipeline import analyze_single_sku


@pytest.mark.asyncio
async def test_sku_not_found(mock_db):
    """Verify that a non-existent SKU returns an error result."""
    # Mock _get_product to return None (SKU not found).
    # Mock logger.exception to avoid StructuredLogger signature issue.
    with (
        mock.patch(
            "App.services.analysis_pipeline._get_product",
            new=mock.AsyncMock(return_value=None),
        ),
        mock.patch(
            "App.services.analysis_pipeline.logger.exception",
            new=mock.MagicMock(),
        ),
    ):
        result = await analyze_single_sku(mock_db, "non_existent_sku")

    assert result["success"] is False
    assert result["error"] is not None
    assert "不存在" in result["error"]
    assert result["profit"] is None
    assert result["decision"] is None


@pytest.mark.asyncio
async def test_profit_calculation_failure(mock_db):
    """Verify profit calculation error is caught and reported."""
    # Mock _get_product to return a fake product (SKU found),
    # and mock compute_profit to raise an error.
    fake_product = mock.MagicMock(sku_id="test_sku", cost_price=5.0, category="Electronics")

    with (
        mock.patch(
            "App.services.analysis_pipeline._get_product",
            new=mock.AsyncMock(return_value=fake_product),
        ),
        mock.patch(
            "App.services.analysis_pipeline.compute_profit",
            new=mock.AsyncMock(side_effect=ValueError("DB connection lost")),
        ),
        mock.patch(
            "App.services.analysis_pipeline.logger.exception",
            new=mock.MagicMock(),
        ),
    ):
        result = await analyze_single_sku(mock_db, "test_sku")

    assert result["success"] is False
    assert result["error"] is not None
    assert "利润计算失败" in result["error"]


@pytest.mark.asyncio
async def test_ai_decision_value_error_fallback(mock_db):
    """Verify ValueError from AI (e.g. missing API key) returns safe fallback."""
    fake_product = mock.MagicMock(sku_id="test_sku", cost_price=5.0, category="Electronics")
    fake_profit = mock.MagicMock(
        id=1, logistics_cost=2.5, platform_fee=0.6,
        true_cost=8.1, gross_margin=0.325,
        breakeven_ad_spend=3.9, current_roi=2.5, roi_7d_trend=[],
    )

    with (
        mock.patch(
            "App.services.analysis_pipeline._get_product",
            new=mock.AsyncMock(return_value=fake_product),
        ),
        mock.patch(
            "App.services.analysis_pipeline.compute_profit",
            new=mock.AsyncMock(return_value=fake_profit),
        ),
        mock.patch(
            "App.services.analysis_pipeline._get_ad_snapshots_7d",
            new=mock.AsyncMock(return_value=[]),
        ),
        mock.patch(
            "App.services.analysis_pipeline._get_platform_fee_rate",
            new=mock.AsyncMock(return_value=0.05),
        ),
        mock.patch(
            "App.services.analysis_pipeline.generate_decision",
            new=mock.AsyncMock(side_effect=ValueError("LLM_API_KEY not configured")),
        ),
    ):
        # Configure scalar_one_or_none with MagicMock so it doesn't return a coroutine
        mock_db.execute.return_value.scalar_one_or_none = mock.MagicMock(return_value=12.0)
        result = await analyze_single_sku(mock_db, "test_sku")

    assert result["success"] is True  # profit was computed
    assert result["decision"]["decision_type"] == "no_action"
    assert "API key" in result["decision"]["reasoning"]
    assert result["boundary"]["passed"] is True


@pytest.mark.asyncio
async def test_ai_decision_generic_exception_fallback(mock_db):
    """Verify generic AI exception returns hard boundary fallback."""
    fake_product = mock.MagicMock(sku_id="test_sku", cost_price=5.0, category="Electronics")
    fake_profit = mock.MagicMock(
        id=1, logistics_cost=2.5, platform_fee=0.6,
        true_cost=8.1, gross_margin=0.325,
        breakeven_ad_spend=3.9, current_roi=2.5, roi_7d_trend=[],
    )

    with (
        mock.patch(
            "App.services.analysis_pipeline._get_product",
            new=mock.AsyncMock(return_value=fake_product),
        ),
        mock.patch(
            "App.services.analysis_pipeline.compute_profit",
            new=mock.AsyncMock(return_value=fake_profit),
        ),
        mock.patch(
            "App.services.analysis_pipeline._get_ad_snapshots_7d",
            new=mock.AsyncMock(return_value=[]),
        ),
        mock.patch(
            "App.services.analysis_pipeline._get_platform_fee_rate",
            new=mock.AsyncMock(return_value=0.05),
        ),
        mock.patch(
            "App.services.analysis_pipeline.generate_decision",
            new=mock.AsyncMock(side_effect=RuntimeError("API timeout")),
        ),
    ):
        mock_db.execute.return_value.scalar_one_or_none = mock.MagicMock(return_value=12.0)
        result = await analyze_single_sku(mock_db, "test_sku")

    assert result["success"] is True  # profit was computed
    assert result["decision"]["decision_type"] == "no_action"
    assert result["boundary"]["passed"] is False
    assert result["boundary"]["boundary_type"] == "hard"


@pytest.mark.asyncio
async def test_skip_ai_returns_immediately(mock_db):
    """Verify skip_ai=True bypasses AI and boundary checks."""
    fake_product = mock.MagicMock(sku_id="test_sku", cost_price=5.0, category="Electronics")
    fake_profit = mock.MagicMock(
        id=1, logistics_cost=2.5, platform_fee=0.6,
        true_cost=8.1, gross_margin=0.325,
        breakeven_ad_spend=3.9, current_roi=2.5, roi_7d_trend=[],
    )

    with (
        mock.patch(
            "App.services.analysis_pipeline._get_product",
            new=mock.AsyncMock(return_value=fake_product),
        ),
        mock.patch(
            "App.services.analysis_pipeline.compute_profit",
            new=mock.AsyncMock(return_value=fake_profit),
        ),
    ):
        result = await analyze_single_sku(mock_db, "test_sku", skip_ai=True)

    assert result["success"] is True
    assert result["decision"]["decision_type"] == "no_action"
    assert "skip_ai" in result["decision"]["reasoning"].lower()
    assert result["boundary"]["passed"] is True
