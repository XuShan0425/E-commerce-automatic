"""竞品数据 Pydantic schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CompetitorSnapshotRead(BaseModel):
    """竞品快照读取响应。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    sku_id: str
    name: str | None = None
    price: float = 0.0
    rating: float | None = None
    sales: int | None = None
    snapshot_time: datetime
    source_sku_id: str


class CompetitorCompareItem(BaseModel):
    """竞品对比条目（含本店商品信息）。"""

    sku_id: str
    name: str | None = None
    price: float = 0.0
    rating: float | None = None
    sales: int | None = None
    is_self: bool = False
    snapshot_time: datetime | None = None


class CompetitorCompareResponse(BaseModel):
    """竞品对比响应。"""

    self_product: CompetitorCompareItem | None = None
    competitors: list[CompetitorCompareItem] = []
