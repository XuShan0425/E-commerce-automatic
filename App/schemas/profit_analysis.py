"""Pydantic schemas — 利润分析."""

from datetime import datetime

from pydantic import BaseModel, Field


class ProfitAnalysisBase(BaseModel):
    sku_id: str = Field(..., max_length=100)
    logistics_cost: float = 0
    platform_fee: float = 0
    true_cost: float = 0
    gross_margin: float = 0
    breakeven_ad_spend: float = 0
    current_roi: float = 0
    roi_7d_trend: list | None = None


class ProfitAnalysisRead(ProfitAnalysisBase):
    id: int
    calc_time: datetime

    model_config = {"from_attributes": True}


class RoiTrendPoint(BaseModel):
    """单日 ROI 趋势数据点."""

    date: str
    roi: float
    revenue: float
    ad_spend: float


class RoiTrendItem(BaseModel):
    """单个 SKU 的 ROI 趋势."""

    sku_id: str
    trend: list[RoiTrendPoint]


class RoiTrendSummary(BaseModel):
    """按日聚合的 ROI 趋势摘要."""

    date: str
    roi: float
    revenue: float
    ad_spend: float
    sku_count: int
