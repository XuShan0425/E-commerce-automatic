"""Pydantic schemas — 广告快照."""

from datetime import datetime

from pydantic import BaseModel, Field


class AdSnapshotCreate(BaseModel):
    sku_id: str = Field(..., max_length=100)
    impressions: int = 0
    clicks: int = 0
    ctr: float = 0
    orders: int = 0
    conversion_rate: float = 0
    ad_spend: float = 0
    revenue: float = 0
    ad_type: str = "standard"
    buyer_region_breakdown: dict | None = None


class AdSnapshotRead(AdSnapshotCreate):
    id: int
    snapshot_time: datetime

    model_config = {"from_attributes": True}
