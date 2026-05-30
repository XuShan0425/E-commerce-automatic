"""Pydantic schemas — 费率和物流."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ── 物流费率 ────────────────────────────────────

class LogisticsRateBase(BaseModel):
    destination_region: str = Field(..., max_length=50)
    weight_range_min: float
    weight_range_max: float
    cost: float = Field(..., ge=0)


class LogisticsRateCreate(LogisticsRateBase):
    """创建单条物流费率。"""
    pass


class LogisticsRateRead(LogisticsRateBase):
    id: int
    updated_at: datetime

    model_config = {"from_attributes": True}


class LogisticsRateUpdate(BaseModel):
    """更新物流费率（所有字段可选）。"""
    destination_region: str | None = Field(None, max_length=50)
    weight_range_min: float | None = None
    weight_range_max: float | None = None
    cost: float | None = Field(None, ge=0)


# ── 平台佣金 ────────────────────────────────────

class PlatformFeeBase(BaseModel):
    category: str = Field(..., max_length=200)
    fee_rate: float = Field(..., ge=0)


class PlatformFeeCreate(PlatformFeeBase):
    """创建单条平台费率。"""
    pass


class PlatformFeeRead(PlatformFeeBase):
    id: int
    updated_at: datetime

    model_config = {"from_attributes": True}


class PlatformFeeUpdate(BaseModel):
    """更新平台费率（所有字段可选）。"""
    category: str | None = Field(None, max_length=200)
    fee_rate: float | None = Field(None, ge=0)


# ── AI 解析结果（未确认状态）────────────────────

class ParsedLogisticsRate(BaseModel):
    """AI 解析出的单条物流费率（未确认）。"""
    destination_region: str
    weight_range_min: float
    weight_range_max: float
    cost: float


class ParsedPlatformFee(BaseModel):
    """AI 解析出的单条平台费率（未确认）。"""
    category: str
    fee_rate: float


class ParseResultLogistics(BaseModel):
    """物流费率 AI 解析结果。"""
    source_url: str
    parsed_items: list[ParsedLogisticsRate]
    raw_ai_response: str = ""


class ParseResultFees(BaseModel):
    """平台佣金 AI 解析结果。"""
    source_url: str
    parsed_items: list[ParsedPlatformFee]
    raw_ai_response: str = ""


class ConfirmLogisticsRequest(BaseModel):
    """确认物流费率写入请求。"""
    items: list[ParsedLogisticsRate]
    overwrite: bool = False


class ConfirmFeesRequest(BaseModel):
    """确认平台佣金写入请求。"""
    items: list[ParsedPlatformFee]
    overwrite: bool = False


class BatchLogisticsWriteResult(BaseModel):
    """物流费率批量写入结果。"""
    inserted: int
    replaced: int
    errors: list[dict[str, Any]]
