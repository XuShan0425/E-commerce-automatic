"""Tests for inspection_engine.py — 小易巡检引擎."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest import mock

from App.services.inspection_engine import (
    INSPECTION_TYPES,
    _aggregate_metrics,
    _split_recent_vs_previous,
    get_alert_type_label,
    get_severity_label,
)


def _make_snapshot(impressions=1000, clicks=50, orders=5, ad_spend=20.0, revenue=100.0,
                   days_ago=0, ad_type="standard"):
    snap = mock.Mock()
    snap.impressions = impressions
    snap.clicks = clicks
    snap.orders = orders
    snap.ad_spend = ad_spend
    snap.revenue = revenue
    snap.snapshot_time = datetime.now(UTC) - timedelta(days=days_ago)
    snap.ad_type = ad_type
    return snap


class TestAggregateMetrics:
    def test_empty_list(self):
        agg = _aggregate_metrics([])
        assert agg["impressions"] == 0
        assert agg["clicks"] == 0

    def test_single_snapshot(self):
        agg = _aggregate_metrics([_make_snapshot(impressions=1000, clicks=100)])
        assert agg["impressions"] == 1000
        assert agg["clicks"] == 100
        assert agg["ctr"] == 0.1  # 100/1000
        assert agg["roi"] == 5.0  # 100/20

    def test_multiple_snapshots(self):
        snaps = [
            _make_snapshot(impressions=500, clicks=25, ad_spend=10, revenue=50),
            _make_snapshot(impressions=500, clicks=25, ad_spend=10, revenue=50),
        ]
        agg = _aggregate_metrics(snaps)
        assert agg["impressions"] == 1000
        assert agg["clicks"] == 50
        assert agg["ad_spend"] == 20.0
        assert agg["revenue"] == 100.0


class TestSplitRecentVsPrevious:
    def test_recent_is_newer(self):
        snaps = [
            _make_snapshot(days_ago=10),
            _make_snapshot(days_ago=5),
            _make_snapshot(days_ago=1),
        ]
        recent, previous = _split_recent_vs_previous(snaps, recent_days=3)
        assert len(recent) == 1  # 1 day ago
        assert len(previous) >= 1

    def test_empty_returns_empty(self):
        recent, previous = _split_recent_vs_previous([])
        assert recent == []
        assert previous == []


class TestLabels:
    def test_severity_labels(self):
        assert get_severity_label("critical") == "严重"
        assert get_severity_label("warning") == "警告"
        assert get_severity_label("info") == "提示"

    def test_alert_type_labels(self):
        assert get_alert_type_label("exposure_anomaly") == "曝光异常"
        assert get_alert_type_label("replace_product") == "换品建议"
        assert get_alert_type_label("budget_suggestion") == "预算建议"

    def test_inspection_types_defined(self):
        assert "exposure_anomaly" in INSPECTION_TYPES
        assert "replace_product" in INSPECTION_TYPES
        assert len(INSPECTION_TYPES) == 7
