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
    is_tracked: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}


class ProductUpdate(BaseModel):
    name: str | None = Field(None, max_length=500)
    cost_price: float | None = Field(None, gt=0)
    category: str | None = Field(None, max_length=200)
    is_tracked: bool | None = None


class CSVImportResult(BaseModel):
    """CSV 批量导入结果。"""
    total_rows: int
    success_count: int
    failed_rows: list[dict] = []  # [{row: 行号, sku_id: "xxx", error: "错误描述"}, ...]
    preview_rows: list[dict] = []  # 预览模式返回的解析数据 [{row, sku_id, name, cost_price, category}]
    missing_cost_price: bool = False  # 预览模式标记：文件中是否缺少成本价列


class ExportRequest(BaseModel):
    """商品导出请求。"""
    sku_ids: list[str] | None = None


class ProductToggleTracking(BaseModel):
    """Toggle tracking on/off for a single product."""
    is_tracked: bool
