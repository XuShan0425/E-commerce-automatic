"""SQLAlchemy ORM 模型."""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
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


class Product(AsyncAttrs, Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sku_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    cost_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    category: Mapped[str | None] = mapped_column(String(200))
    is_tracked: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, server_default="false"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class LogisticsRate(AsyncAttrs, Base):
    __tablename__ = "logistics_rates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    destination_region: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    weight_range_min: Mapped[float] = mapped_column(Numeric(10, 1), nullable=False)
    weight_range_max: Mapped[float] = mapped_column(Numeric(10, 1), nullable=False)
    cost: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class PlatformFee(AsyncAttrs, Base):
    __tablename__ = "platform_fees"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    fee_rate: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AdSnapshot(AsyncAttrs, Base):
    __tablename__ = "ad_snapshots"
    __table_args__ = (
        Index("idx_ad_snapshots_sku_time", "sku_id", "snapshot_time"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sku_id: Mapped[str] = mapped_column(String(100), nullable=False)
    snapshot_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    impressions: Mapped[int] = mapped_column(BigInteger, default=0)
    clicks: Mapped[int] = mapped_column(BigInteger, default=0)
    ctr: Mapped[float] = mapped_column(Numeric(7, 4), default=0)
    orders: Mapped[int] = mapped_column(Integer, default=0)
    conversion_rate: Mapped[float] = mapped_column(Numeric(7, 4), default=0)
    ad_spend: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    revenue: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    ad_type: Mapped[str] = mapped_column(String(50), default="standard")
    buyer_region_breakdown: Mapped[dict | None] = mapped_column(JSONB, default=dict)


class PriceSnapshot(AsyncAttrs, Base):
    __tablename__ = "price_snapshots"
    __table_args__ = (
        Index("idx_price_snapshots_sku_time", "sku_id", "snapshot_time"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sku_id: Mapped[str] = mapped_column(String(100), nullable=False)
    snapshot_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    current_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)


class ProfitAnalysis(AsyncAttrs, Base):
    __tablename__ = "profit_analysis"
    __table_args__ = (
        Index("idx_profit_analysis_sku_time", "sku_id", "calc_time"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sku_id: Mapped[str] = mapped_column(String(100), nullable=False)
    calc_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    logistics_cost: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    platform_fee: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    true_cost: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    gross_margin: Mapped[float] = mapped_column(Numeric(7, 4), default=0)
    breakeven_ad_spend: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    current_roi: Mapped[float] = mapped_column(Numeric(7, 4), default=0)
    roi_7d_trend: Mapped[dict | None] = mapped_column(JSONB, default=list)
