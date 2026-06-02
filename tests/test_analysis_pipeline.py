"""集成测试：analyze_all_skus 管线.

用模拟数据填充 PostgreSQL 数据库，对 3 个 SKU 运行 analyze_all_skus，
断言均成功且利润非零。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from App.core.database import Base
from App.models.base import (
    AdSnapshot,
    LogisticsRate,
    PlatformFee,
    PriceSnapshot,
    Product,
    ProfitAnalysis,
)
from App.services.analysis_pipeline import analyze_all_skus

# Dedicated test database (created externally).
_TEST_DB_URL = (
    "postgresql+asyncpg://ad_manager:change-me-in-production"
    "@localhost:5432/ad_manager_test"
)


# ── Test data: 3 SKUs ──────────────────────────────────────
# Each SKU has: product, price snapshot, 2 ad snapshots (7d window).
# Shared: logistics rates (3 regions), platform fees (2 categories).

_PRODUCT_ROWS = [
    {"sku_id": "SKU-A001", "name": "Wireless Earbuds",
     "cost_price": 15.00, "category": "Electronics", "is_tracked": True},
    {"sku_id": "SKU-A002", "name": "Silicone Phone Case",
     "cost_price": 3.00, "category": "Accessories", "is_tracked": True},
    {"sku_id": "SKU-A003", "name": "Fitness Watch Strap",
     "cost_price": 8.00, "category": "Accessories", "is_tracked": True},
]

_LOGISTICS_ROWS = [
    {"destination_region": "US", "weight_range_min": 0, "weight_range_max": 500, "cost": 3.50},
    {"destination_region": "EU", "weight_range_min": 0, "weight_range_max": 500, "cost": 4.20},
    {"destination_region": "AU", "weight_range_min": 0, "weight_range_max": 500, "cost": 5.00},
]

_FEE_ROWS = [
    {"category": "Electronics", "fee_rate": 0.05},
    {"category": "Accessories", "fee_rate": 0.08},
]

_NOW = datetime.now(timezone.utc)
_T1 = _NOW - timedelta(hours=3)
_T2 = _NOW - timedelta(days=1)

_PRICE_ROWS = [
    {"sku_id": "SKU-A001", "snapshot_time": _NOW, "current_price": 35.00},
    {"sku_id": "SKU-A002", "snapshot_time": _NOW, "current_price": 12.00},
    {"sku_id": "SKU-A003", "snapshot_time": _NOW, "current_price": 25.00},
]

_AD_ROWS = [
    # SKU-A001: profitable (~4x ROI)
    {"sku_id": "SKU-A001", "snapshot_time": _T2,
     "impressions": 500, "clicks": 25, "ctr": 0.05, "orders": 3,
     "conversion_rate": 0.12, "ad_spend": 28.00, "revenue": 105.00,
     "ad_type": "standard", "buyer_region_breakdown": {"US": 0.6, "EU": 0.3, "AU": 0.1}},
    {"sku_id": "SKU-A001", "snapshot_time": _T1,
     "impressions": 620, "clicks": 31, "ctr": 0.05, "orders": 4,
     "conversion_rate": 0.129, "ad_spend": 32.00, "revenue": 140.00,
     "ad_type": "standard", "buyer_region_breakdown": {"US": 0.55, "EU": 0.35, "AU": 0.1}},
    # SKU-A002: healthy (~2.4x ROI)
    {"sku_id": "SKU-A002", "snapshot_time": _T2,
     "impressions": 1200, "clicks": 48, "ctr": 0.04, "orders": 5,
     "conversion_rate": 0.104, "ad_spend": 20.00, "revenue": 60.00,
     "ad_type": "standard", "buyer_region_breakdown": {"US": 0.5, "EU": 0.4, "AU": 0.1}},
    {"sku_id": "SKU-A002", "snapshot_time": _T1,
     "impressions": 980, "clicks": 39, "ctr": 0.04, "orders": 3,
     "conversion_rate": 0.077, "ad_spend": 18.00, "revenue": 36.00,
     "ad_type": "standard", "buyer_region_breakdown": {"US": 0.45, "EU": 0.45, "AU": 0.1}},
    # SKU-A003: moderate (~2.3x ROI)
    {"sku_id": "SKU-A003", "snapshot_time": _T2,
     "impressions": 300, "clicks": 12, "ctr": 0.04, "orders": 1,
     "conversion_rate": 0.083, "ad_spend": 15.00, "revenue": 25.00,
     "ad_type": "standard", "buyer_region_breakdown": {"US": 0.7, "EU": 0.2, "AU": 0.1}},
    {"sku_id": "SKU-A003", "snapshot_time": _T1,
     "impressions": 250, "clicks": 10, "ctr": 0.04, "orders": 2,
     "conversion_rate": 0.200, "ad_spend": 18.00, "revenue": 50.00,
     "ad_type": "standard", "buyer_region_breakdown": {"US": 0.65, "EU": 0.25, "AU": 0.1}},
]


# ── Fixtures ───────────────────────────────────────────────


@pytest_asyncio.fixture
async def test_engine():
    """Create all tables in the test database; drop on teardown."""
    engine = create_async_engine(
        _TEST_DB_URL, echo=False,
        use_insertmanyvalues=False,
    )
    # Drop stale tables first, then create fresh ones
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


async def _insert_rows(conn, table, rows):
    """Insert rows one-by-one using core INSERT to avoid asyncpg batch issues."""
    for row in rows:
        await conn.execute(table.insert().values(**row))


@pytest_asyncio.fixture
async def seeded_factory(test_engine):
    """Seed 3 SKUs of data and patch async_session_factory."""
    factory = async_sessionmaker(
        test_engine, expire_on_commit=False,
    )

    # Use core-level single-row inserts to avoid asyncpg multi-statement limitations.
    async with test_engine.begin() as conn:
        await _insert_rows(conn, Product.__table__, _PRODUCT_ROWS)
        await _insert_rows(conn, LogisticsRate.__table__, _LOGISTICS_ROWS)
        await _insert_rows(conn, PlatformFee.__table__, _FEE_ROWS)
        await _insert_rows(conn, PriceSnapshot.__table__, _PRICE_ROWS)
        await _insert_rows(conn, AdSnapshot.__table__, _AD_ROWS)

    # Patch where it's already imported (module-level reference).
    with patch("App.services.analysis_pipeline.async_session_factory", factory):
        yield factory

    # Cleanup: delete seeded data.
    async with factory() as session:
        for model in (AdSnapshot, PriceSnapshot, ProfitAnalysis,
                       LogisticsRate, PlatformFee, Product):
            await session.execute(model.__table__.delete())
        await session.commit()


# ── Tests ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_analyze_all_skus_profit_non_zero(seeded_factory):
    """3 SKUs analyzed -> all succeed, profit (true_cost, roi) non-zero."""
    factory = seeded_factory

    async with factory() as db:
        result = await analyze_all_skus(db, skip_ai=True)

    # -- Top-level shape ------------------------------------------------
    assert isinstance(result, dict)
    assert result["total"] == 3, f"Expected 3 SKUs, got {result['total']}"
    assert result["analyzed"] == 3, (
        f"Expected 3 analyzed, got {result['analyzed']}"
    )

    # -- Per-SKU assertions ---------------------------------------------
    assert len(result["results"]) == 3

    for r in result["results"]:
        assert r["success"] is True, f"SKU {r['sku_id']} should succeed"
        assert r["error"] is None, f"SKU {r['sku_id']} should have no error"

        profit = r["profit"]
        assert profit is not None, f"SKU {r['sku_id']} should have profit data"

        # Acceptance criterion: profit values are non-zero.
        assert profit["true_cost"] > 0, (
            f"SKU {r['sku_id']}: true_cost={profit['true_cost']} should be > 0"
        )
        assert profit["logistics_cost"] > 0, (
            f"SKU {r['sku_id']}: logistics_cost={profit['logistics_cost']} should be > 0"
        )
        assert profit["gross_margin"] != 0, (
            f"SKU {r['sku_id']}: gross_margin should be non-zero"
        )
        assert profit["current_roi"] > 0, (
            f"SKU {r['sku_id']}: current_roi={profit['current_roi']} should be > 0"
        )
        assert profit["breakeven_ad_spend"] > 0, (
            f"SKU {r['sku_id']}: breakeven_ad_spend={profit['breakeven_ad_spend']} should be > 0"
        )

    # -- Per-SKU spot checks --------------------------------------------
    sku1 = next(r for r in result["results"] if r["sku_id"] == "SKU-A001")
    p1 = sku1["profit"]
    assert p1["cost_price"] == 15.00
    # Electronics fee = 5%; logistics weighted ~3.86
    # true_cost ~= 15 + 3.86 + (35 * 0.05 = 1.75) = 20.61
    assert 20.0 <= p1["true_cost"] <= 22.0, (
        f"SKU-A001 true_cost={p1['true_cost']}"
    )
    # total_revenue = 245, total_ad_spend = 60 -> ROI ~= 4.08
    assert p1["current_roi"] >= 3.0, f"SKU-A001 roi={p1['current_roi']}"

    sku2 = next(r for r in result["results"] if r["sku_id"] == "SKU-A002")
    p2 = sku2["profit"]
    assert p2["cost_price"] == 3.00
    assert p2["current_roi"] > 0

    sku3 = next(r for r in result["results"] if r["sku_id"] == "SKU-A003")
    p3 = sku3["profit"]
    assert p3["cost_price"] == 8.00
    assert p3["current_roi"] > 0

    # -- Summary --------------------------------------------------------
    assert result["summary"]["boundary_passed"] == 3
    assert "no_action" in result["summary"]["decisions"]
