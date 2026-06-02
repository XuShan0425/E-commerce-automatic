"""单元测试 — feedback_service.py 反馈闭环服务."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest import mock

import pytest

from App.models.base import ProfitAnalysis
from App.models.operation_log import OperationLog
from App.services.feedback_service import (
    _find_nearest_roi,
    format_history_for_prompt,
    get_decision_history,
)


@pytest.fixture
def mock_db():
    """AsyncSession mock."""
    db = mock.AsyncMock()
    db.execute = mock.AsyncMock()
    return db


def _make_op_log(
    operation_type: str = "adjust_bid",
    status: str = "success",
    sku_id: str = "TEST-SKU-001",
    old_value: float | None = 3.00,
    new_value: float | None = 3.40,
    confidence: float | None = 0.82,
    reasoning: str = "点击率上升，建议提升预算",
    hours_ago: int = 2,
) -> mock.MagicMock:
    """创建 mock OperationLog。"""
    log = mock.MagicMock(spec=OperationLog)
    log.sku_id = sku_id
    log.operation_type = operation_type
    log.status = status
    log.field_name = "daily_budget"
    log.old_value = old_value
    log.new_value = new_value
    log.ai_confidence = confidence
    log.ai_reasoning = reasoning
    log.details = {}
    log.executed_at = datetime.now(UTC) - timedelta(hours=hours_ago)
    return log


def _make_profit_analysis(
    roi: float = 1.5,
    hours_ago: int = 1,
) -> mock.MagicMock:
    """创建 mock ProfitAnalysis。"""
    pa = mock.MagicMock(spec=ProfitAnalysis)
    pa.current_roi = roi
    pa.calc_time = datetime.now(UTC) - timedelta(hours=hours_ago)
    return pa


# ============================================================
#  Tests: get_decision_history
# ============================================================


class TestGetDecisionHistory:
    """反馈服务：查询决策历史"""

    @pytest.mark.asyncio
    async def test_no_history(self, mock_db):
        """AC-1: 无操作日志时应返回空历史。"""
        # 模拟空结果
        mock_result = mock.MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        result = await get_decision_history(mock_db, "SKU-NO-HISTORY")

        assert result["has_history"] is False
        assert result["recent_decisions"] == []
        assert result["summary"]["total_operations"] == 0

    @pytest.mark.asyncio
    async def test_single_operation(self, mock_db):
        """AC-1: 有操作日志时返回历史记录。"""
        op_logs = [
            _make_op_log(
                operation_type="adjust_bid",
                status="success",
                old_value=3.00,
                new_value=3.40,
                confidence=0.82,
                reasoning="点击率上升 12%",
                hours_ago=2,
            ),
        ]

        profit_records = [
            _make_profit_analysis(roi=1.5, hours_ago=4),
            _make_profit_analysis(roi=1.8, hours_ago=1),
        ]

        mock_op_result = mock.MagicMock()
        mock_op_result.scalars.return_value.all.return_value = op_logs

        mock_profit_result = mock.MagicMock()
        mock_profit_result.scalars.return_value.all.return_value = profit_records

        mock_db.execute = mock.AsyncMock(
            side_effect=[mock_op_result, mock_profit_result]
        )

        result = await get_decision_history(mock_db, "TEST-SKU-001")

        assert result["has_history"] is True
        assert len(result["recent_decisions"]) == 1
        decision = result["recent_decisions"][0]
        assert decision["operation_type"] == "adjust_bid"
        assert decision["status"] == "success"
        assert decision["old_value"] == 3.00
        assert decision["new_value"] == 3.40
        assert decision["ai_confidence"] == 0.82

    @pytest.mark.asyncio
    async def test_roi_delta(self, mock_db):
        """AC-2: 决策历史包含 ROI 变化对比。"""
        op_logs = [
            _make_op_log(operation_type="adjust_bid", hours_ago=3),
        ]

        profit_records = [
            _make_profit_analysis(roi=1.5, hours_ago=5),
            _make_profit_analysis(roi=2.0, hours_ago=1),
        ]

        mock_op_result = mock.MagicMock()
        mock_op_result.scalars.return_value.all.return_value = op_logs

        mock_profit_result = mock.MagicMock()
        mock_profit_result.scalars.return_value.all.return_value = profit_records

        mock_db.execute = mock.AsyncMock(
            side_effect=[mock_op_result, mock_profit_result]
        )

        result = await get_decision_history(mock_db, "TEST-SKU-001")

        decision = result["recent_decisions"][0]
        # roi_before: 最近一次在操作之前的 profit_analysis
        # roi_after: 最近一次在操作之后的 profit_analysis
        assert decision["roi_before"] is not None
        assert decision["roi_after"] is not None
        assert decision["roi_delta"] == round(
            decision["roi_after"] - decision["roi_before"], 4
        )

    @pytest.mark.asyncio
    async def test_summary_stats(self, mock_db):
        """AC-1: 汇总结算正确。"""
        op_logs = [
            _make_op_log(operation_type="adjust_bid", status="success", hours_ago=6),
            _make_op_log(operation_type="no_action", status="success", hours_ago=24),
            _make_op_log(
                operation_type="adjust_price",
                status="failed",
                old_value=10.00,
                new_value=10.50,
                hours_ago=48,
            ),
            _make_op_log(
                operation_type="stop_ad",
                status="pending_confirmation",
                hours_ago=72,
            ),
        ]

        mock_op_result = mock.MagicMock()
        mock_op_result.scalars.return_value.all.return_value = op_logs

        mock_profit_result = mock.MagicMock()
        mock_profit_result.scalars.return_value.all.return_value = []

        mock_db.execute = mock.AsyncMock(
            side_effect=[mock_op_result, mock_profit_result]
        )

        result = await get_decision_history(mock_db, "TEST-SKU-001")

        summary = result["summary"]
        assert summary["total_operations"] == 4
        assert summary["success_count"] == 2
        assert summary["failed_count"] == 1
        assert summary["pending_count"] == 1
        assert summary["rejected_count"] == 0
        assert summary["operation_types"]["adjust_bid"] == 1
        assert summary["operation_types"]["no_action"] == 1
        assert summary["operation_types"]["adjust_price"] == 1
        assert summary["operation_types"]["stop_ad"] == 1


# ============================================================
#  Tests: _find_nearest_roi
# ============================================================


class TestFindNearestRoi:
    """辅助函数：查找最近 ROI"""

    def test_find_before(self):
        records = [
            _make_profit_analysis(roi=1.0, hours_ago=10),
            _make_profit_analysis(roi=1.5, hours_ago=5),
            _make_profit_analysis(roi=2.0, hours_ago=1),
        ]

        ref_time = datetime.now(UTC) - timedelta(hours=3)
        roi = _find_nearest_roi(records, ref_time, before=True)

        assert roi == 1.5  # 3 小时前之前最近的记录是 5 小时前, ROI=1.5

    def test_find_after(self):
        records = [
            _make_profit_analysis(roi=1.0, hours_ago=10),
            _make_profit_analysis(roi=1.5, hours_ago=5),
            _make_profit_analysis(roi=2.0, hours_ago=1),
        ]

        ref_time = datetime.now(UTC) - timedelta(hours=3)
        roi = _find_nearest_roi(records, ref_time, before=False)

        assert roi == 2.0  # 3 小时前之后最近的记录是 1 小时前, ROI=2.0

    def test_empty_records(self):
        roi = _find_nearest_roi([], datetime.now(UTC), before=True)
        assert roi is None

    def test_all_before(self):
        records = [
            _make_profit_analysis(roi=1.0, hours_ago=10),
            _make_profit_analysis(roi=1.5, hours_ago=8),
        ]

        ref_time = datetime.now(UTC) - timedelta(hours=3)
        roi = _find_nearest_roi(records, ref_time, before=True)

        assert roi == 1.5  # 之前最近的是 8 小时前

    def test_all_after(self):
        records = [
            _make_profit_analysis(roi=2.0, hours_ago=1),
            _make_profit_analysis(roi=3.0, hours_ago=0),
        ]

        ref_time = datetime.now(UTC) - timedelta(hours=5)
        roi = _find_nearest_roi(records, ref_time, before=True)

        assert roi == 2.0  # 之前最近的是最早的记录


# ============================================================
#  Tests: format_history_for_prompt
# ============================================================


class TestFormatHistoryForPrompt:
    """辅助函数：格式化决策历史为 AI prompt 文本"""

    def test_empty_history(self):
        history = {"has_history": False, "recent_decisions": [], "summary": {}}
        text = format_history_for_prompt(history)
        assert text == ""

    def test_formatted_output(self):
        history = {
            "has_history": True,
            "recent_decisions": [
                {
                    "operation_type": "adjust_bid",
                    "status": "success",
                    "field_name": "daily_budget",
                    "old_value": 3.00,
                    "new_value": 3.40,
                    "change_pct": 0.133,
                    "ai_reasoning": "点击率上升 12%，建议提升预算",
                    "ai_confidence": 0.82,
                    "roi_before": 1.5,
                    "roi_after": 1.8,
                    "roi_delta": 0.3,
                },
            ],
            "summary": {
                "total_operations": 1,
                "success_count": 1,
                "failed_count": 0,
                "pending_count": 0,
                "rejected_count": 0,
                "avg_confidence": 0.82,
            },
        }

        text = format_history_for_prompt(history)

        assert "近期操作历史" in text
        assert "adjust_bid" in text
        assert "成功" in text
        assert "ROI 变化" in text
        assert "+0.3" in text or "0.3" in text
        assert "反馈闭环" in text

    def test_no_decisions_no_history(self):
        history = {
            "has_history": True,
            "recent_decisions": [],
            "summary": {"total_operations": 0, "success_count": 0},
        }
        text = format_history_for_prompt(history)
        assert text == ""


if __name__ == "__main__":
    pytest.main([__file__, "-x", "-v"])
