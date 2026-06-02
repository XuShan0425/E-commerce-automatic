"""Pydantic schemas — 价格快照."""

from datetime import datetime

from pydantic import BaseModel, Field


class PriceSnapshotCreate(BaseModel):
    sku_id: str = Field(..., max_length=100)
    current_price: float = Field(..., gt=0)


class PriceSnapshotRead(PriceSnapshotCreate):
    id: int
    snapshot_time: datetime

    model_config = {"from_attributes": True}


class PriceSnapshotLatestRead(BaseModel):
    """最新价格快照（不含 snapshot_time 的统一时刻视图）。"""

    sku_id: str
    current_price: float

    model_config = {"from_attributes": True}


class PriceChangeResult(BaseModel):
    """价格变动检测结果。"""

    sku_id: str
    previous_price: float
    current_price: float
    change_pct: float
    is_significant: bool
    direction: str  # "up" | "down" | "unchanged"
