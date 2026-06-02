"""TASK-002-1: Shared test fixtures and mocks for unit tests."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest import mock

import pytest


@pytest.fixture
def mock_db():
    """Create a mock AsyncSession."""
    return mock.AsyncMock()


@pytest.fixture
def sample_ad_snapshots():
    """Create sample AdSnapshot-like objects for testing."""

    class FakeAdSnapshot:
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
            self.snapshot_time = snapshot_time or datetime.now(UTC)
            self.buyer_region_breakdown = None
            self.conversion_rate = orders / clicks if clicks > 0 else 0.0
            self.ctr = clicks / impressions if impressions > 0 else 0.0

    return [
        FakeAdSnapshot(impressions=1200, clicks=60, orders=6, ad_spend=25.0, revenue=150.0),
        FakeAdSnapshot(impressions=1100, clicks=55, orders=5, ad_spend=22.0, revenue=130.0),
        FakeAdSnapshot(impressions=1300, clicks=65, orders=7, ad_spend=28.0, revenue=160.0),
    ]


@pytest.fixture
def sample_profit_analysis():
    """Create a sample ProfitAnalysis-like object."""

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
            {"date": "2026-05-26", "revenue": 120, "ad_spend": 45, "roi": 2.67},
            {"date": "2026-05-27", "revenue": 90, "ad_spend": 50, "roi": 1.80},
            {"date": "2026-05-28", "revenue": 110, "ad_spend": 42, "roi": 2.62},
            {"date": "2026-05-29", "revenue": 130, "ad_spend": 48, "roi": 2.71},
            {"date": "2026-05-30", "revenue": 95, "ad_spend": 38, "roi": 2.50},
            {"date": "2026-05-31", "revenue": 140, "ad_spend": 50, "roi": 2.80},
            {"date": "2026-06-01", "revenue": 160, "ad_spend": 55, "roi": 2.91},
        ],
    )


@pytest.fixture
def sample_analysis_result():
    """Create a sample analysis result dict for execute_decision tests."""
    return {
        "sku_id": "test_sku_001",
        "analyzed_at": "2026-06-01T12:00:00+00:00",
        "success": True,
        "profit": {
            "id": 1,
            "cost_price": 5.00,
            "logistics_cost": 2.50,
            "platform_fee": 0.60,
            "true_cost": 8.10,
            "gross_margin": 0.325,
            "breakeven_ad_spend": 3.90,
            "current_roi": 2.5,
            "roi_7d_trend": [],
        },
        "decision": {
            "decision_type": "no_action",
            "action": None,
            "reasoning": "Current performance is good, no adjustment needed.",
            "confidence": 0.85,
            "risk_level": "low",
        },
        "boundary": {
            "passed": True,
            "boundary_type": None,
            "reason": "",
        },
        "error": None,
    }
