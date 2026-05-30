"""Pydantic schemas — 费率和物流."""

from datetime import datetime

from pydantic import BaseModel, Field


class LogisticsRateBase(BaseModel):
    destination_region: str = Field(..., max_length=50)
    weight_range_min: float
    weight_range_max: float
    cost: float = Field(..., ge=0)


class LogisticsRateRead(LogisticsRateBase):
    id: int
    updated_at: datetime

    model_config = {"from_attributes": True}


class PlatformFeeBase(BaseModel):
    category: str = Field(..., max_length=200)
    fee_rate: float = Field(..., ge=0)


class PlatformFeeRead(PlatformFeeBase):
    id: int
    updated_at: datetime

    model_config = {"from_attributes": True}
