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
