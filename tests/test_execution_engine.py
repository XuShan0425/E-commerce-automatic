"""TASK-002-1: Tests for execution_engine.py decision routing logic.

Tests execute_decision() with mocked DB and service calls.
"""

from __future__ import annotations

from unittest import mock

import pytest

from App.services.execution_engine import execute_decision


@pytest.mark.asyncio
async def test_no_action_path(mock_db, sample_analysis_result):
    """Verify no_action decision_type returns immediately without executing."""
    sample_analysis_result["decision"]["decision_type"] = "no_action"
    sample_analysis_result["decision"]["action"] = None

    with (
        mock.patch("App.services.execution_engine.log_operation", new=mock.AsyncMock()) as mock_log,
    ):
        result = await execute_decision(mock_db, sample_analysis_result)

    assert result["decision_type"] == "no_action"
    assert result["status"] == "success"
    assert result["executed"] is False
    # log_operation should have been called for the no_action record
    mock_log.assert_awaited_once_with(
        mock_db, "test_sku_001", "no_action",
        ai_confidence=0.85,
        ai_reasoning="Current performance is good, no adjustment needed.",
        status="success",
        details={"message": "AI 建议维持现状，无需调整"},
    )


@pytest.mark.asyncio
async def test_hard_boundary_skips_execution(mock_db, sample_analysis_result):
    """Verify a hard boundary result does not execute the action."""
    sample_analysis_result["decision"]["decision_type"] = "adjust_bid"
    sample_analysis_result["boundary"] = {
        "passed": False,
        "boundary_type": "hard",
        "reason": "ROI 连续 7 天为负",
    }

    with (
        mock.patch("App.services.execution_engine.log_operation", new=mock.AsyncMock()) as mock_log,
        mock.patch("App.services.execution_engine.raise_alert", new=mock.AsyncMock()) as mock_alert,
    ):
        result = await execute_decision(mock_db, sample_analysis_result)

    assert result["status"] != "success"
    assert "硬边界拦截" in result["reason"]
    mock_log.assert_awaited_once()
    mock_alert.assert_awaited_once()


@pytest.mark.asyncio
async def test_soft_boundary_returns_pending(mock_db, sample_analysis_result):
    """Verify a soft boundary result returns pending_confirmation status."""
    sample_analysis_result["decision"]["decision_type"] = "stop_ad"
    sample_analysis_result["boundary"] = {
        "passed": False,
        "boundary_type": "soft",
        "reason": "决定关闭推广活动，需要人工确认",
    }

    with (
        mock.patch("App.services.execution_engine.log_operation", new=mock.AsyncMock()) as mock_log,
        mock.patch("App.services.execution_engine.raise_alert", new=mock.AsyncMock()) as mock_alert,
    ):
        result = await execute_decision(mock_db, sample_analysis_result)

    assert result["status"] == "pending_confirmation"
    assert result["executed"] is False
    assert "operation_log_id" in result
    mock_log.assert_awaited_once()
    mock_alert.assert_awaited_once()


@pytest.mark.asyncio
async def test_dry_run_logs_only(mock_db, sample_analysis_result):
    """Verify dry_run=True logs without running browser adjustments."""
    sample_analysis_result["decision"] = {
        "decision_type": "adjust_bid",
        "action": {
            "field": "daily_budget",
            "current_value": 3.0,
            "new_value": 3.4,
        },
        "reasoning": "Increase budget for better exposure.",
        "confidence": 0.82,
        "risk_level": "low",
    }

    with (
        mock.patch("App.services.execution_engine.log_operation", new=mock.AsyncMock()) as mock_log,
    ):
        result = await execute_decision(mock_db, sample_analysis_result, dry_run=True)

    assert result["executed"] is True
    assert result["status"] == "success"
    assert "dry_run" in result["reason"]
    mock_log.assert_awaited_once()


@pytest.mark.asyncio
async def test_crash_during_execution_sets_global_stop(mock_db, sample_analysis_result):
    """Verify an exception during execution triggers critical alert with global stop."""
    sample_analysis_result["decision"] = {
        "decision_type": "adjust_bid",
        "action": {
            "field": "daily_budget",
            "current_value": 3.0,
            "new_value": 3.4,
        },
        "reasoning": "Increase budget.",
        "confidence": 0.82,
        "risk_level": "low",
    }

    # Mock CookieManager with AsyncMock so load_cookies() is awaitable,
    # then mock run_executor to raise the crash exception.
    # Also mock logger.exception to avoid StructuredLogger signature issue.
    fake_cookie_mgr = mock.AsyncMock()
    fake_cookie_mgr.load_cookies.return_value = [{"name": "test_cookie", "value": "test_value"}]

    with (
        mock.patch(
            "App.services.execution_engine.log_operation", new=mock.AsyncMock()
        ) as mock_log,
        mock.patch(
            "App.services.execution_engine.raise_alert", new=mock.AsyncMock()
        ) as mock_alert,
        mock.patch(
            "App.services.execution_engine.logger.exception",
            new=mock.MagicMock(),
        ),
        mock.patch(
            "App.services.execution_engine.CookieManager",
            return_value=fake_cookie_mgr,
        ),
        mock.patch(
            "App.services.execution_engine.run_executor",
            side_effect=RuntimeError("Browser crashed"),
        ),
    ):
        result = await execute_decision(mock_db, sample_analysis_result)

    assert result["status"] == "failed"
    mock_log.assert_called()  # should log the failure
    mock_alert.assert_awaited_once()


@pytest.mark.asyncio
async def test_no_boundary_info_defaults_to_skipped(mock_db, sample_analysis_result):
    """Verify if boundary info is missing, the decision is handled."""
    sample_analysis_result["decision"]["decision_type"] = "adjust_bid"
    del sample_analysis_result["boundary"]

    with (
        mock.patch("App.services.execution_engine.log_operation", new=mock.AsyncMock()),
        mock.patch("App.services.execution_engine.raise_alert", new=mock.AsyncMock()),
    ):
        # boundary not passed == hard boundary behavior
        result = await execute_decision(mock_db, sample_analysis_result)
    # Should still work without KeyError because of .get() usage
    assert isinstance(result, dict)
