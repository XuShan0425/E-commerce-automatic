"""Pydantic schemas — 商品."""

from datetime import datetime

from pydantic import BaseModel, Field


class ProductCreate(BaseModel):
    sku_id: str = Field(..., max_length=100, description="速卖通商品ID")
    name: str = Field(..., max_length=500)
    cost_price: float = Field(..., gt=0, description="成本价 (USD)")
    category: str | None = Field(None, max_length=200)


class ProductRead(ProductCreate):
    id: int
    created_at: datetime

    model_config = {"from_attributes": True}


class ProductUpdate(BaseModel):
    name: str | None = Field(None, max_length=500)
    cost_price: float | None = Field(None, gt=0)
    category: str | None = Field(None, max_length=200)


class CSVImportResult(BaseModel):
    """CSV 批量导入结果。"""
    total_rows: int
    success_count: int
    failed_rows: list[dict]  # [{row: 行号, sku_id: "xxx", error: "错误描述"}, ...]
