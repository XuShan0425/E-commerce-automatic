"""TASK-001-4 测试共用 mock 和 fixture。"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest import mock

import pytest


@pytest.fixture
def mock_db():
    """创建 mock AsyncSession。"""
    return mock.AsyncMock()


@pytest.fixture
def sample_ad_snapshots():
    """创建示例广告快照数据。"""
    now = datetime.now(UTC)

    class FakeSnapshot:
        def __init__(
            self,
            impressions: int = 1000,
            clicks: int = 50,
            orders: int = 5,
            ad_spend: float | str = 20.0,
            revenue: float | str = 100.0,
            ad_type: str = "standard",
            snapshot_time: datetime | None = None,
        ):
            self.impressions = impressions
            self.clicks = clicks
            self.orders = orders
            self.ad_spend = ad_spend
            self.revenue = revenue
            self.ad_type = ad_type
            self.snapshot_time = snapshot_time or now
            self.buyer_region_breakdown = None
            self.conversion_rate = orders / clicks if clicks > 0 else 0.0
            self.ctr = clicks / impressions if impressions > 0 else 0.0

    return [
        FakeSnapshot(
            impressions=1200,
            clicks=60,
            orders=6,
            ad_spend=25.0,
            revenue=150.0,
            snapshot_time=now,
        ),
        FakeSnapshot(
            impressions=1100,
            clicks=55,
            orders=5,
            ad_spend=22.0,
            revenue=130.0,
            snapshot_time=now,
        ),
        FakeSnapshot(
            impressions=1300,
            clicks=65,
            orders=7,
            ad_spend=28.0,
            revenue=160.0,
            snapshot_time=now,
        ),
    ]


@pytest.fixture
def sample_profit_analysis():
    """创建示例 ProfitAnalysis 对象。"""

    class FakeProfitAnalysis:
        def __init__(self, **kwargs: Any):
            for k, v in kwargs.items():
                setattr(self, k, v)

    return FakeProfitAnalysis(
        id=1,
        sku_id="test_sku_001",
        calc_time=datetime.now(UTC),
        logistics_cost=2.50,
        platform_fee=0.60,
        true_cost=8.10,
        gross_margin=0.325,
        breakeven_ad_spend=3.90,
        current_roi=2.5,
        roi_7d_trend=[
            {"date": "2026-05-25", "revenue": 100, "ad_spend": 40, "roi": 2.5},
            {"date": "2026-05-26", "revenue": 120, "ad_spend": 45, "roi": 2.67},
            {"date": "2026-05-27", "revenue": 90, "ad_spend": 50, "roi": 1.8},
            {"date": "2026-05-28", "revenue": 110, "ad_spend": 42, "roi": 2.62},
            {"date": "2026-05-29", "revenue": 130, "ad_spend": 48, "roi": 2.71},
            {"date": "2026-05-30", "revenue": 95, "ad_spend": 38, "roi": 2.5},
            {"date": "2026-05-31", "revenue": 140, "ad_spend": 50, "roi": 2.8},
        ],
    )


@pytest.fixture
def negative_roi_analysis():
    """创建 ROI 连续为负的 ProfitAnalysis 对象。"""

    class FakeProfitAnalysis:
        def __init__(self, **kwargs: Any):
            for k, v in kwargs.items():
                setattr(self, k, v)

    return FakeProfitAnalysis(
        id=2,
        sku_id="bad_sku",
        calc_time=datetime.now(UTC),
        logistics_cost=3.00,
        platform_fee=0.50,
        true_cost=8.50,
        gross_margin=-0.1,
        breakeven_ad_spend=1.00,
        current_roi=-0.5,
        roi_7d_trend=[
            {"date": "2026-05-25", "revenue": 30, "ad_spend": 50, "roi": -0.4},
            {"date": "2026-05-26", "revenue": 25, "ad_spend": 55, "roi": -0.55},
            {"date": "2026-05-27", "revenue": 20, "ad_spend": 45, "roi": -0.56},
            {"date": "2026-05-28", "revenue": 35, "ad_spend": 60, "roi": -0.42},
            {"date": "2026-05-29", "revenue": 28, "ad_spend": 52, "roi": -0.46},
            {"date": "2026-05-30", "revenue": 22, "ad_spend": 48, "roi": -0.54},
            {"date": "2026-05-31", "revenue": 30, "ad_spend": 55, "roi": -0.45},
        ],
    )
