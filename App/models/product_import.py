"""商品导入相关模型 — ProductSku（SKU 维度数据）."""

from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from App.core.database import Base


class ProductSku(AsyncAttrs, Base):
    """SKU 级别数据 — 从速卖通导出的 xlsx 中解析。"""
    __tablename__ = "product_skus"
    __table_args__ = (Index("idx_product_skus_product", "product_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    sku_id: Mapped[str] = mapped_column(String(100), nullable=False)
    sku_attrs: Mapped[str | None] = mapped_column(Text, nullable=True)
    retail_price_usd: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    cost_price_usd: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    stock: Mapped[int] = mapped_column(Integer, default=0)
    weight_kg: Mapped[float | None] = mapped_column(Numeric(8, 3), nullable=True)
    prices_by_country: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
