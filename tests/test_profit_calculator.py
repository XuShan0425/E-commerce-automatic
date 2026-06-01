"""TASK-001-4: 测试 profit_calculator 模块。

测试利润计算和 ROI 趋势计算函数。
"""

from __future__ import annotations

from datetime import UTC, datetime

from App.services.profit_calculator import _compute_roi_7d_trend


class TestComputeRoi7dTrend:
    """测试 _compute_roi_7d_trend 函数。"""

    def test_basic_trend(self, sample_ad_snapshots):
        """验证 ROI 趋势计算正确。"""
        trend = _compute_roi_7d_trend(sample_ad_snapshots)

        # 结果应该按日期排序
        assert len(trend) > 0
        for entry in trend:
            assert "date" in entry
            assert "revenue" in entry
            assert "ad_spend" in entry
            assert "roi" in entry

        # 验证所有快照的天数都被包含
        dates = {s.snapshot_time.strftime("%Y-%m-%d") for s in sample_ad_snapshots}
        trend_dates = {t["date"] for t in trend}
        assert dates == trend_dates

    def test_empty_snapshots(self):
        """验证无快照时返回空列表。"""
        trend = _compute_roi_7d_trend([])
        assert trend == []

    def test_roi_calculation(self, sample_ad_snapshots):
        """验证 ROI 计算公式：revenue / ad_spend。"""
        trend = _compute_roi_7d_trend(sample_ad_snapshots)

        for entry in trend:
            if entry["ad_spend"] > 0:
                expected_roi = entry["revenue"] / entry["ad_spend"]
                assert entry["roi"] == round(expected_roi, 4)
            else:
                assert entry["roi"] == 0.0

    def test_zero_spend_handling(self):
        """验证零广告花费时 ROI 为 0。"""

        class FakeSnap:
            def __init__(self):
                self.snapshot_time = datetime.now(UTC)
                self.revenue = 100.0
                self.ad_spend = 0.0

        trend = _compute_roi_7d_trend([FakeSnap()])
        assert len(trend) == 1
        assert trend[0]["roi"] == 0.0
        assert trend[0]["ad_spend"] == 0.0
        assert trend[0]["revenue"] == 100.0

    def test_multiple_snapshots_same_day(self):
        """验证同一天多个快照会合并。"""

        class FakeSnap:
            def __init__(self, revenue: float, ad_spend: float):
                self.snapshot_time = datetime(2026, 5, 30, tzinfo=UTC)
                self.revenue = revenue
                self.ad_spend = ad_spend

        snaps = [FakeSnap(100, 50), FakeSnap(200, 60)]
        trend = _compute_roi_7d_trend(snaps)

        assert len(trend) == 1
        assert trend[0]["revenue"] == 300.0  # 100 + 200
        assert trend[0]["ad_spend"] == 110.0  # 50 + 60

    def test_trend_sorted_by_date(self):
        """验证趋势按日期排序。"""

        class FakeSnap:
            def __init__(self, day: int):
                self.snapshot_time = datetime(2026, 5, day, tzinfo=UTC)
                self.revenue = 100.0
                self.ad_spend = 50.0

        snaps = [FakeSnap(28), FakeSnap(25), FakeSnap(30), FakeSnap(26)]
        trend = _compute_roi_7d_trend(snaps)

        dates = [t["date"] for t in trend]
        assert dates == sorted(dates)

    def test_values_rounded(self):
        """验证返回的值已四舍五入。"""

        class FakeSnap:
            def __init__(self):
                self.snapshot_time = datetime(2026, 5, 30, tzinfo=UTC)
                self.revenue = 100.12345
                self.ad_spend = 33.33333

        trend = _compute_roi_7d_trend([FakeSnap()])
        assert trend[0]["revenue"] == 100.12
        assert trend[0]["ad_spend"] == 33.33


class TestModuleImport:
    """验证模块可正常导入。"""

    def test_import_profit_calculator(self):
        from App.services.profit_calculator import compute_profit
        assert compute_profit is not None

    def test_import_decision_engine(self):
        from App.services.decision_engine import generate_decision
        assert generate_decision is not None

    def test_import_boundary_checker(self):
        from App.services.boundary_checker import BoundaryResult, check_boundaries
        assert check_boundaries is not None
        assert BoundaryResult is not None

    def test_import_analysis_pipeline(self):
        from App.services.analysis_pipeline import analyze_all_skus, analyze_single_sku
        assert analyze_single_sku is not None
        assert analyze_all_skus is not None
