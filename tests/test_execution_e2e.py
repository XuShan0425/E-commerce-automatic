"""E2E 自动化测试 — 验证 1 SKU 的完整执行循环。

测试覆盖:
  决策摄取 → 边界检查 → Playwright 操作 → 操作日志写入全流程。

依赖 mock 避免真实数据库/AI/浏览器调用，聚焦管线编排逻辑。
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest import mock

import pytest

from App.models.operation_log import OperationLog
from App.services.analysis_pipeline import analyze_single_sku

# ── 被测试模块 ──────────────────────────────────────
from App.services.execution_engine import (
    confirm_pending,
    execute_all_passed,
    execute_decision,
    reject_pending,
)
from App.services.operation_logger import (
    get_logs,
    get_pending_operations,
    log_operation,
    update_log_status,
)

# ═══════════════════════════════════════════════════════
#  Fixtures
# ═══════════════════════════════════════════════════════


@pytest.fixture
def mock_db():
    """AsyncSession mock with commonly needed methods."""
    db = mock.AsyncMock()
    db.add = mock.AsyncMock()
    db.flush = mock.AsyncMock()
    db.refresh = mock.AsyncMock()
    db.get = mock.AsyncMock()
    db.execute = mock.AsyncMock()
    db.commit = mock.AsyncMock()
    db.rollback = mock.AsyncMock()
    return db


@pytest.fixture
def mock_op_log():
    """Minimal OperationLog mock."""
    log = mock.MagicMock(spec=OperationLog)
    log.id = 42
    log.sku_id = "TEST-SKU-001"
    log.operation_type = "adjust_bid"
    log.field_name = "daily_budget"
    log.old_value = 3.00
    log.new_value = 3.40
    log.ai_confidence = 0.82
    log.ai_reasoning = "近 7 天点击率上升 12%，建议小幅提升预算"
    log.status = "success"
    log.executed_at = datetime.now(UTC)
    log.details = {}
    return log


@pytest.fixture
def mock_profit():
    """ProfitAnalysis fields as a plain dict."""
    return {
        "id": 1,
        "cost_price": 5.00,
        "logistics_cost": 2.30,
        "platform_fee": 0.60,
        "true_cost": 7.90,
        "gross_margin": 0.3417,
        "breakeven_ad_spend": 3.20,
        "current_roi": 1.85,
        "roi_7d_trend": [
            {"date": "2026-05-26", "roi": 1.2},
            {"date": "2026-05-27", "roi": 1.5},
            {"date": "2026-05-28", "roi": 1.8},
            {"date": "2026-05-29", "roi": 2.0},
            {"date": "2026-05-30", "roi": 1.9},
            {"date": "2026-05-31", "roi": 2.1},
            {"date": "2026-06-01", "roi": 2.2},
        ],
    }


@pytest.fixture
def analysis_passed(mock_profit):
    """Analysis result: adjust_bid with boundary passed."""
    return {
        "sku_id": "TEST-SKU-001",
        "analyzed_at": "2026-06-01T10:00:00Z",
        "success": True,
        "profit": mock_profit,
        "decision": {
            "decision_type": "adjust_bid",
            "action": {
                "field": "daily_budget",
                "current_value": 3.00,
                "new_value": 3.40,
                "change_pct": 0.133,
            },
            "reasoning": "近 7 天点击率上升 12%，建议提升预算",
            "confidence": 0.82,
            "risk_level": "low",
        },
        "boundary": {"passed": True, "boundary_type": None, "reason": ""},
        "error": None,
    }


# ============================================================
#  Test: 完整执行循环 (边界通过 -> _run_adjuster -> 日志)
# ============================================================


@pytest.mark.asyncio
async def test_full_execution_cycle(mock_db, analysis_passed):
    """AC-1 & AC-2: full cycle — decision -> boundary -> adjuster -> log."""
    mock_db.get.return_value = None

    with mock.patch(
        "App.services.execution_engine._run_adjuster",
        new=mock.AsyncMock(
            return_value={
                "success": True,
                "operation": "adjust_bid",
                "sku_id": "TEST-SKU-001",
                "old_value": 3.00,
                "new_value": 3.40,
            }
        ),
    ) as mock_run:
        result = await execute_decision(mock_db, analysis_passed)

    assert result["executed"] is True
    assert result["status"] == "success"
    assert result["sku_id"] == "TEST-SKU-001"
    assert result["decision_type"] == "adjust_bid"
    mock_run.assert_awaited_once()
    assert result["adjuster_result"]["success"] is True


# ============================================================
#  Test: 硬边界拦截
# ============================================================


@pytest.mark.asyncio
async def test_hard_boundary_blocked(mock_db):
    """Hard boundary -> failed log + alert."""
    mock_db.get.return_value = None

    analysis = {
        "sku_id": "TEST-SKU-BAD",
        "analyzed_at": "2026-06-01T10:00:00Z",
        "success": True,
        "profit": {"id": 1, "breakeven_ad_spend": 3.20, "roi_7d_trend": []},
        "decision": {
            "decision_type": "adjust_bid",
            "action": {
                "field": "daily_budget",
                "current_value": 3.00,
                "new_value": 500.00,
                "change_pct": 165.0,
            },
            "reasoning": "测试 — 超出预算上限",
            "confidence": 0.50,
            "risk_level": "high",
        },
        "boundary": {
            "passed": False,
            "boundary_type": "hard",
            "reason": "新预算 $500.00 超出上限 $4.80 (盈亏平衡 $3.20 x 150%)",
        },
        "error": None,
    }

    with mock.patch(
        "App.services.execution_engine.log_operation",
        new=mock.AsyncMock(return_value=mock.MagicMock(spec=OperationLog, id=101)),
    ) as mock_log_op:
        with mock.patch(
            "App.services.execution_engine.raise_alert",
            new=mock.AsyncMock(),
        ) as mock_alert:
            result = await execute_decision(mock_db, analysis)

    assert result["executed"] is False
    assert result["status"] == "skipped"
    assert "硬边界" in result["reason"]

    mock_log_op.assert_awaited_once()
    assert mock_log_op.call_args.kwargs.get("status") == "failed"
    mock_alert.assert_awaited_once()


# ============================================================
#  Test: no_action 跳过执行
# ============================================================


@pytest.mark.asyncio
async def test_no_action_skips_execution(mock_db):
    """no_action: only log, no adjuster call."""
    mock_db.get.return_value = None

    analysis = {
        "sku_id": "TEST-SKU-NOP",
        "analyzed_at": "2026-06-01T10:00:00Z",
        "success": True,
        "profit": {"id": 2, "breakeven_ad_spend": 3.20, "roi_7d_trend": []},
        "decision": {
            "decision_type": "no_action",
            "action": None,
            "reasoning": "当前表现良好，无需调整",
            "confidence": 0.95,
            "risk_level": "low",
        },
        "boundary": {"passed": True, "boundary_type": None, "reason": ""},
        "error": None,
    }

    with mock.patch(
        "App.services.execution_engine.log_operation",
        new=mock.AsyncMock(return_value=mock.MagicMock(spec=OperationLog, id=102)),
    ) as mock_log_op:
        result = await execute_decision(mock_db, analysis)

    assert result["executed"] is False
    assert result["status"] == "success"
    assert "no_action" in result["reason"]
    mock_log_op.assert_awaited_once()


# ============================================================
#  Test: dry_run 模式
# ============================================================


@pytest.mark.asyncio
async def test_dry_run_mode(mock_db, analysis_passed):
    """dry_run: log only, skip _run_adjuster."""
    mock_db.get.return_value = None

    with mock.patch(
        "App.services.execution_engine.log_operation",
        new=mock.AsyncMock(return_value=mock.MagicMock(spec=OperationLog, id=103)),
    ) as mock_log_op:
        with mock.patch(
            "App.services.execution_engine._run_adjuster",
            new=mock.AsyncMock(),
        ) as mock_run:
            result = await execute_decision(mock_db, analysis_passed, dry_run=True)

    assert result["executed"] is True
    assert result["status"] == "success"
    assert "dry_run" in result["reason"]
    mock_log_op.assert_awaited_once()
    mock_run.assert_not_awaited()


# ============================================================
#  Test: 软边界暂停确认
# ============================================================


@pytest.mark.asyncio
async def test_soft_boundary_pending(mock_db):
    """Soft boundary -> pending_confirmation log + alert."""
    mock_db.get.return_value = None

    analysis = {
        "sku_id": "TEST-SKU-SOFT",
        "analyzed_at": "2026-06-01T10:00:00Z",
        "success": True,
        "profit": {"id": 3, "breakeven_ad_spend": 3.20, "roi_7d_trend": []},
        "decision": {
            "decision_type": "stop_ad",
            "action": {"field": "ad_type", "current_value": "standard", "new_value": "paused"},
            "reasoning": "ROI 持续下降，建议暂停推广活动",
            "confidence": 0.75,
            "risk_level": "medium",
        },
        "boundary": {
            "passed": False,
            "boundary_type": "soft",
            "reason": "决定关闭推广活动，需要人工确认",
        },
        "error": None,
    }

    mock_pending_log = mock.MagicMock(spec=OperationLog)
    mock_pending_log.id = 200
    mock_pending_log.sku_id = "TEST-SKU-SOFT"
    mock_pending_log.status = "pending_confirmation"

    with mock.patch(
        "App.services.execution_engine.log_operation",
        new=mock.AsyncMock(return_value=mock_pending_log),
    ) as mock_log_op:
        with mock.patch(
            "App.services.execution_engine.raise_alert",
            new=mock.AsyncMock(),
        ) as mock_alert:
            result = await execute_decision(mock_db, analysis)

    assert result["executed"] is False
    assert result["status"] == "pending_confirmation"
    assert result["operation_log_id"] == 200
    assert "软边界" in result["reason"]

    assert mock_log_op.call_args.kwargs.get("status") == "pending_confirmation"
    mock_alert.assert_awaited_once()


# ============================================================
#  Test: confirm_pending
# ============================================================


@pytest.mark.asyncio
async def test_confirm_pending(mock_db):
    """confirm_pending runs the deferred operation."""
    pending_log = mock.MagicMock(spec=OperationLog)
    pending_log.id = 200
    pending_log.sku_id = "TEST-SKU-CONFIRM"
    pending_log.operation_type = "adjust_bid"
    pending_log.field_name = "daily_budget"
    pending_log.old_value = 3.00
    pending_log.new_value = 3.40
    pending_log.ai_reasoning = "ROI 改善中，建议提升预算"
    pending_log.ai_confidence = 0.82
    pending_log.status = "pending_confirmation"
    pending_log.details = {
        "decision": {
            "decision_type": "adjust_bid",
            "action": {"field": "daily_budget"},
        }
    }

    mock_db.get.return_value = pending_log

    with mock.patch(
        "App.services.execution_engine._run_adjuster",
        new=mock.AsyncMock(return_value={"success": True, "operation": "adjust_bid"}),
    ) as mock_run:
        with mock.patch(
            "App.services.execution_engine.update_log_status",
            new=mock.AsyncMock(),
        ) as mock_update:
            result = await confirm_pending(mock_db, 200)

    assert result["success"] is True
    assert result["status"] == "success"
    mock_run.assert_awaited_once()
    mock_update.assert_awaited_once_with(mock_db, 200, "success")


# ============================================================
#  Test: reject_pending
# ============================================================


@pytest.mark.asyncio
async def test_reject_pending(mock_db):
    """reject_pending sets status = rejected."""
    pending_log = mock.MagicMock(spec=OperationLog)
    pending_log.id = 200
    pending_log.sku_id = "TEST-SKU-SOFT"
    pending_log.operation_type = "stop_ad"
    pending_log.status = "pending_confirmation"

    mock_db.get.return_value = pending_log

    with mock.patch(
        "App.services.execution_engine.update_log_status",
        new=mock.AsyncMock(),
    ) as mock_update:
        result = await reject_pending(mock_db, 200)

    assert result["success"] is True
    assert result["status"] == "rejected"
    mock_update.assert_awaited_once_with(mock_db, 200, "rejected")


@pytest.mark.asyncio
async def test_reject_nonexistent_log(mock_db):
    """reject_pending on non-existent log returns error."""
    mock_db.get.return_value = None
    result = await reject_pending(mock_db, 9999)
    assert result["success"] is False
    assert "不存在" in result["error"]


# ============================================================
#  Test: 批量执行
# ============================================================


@pytest.mark.asyncio
async def test_execute_all_passed(mock_db, analysis_passed):
    """execute_all_passed handles multiple results correctly."""
    mock_db.get.return_value = None

    results_list = [
        analysis_passed,
        {  # gets skipped (success=False)
            "sku_id": "SKIP-SKU",
            "success": False,
            "error": "利润计算失败",
            "profit": None,
            "decision": None,
            "boundary": None,
        },
        {
            "sku_id": "TEST-SKU-002",
            "success": True,
            "profit": {"id": 4, "breakeven_ad_spend": 5.00, "roi_7d_trend": []},
            "decision": {
                "decision_type": "adjust_price",
                "action": {
                    "field": "price",
                    "current_value": 12.00,
                    "new_value": 12.50,
                    "change_pct": 0.0417,
                },
                "reasoning": "毛利率偏低，建议微调价格",
                "confidence": 0.65,
                "risk_level": "medium",
            },
            "boundary": {"passed": True, "boundary_type": None, "reason": ""},
            "error": None,
        },
    ]

    with mock.patch(
        "App.services.execution_engine.execute_decision",
        new=mock.AsyncMock(
            side_effect=[
                {"executed": True, "status": "success", "sku_id": "TEST-SKU-001"},
                {"executed": True, "status": "success", "sku_id": "TEST-SKU-002"},
            ]
        ),
    ) as mock_exec:
        summary = await execute_all_passed(mock_db, results_list)

    assert summary["total"] == 3
    assert summary["executed"] == 2
    assert summary["skipped"] == 1
    assert summary["failed"] == 0
    assert summary["pending"] == 0
    assert mock_exec.await_count == 2


# ============================================================
#  Test: 执行崩溃处理
# ============================================================


@pytest.mark.asyncio
async def test_execution_crash(mock_db, analysis_passed):
    """_run_adjuster exception -> failed log + critical alert + global_stop."""
    mock_db.get.return_value = None

    with mock.patch(
        "App.services.execution_engine.log_operation",
        new=mock.AsyncMock(),
    ) as mock_log_op:
        with mock.patch(
            "App.services.execution_engine.raise_alert",
            new=mock.AsyncMock(),
        ) as mock_alert:
            with mock.patch(
                "App.services.execution_engine._run_adjuster",
                new=mock.AsyncMock(side_effect=RuntimeError("浏览器崩溃")),
            ):
                result = await execute_decision(mock_db, analysis_passed)

    assert result["status"] == "failed"
    assert "浏览器崩溃" in result["reason"]

    failed_logs = [
        c for c in mock_log_op.await_args_list if c.kwargs.get("status") == "failed"
    ]
    assert len(failed_logs) >= 1

    global_stop_alerts = [
        c for c in mock_alert.await_args_list if c.kwargs.get("set_global_stop")
    ]
    assert len(global_stop_alerts) >= 1


# ============================================================
#  Test: 操作日志生命周期
# ============================================================


@pytest.mark.asyncio
async def test_operation_log_lifecycle(mock_db, mock_op_log):
    """Verify log creation, status update, and query."""
    # -- create --
    await log_operation(
        mock_db,
        sku_id="TEST-SKU-001",
        operation_type="adjust_bid",
        field_name="daily_budget",
        old_value=3.00,
        new_value=3.40,
        ai_confidence=0.82,
        ai_reasoning="近 7 天点击率上升 12%",
        status="pending_confirmation",
        details={"reason": "人工确认"},
    )

    mock_db.add.assert_called_once()
    added = mock_db.add.call_args[0][0]
    assert added.sku_id == "TEST-SKU-001"
    assert added.operation_type == "adjust_bid"
    assert added.status == "pending_confirmation"

    # -- update status --
    mock_db.get.return_value = mock_op_log
    updated = await update_log_status(mock_db, log_id=42, status="success")
    assert updated is not None

    # -- get pending --
    # scalars()/all() is a sync chain on the result of await db.execute()
    scalars_mock = mock.MagicMock()
    scalars_mock.all.return_value = [mock_op_log]
    mock_db.execute.return_value.scalars = mock.MagicMock(return_value=scalars_mock)
    pending = await get_pending_operations(mock_db)
    assert len(pending) == 1

    # -- filtered query --
    filtered = await get_logs(
        mock_db,
        sku_id="TEST-SKU-001",
        status="success",
        operation_type="adjust_bid",
    )
    assert len(filtered) == 1


# ============================================================
#  Test: 分析管线边界值
# ============================================================


class TestAnalysisBoundaries:
    """Edge cases in the analysis pipeline."""

    @pytest.mark.asyncio
    async def test_missing_sku(self, mock_db):
        """Non-existent SKU returns error."""
        with mock.patch(
            "App.services.analysis_pipeline._get_product",
            new=mock.AsyncMock(return_value=None),
        ):
            result = await analyze_single_sku(mock_db, "NONEXISTENT")
        assert result["success"] is False
        assert "不存在" in result.get("error", "")

    @pytest.mark.asyncio
    async def test_profit_failure(self, mock_db):
        """Profit calculation failure returns error."""
        mock_product = mock.MagicMock()
        mock_product.sku_id = "TEST-SKU"
        mock_product.cost_price = 5.00
        mock_product.category = "Electronics"
        mock_product.is_tracked = True

        with mock.patch(
            "App.services.analysis_pipeline._get_product",
            new=mock.AsyncMock(return_value=mock_product),
        ):
            with mock.patch(
                "App.services.analysis_pipeline.compute_profit",
                new=mock.AsyncMock(side_effect=ValueError("DB 连接失败")),
            ):
                result = await analyze_single_sku(mock_db, "TEST-SKU")

        assert result["success"] is False
        assert "利润计算失败" in result.get("error", "")

    @pytest.mark.asyncio
    async def test_skip_ai(self, mock_db):
        """skip_ai=True skips AI, returns no_action."""
        mock_product = mock.MagicMock()
        mock_product.sku_id = "TEST-SKU"
        mock_product.cost_price = 5.00
        mock_product.category = "Electronics"
        mock_product.is_tracked = True

        mock_profit = mock.MagicMock()
        mock_profit.id = 1
        mock_profit.logistics_cost = 2.30
        mock_profit.platform_fee = 0.60
        mock_profit.true_cost = 7.90
        mock_profit.gross_margin = 0.34
        mock_profit.breakeven_ad_spend = 3.20
        mock_profit.current_roi = 1.85
        mock_profit.roi_7d_trend = []

        with mock.patch(
            "App.services.analysis_pipeline._get_product",
            new=mock.AsyncMock(return_value=mock_product),
        ):
            with mock.patch(
                "App.services.analysis_pipeline.compute_profit",
                new=mock.AsyncMock(return_value=mock_profit),
            ):
                result = await analyze_single_sku(mock_db, "TEST-SKU", skip_ai=True)

        assert result["success"] is True
        assert result["decision"]["decision_type"] == "no_action"


if __name__ == "__main__":
    pytest.main([__file__, "-x", "-v"])
