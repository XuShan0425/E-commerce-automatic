"""单品分析数据模型 — 历史数据采集结果存储.

命名风格参考 `ad_snapshots` / `price_snapshots`，每张表包含 `product_id` + `stat_date` 联合索引。
字段使用 JSONB 存储灵活指标（因为速卖通导出的列名可能变化）。
"""

from datetime import date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from App.core.database import Base


class CoreMetric(AsyncAttrs, Base):
    """核心指标 — 单品分析概览数据。"""
    __tablename__ = "core_metrics"
    __table_args__ = (Index("idx_core_metrics_product_date", "product_id", "stat_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    stat_date: Mapped[date] = mapped_column(Date, nullable=False)
    metrics: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class TrafficSource(AsyncAttrs, Base):
    """流量来源明细 — 每个来源一行。"""
    __tablename__ = "traffic_sources"
    __table_args__ = (Index("idx_traffic_sources_product_date", "product_id", "stat_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    stat_date: Mapped[date] = mapped_column(Date, nullable=False)
    source_name: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    sub_source: Mapped[str | None] = mapped_column(String(200), nullable=True)
    metrics: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class KeywordData(AsyncAttrs, Base):
    """关键词数据 — 每个关键词一行。"""
    __tablename__ = "keyword_data"
    __table_args__ = (Index("idx_keyword_data_product_date", "product_id", "stat_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    stat_date: Mapped[date] = mapped_column(Date, nullable=False)
    keyword: Mapped[str] = mapped_column(String(300), nullable=False)
    language: Mapped[str | None] = mapped_column(String(20), nullable=True)
    metrics: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ServiceData(AsyncAttrs, Base):
    """服务数据 — 物流时效、纠纷等。"""
    __tablename__ = "service_data"
    __table_args__ = (Index("idx_service_data_product_date", "product_id", "stat_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    stat_date: Mapped[date] = mapped_column(Date, nullable=False)
    metrics: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class PriceDistribution(AsyncAttrs, Base):
    """价格带分布 — 每个价格区间一行。"""
    __tablename__ = "price_distributions"
    __table_args__ = (Index("idx_price_distributions_product_date", "product_id", "stat_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    stat_date: Mapped[date] = mapped_column(Date, nullable=False)
    price_band: Mapped[str] = mapped_column(String(50), nullable=False)
    product_count: Mapped[int] = mapped_column(Integer, default=0)
    conversion_rate_bps: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class SkuAnalysis(AsyncAttrs, Base):
    """SKU 维度销售数据 — 每个 SKU 一行。"""
    __tablename__ = "sku_analyses"
    __table_args__ = (Index("idx_sku_analyses_product_date", "product_id", "stat_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    stat_date: Mapped[date] = mapped_column(Date, nullable=False)
    sku_id: Mapped[str] = mapped_column(String(100), nullable=False)
    sku_info: Mapped[str | None] = mapped_column(Text, nullable=True)
    metrics: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
