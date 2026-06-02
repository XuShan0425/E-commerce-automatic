"""联盟营销数据 Pydantic schemas."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class AffiliateCommissionItem(BaseModel):
    """联盟佣金条目。"""

    sku_id: str = ""
    product_name: str = ""
    commission_rate: float = 0.0
    commission_amount: float = 0.0
    price: float = 0.0


class AffiliatePerformanceItem(BaseModel):
    """联盟效果数据条目。"""

    sku_id: str = ""
    product_name: str = ""
    clicks: int = 0
    orders: int = 0
    commission_earned: float = 0.0
    revenue: float = 0.0
    conversion_rate: float = 0.0


class AffiliateCollectResponse(BaseModel):
    """联盟数据采集响应。"""

    success: bool = False
    total_pages_visited: int = 0
    total_api_responses: int = 0
    affiliate_api_responses: int = 0
    commissions: list[AffiliateCommissionItem] = []
    performance: list[AffiliatePerformanceItem] = []
    errors: list[str] = []
    duration_seconds: float = 0.0
    collected_at: str = ""
