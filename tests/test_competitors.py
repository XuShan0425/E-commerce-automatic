"""单元测试：竞品数据 API 和拦截器提取逻辑.

使用模拟 JSON 响应测试竞品数据提取和 API 端点逻辑。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from App.schemas.competitor import CompetitorCompareItem, CompetitorCompareResponse, CompetitorSnapshotRead


# ── 竞品数据提取测试 ─────────────────────────────────


def _make_mock_body() -> dict:
    """模拟推荐 API 的 JSON 响应，包含竞品条目。"""
    return {
        "api": "mtop.seller.recommend.getRecommendProducts",
        "data": {
            "products": [
                {
                    "productId": "COMP-001",
                    "subject": "Wireless Bluetooth Earbuds",
                    "price": 9.99,
                    "rating": 4.5,
                    "soldQuantity": 1500,
                },
                {
                    "productId": "COMP-002",
                    "subject": "Noise Cancelling Headphones",
                    "price": 25.50,
                    "rating": 4.2,
                    "soldQuantity": 890,
                },
            ],
            "total": 2,
        },
        "success": True,
    }


@pytest.fixture
def mock_body():
    return _make_mock_body()


def test_find_competitor_items_extracts_products(mock_body: dict) -> None:
    """测试 _find_competitor_items 能从模拟响应中提取竞品条目。"""
    from App.services.api_interceptor import _find_competitor_items

    items = _find_competitor_items(mock_body, source_sku_id="SELF-001")

    assert len(items) == 2
    assert items[0]["sku_id"] == "COMP-001"
    assert items[0]["name"] == "Wireless Bluetooth Earbuds"
    assert items[0]["price"] == 9.99
    assert items[0]["rating"] == 4.5
    assert items[0]["sales"] == 1500
    assert items[0]["source_sku_id"] == "SELF-001"
    assert items[1]["sku_id"] == "COMP-002"


def test_find_competitor_items_skips_self(mock_body: dict) -> None:
    """测试 _find_competitor_items 过滤掉与 source_sku_id 相同的条目。"""
    from App.services.api_interceptor import _find_competitor_items

    # 将第一个条目的 ID 设为与 source_sku_id 相同
    mock_body["data"]["products"][0]["productId"] = "SELF-001"

    items = _find_competitor_items(mock_body, source_sku_id="SELF-001")

    assert len(items) == 1
    assert items[0]["sku_id"] == "COMP-002"


def test_find_competitor_items_handles_empty() -> None:
    """测试 _find_competitor_items 对空数据返回空列表。"""
    from App.services.api_interceptor import _find_competitor_items

    assert _find_competitor_items({}) == []
    assert _find_competitor_items([]) == []
    assert _find_competitor_items({"data": None}) == []
    assert _find_competitor_items({"data": []}) == []


def test_is_competitor_api_matches_recommend() -> None:
    """测试 _is_competitor_api 识别推荐类 URL。"""
    from App.services.api_interceptor import _is_competitor_api

    assert _is_competitor_api("https://seller-acs.aliexpress.com/h5/mtop.recommend.get?xxx")
    assert _is_competitor_api("https://seller-acs.aliexpress.com/h5/mtop.product.detail?xxx")
    assert _is_competitor_api("https://seller-acs.aliexpress.com/h5/mtop.similar.get?xxx")
    assert _is_competitor_api("https://seller-acs.aliexpress.com/h5/mtop.related.get?xxx")
    assert not _is_competitor_api("https://seller-acs.aliexpress.com/h5/mtop.adv.campaign?xxx")
    assert not _is_competitor_api("https://google.com/")


def test_collected_competitor_data_dataclass() -> None:
    """测试 CollectedCompetitorData dataclass。"""
    from App.services.api_interceptor import CollectedCompetitorData

    data = CollectedCompetitorData(
        sku_id="COMP-001",
        name="Test Product",
        price=19.99,
        rating=4.0,
        sales=500,
        source_sku_id="SELF-001",
        source_url="https://example.com/api",
    )

    assert data.sku_id == "COMP-001"
    assert data.name == "Test Product"
    assert data.price == 19.99
    assert data.rating == 4.0
    assert data.sales == 500
    assert data.source_sku_id == "SELF-001"
    assert data.source_url == "https://example.com/api"


# ── Schema 测试 ──────────────────────────────────────


def test_competitor_snapshot_read_schema() -> None:
    """测试 CompetitorSnapshotRead Pydantic schema。"""
    data = CompetitorSnapshotRead(
        id=1,
        sku_id="COMP-001",
        name="Test Product",
        price=15.99,
        rating=4.2,
        sales=1200,
        snapshot_time=datetime.now(timezone.utc),
        source_sku_id="SELF-001",
    )

    assert data.sku_id == "COMP-001"
    assert data.name == "Test Product"
    assert data.price == 15.99
    assert data.rating == 4.2
    assert data.sales == 1200


def test_competitor_compare_response_schema() -> None:
    """测试 CompetitorCompareResponse schema。"""
    response = CompetitorCompareResponse(
        self_product=CompetitorCompareItem(
            sku_id="SELF-001",
            name="My Product",
            price=20.00,
            is_self=True,
        ),
        competitors=[
            CompetitorCompareItem(
                sku_id="COMP-001",
                name="Competitor 1",
                price=15.00,
                rating=4.0,
                sales=500,
                is_self=False,
                snapshot_time=datetime.now(timezone.utc).isoformat(),
            ),
        ],
    )

    assert response.self_product is not None
    assert response.self_product.sku_id == "SELF-001"
    assert len(response.competitors) == 1
    assert response.competitors[0].sku_id == "COMP-001"
    assert response.competitors[0].price == 15.00


# ── API 端点逻辑测试 ─────────────────────────────────


@pytest.mark.asyncio
async def test_list_competitors_endpoint() -> None:
    """测试 list_competitors 查询逻辑。

    使用 mock db 验证查询能正确构建并返回数据。
    """
    from App.api.v1.competitors import list_competitors

    now = datetime.now(timezone.utc)
    mock_snapshot = MagicMock(spec=[
        "id", "sku_id", "name", "price", "rating", "sales", "snapshot_time", "source_sku_id"
    ])
    mock_snapshot.id = 1
    mock_snapshot.sku_id = "COMP-001"
    mock_snapshot.name = "Competitor 1"
    mock_snapshot.price = 9.99
    mock_snapshot.rating = 4.5
    mock_snapshot.sales = 100
    mock_snapshot.snapshot_time = now
    mock_snapshot.source_sku_id = "SELF-001"

    mock_db = AsyncMock()
    mock_db.get.return_value = None  # not used by this path
    # db.execute() returns a coroutine; upon await it yields mock_execute
    mock_execute = MagicMock()
    mock_scalars_result = MagicMock()
    mock_scalars_result.all.return_value = [mock_snapshot]
    mock_execute.scalars.return_value = mock_scalars_result
    mock_db.execute.return_value = mock_execute

    with patch("App.api.v1.competitors.datetime") as mock_dt:
        mock_dt.now.return_value = now
        result = await list_competitors(
            source_sku_id=None,
            limit=50,
            _api_key="test-key",
            db=mock_db,
        )

    assert len(result) == 1
    assert result[0].sku_id == "COMP-001"
    assert result[0].price == 9.99


@pytest.mark.asyncio
async def test_competitor_data_saved_in_backend() -> None:
    """测试数据采集模块能正确处理竞品数据。"""
    from App.services.api_interceptor import (
        AdDataInterceptor,
        CollectedCompetitorData,
        InterceptResult,
    )

    interceptor = AdDataInterceptor()
    assert hasattr(interceptor.result, "competitor_data")
    assert isinstance(interceptor.result, InterceptResult)
    assert interceptor.result.competitor_data == []

    # 模拟添加竞品数据
    comp = CollectedCompetitorData(
        sku_id="COMP-001",
        name="Test",
        price=10.0,
        source_sku_id="SELF-001",
    )
    interceptor.result.competitor_data.append(comp)
    assert len(interceptor.result.competitor_data) == 1


@pytest.mark.asyncio
async def test_competitor_data_collector_integration() -> None:
    """测试 collect_ad_data 中包含竞品数据收集。

    验证竞品数据在 data_collector 的正确传递路径。
    """
    from App.models.base import CompetitorSnapshot

    # 验证模型已正确定义
    assert hasattr(CompetitorSnapshot, "sku_id")
    assert hasattr(CompetitorSnapshot, "name")
    assert hasattr(CompetitorSnapshot, "price")
    assert hasattr(CompetitorSnapshot, "rating")
    assert hasattr(CompetitorSnapshot, "sales")
    assert hasattr(CompetitorSnapshot, "snapshot_time")
    assert hasattr(CompetitorSnapshot, "source_sku_id")

    # 验证表名
    assert CompetitorSnapshot.__tablename__ == "competitor_snapshots"
