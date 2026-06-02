"""速卖通广告专家系统 — 广告策略数据模型.

推广评分、关键词表现、巡检报告、广告策略、出价历史、AI 建议.
"""

from datetime import date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from App.core.database import Base


class PromotionScore(AsyncAttrs, Base):
    """推广评分历史 — 每个 SKU 每日的五星评级."""
    __tablename__ = "promotion_scores"
    __table_args__ = (Index("idx_promo_sku_date", "sku_id", "score_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sku_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    score_date: Mapped[date] = mapped_column(Date, nullable=False)
    score: Mapped[int] = mapped_column(SmallInteger, nullable=False)  # 1-5
    # 评分因子明细
    category_match_score: Mapped[float] = mapped_column(Numeric(5, 4), default=0)
    title_match_score: Mapped[float] = mapped_column(Numeric(5, 4), default=0)
    ctr_factor: Mapped[float] = mapped_column(Numeric(5, 4), default=0)
    has_penalty: Mapped[bool] = mapped_column(default=False)
    factors: Mapped[dict | None] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class KeywordPerformance(AsyncAttrs, Base):
    """关键词表现 — 每个关键词的投放效果."""
    __tablename__ = "keyword_performance"
    __table_args__ = (Index("idx_kw_perf_sku_date", "sku_id", "stat_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sku_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    keyword: Mapped[str] = mapped_column(String(300), nullable=False)
    stat_date: Mapped[date] = mapped_column(Date, nullable=False)
    # 推广评分
    promotion_score: Mapped[int | None] = mapped_column(SmallInteger)
    match_score: Mapped[int | None] = mapped_column(SmallInteger)  # 0-100
    # 广告效果
    impressions: Mapped[int] = mapped_column(Integer, default=0)
    clicks: Mapped[int] = mapped_column(Integer, default=0)
    ctr: Mapped[float] = mapped_column(Numeric(7, 4), default=0)
    avg_cpc: Mapped[float] = mapped_column(Numeric(10, 4), default=0)
    orders: Mapped[int] = mapped_column(Integer, default=0)
    revenue: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    ad_spend: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    roi: Mapped[float] = mapped_column(Numeric(7, 4), default=0)
    # 关键词类型：热搜词/高转化词/捡漏词/低成本词
    keyword_type: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class InspectionReport(AsyncAttrs, Base):
    """巡检报告 — 小易巡检每次检查的输出."""
    __tablename__ = "inspection_reports"
    __table_args__ = (Index("idx_inspect_sku_alert", "sku_id", "alert_type"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sku_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    alert_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )
    # exposure | click | roi | spend | conversion | replace | budget
    severity: Mapped[str] = mapped_column(String(20), default="info")
    # info | warning | critical
    reason: Mapped[str] = mapped_column(Text, default="")
    suggestion: Mapped[str | None] = mapped_column(Text)
    detail_data: Mapped[dict | None] = mapped_column(JSONB, default=dict)
    is_resolved: Mapped[bool] = mapped_column(default=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class CampaignStrategy(AsyncAttrs, Base):
    """广告策略 — 当前生效的投放策略配置."""
    __tablename__ = "campaign_strategies"
    __table_args__ = (Index("idx_campaign_sku_active", "sku_id", "is_active"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sku_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    campaign_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )
    # zijitou | quandian | yizhantui | lianmeng
    strategy: Mapped[str] = mapped_column(String(100), nullable=False)
    # manual_bid | cost_control | volume_first | roi_target
    # 策略参数
    params: Mapped[dict | None] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(default=True)
    activated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    deactivated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class BidHistory(AsyncAttrs, Base):
    """出价历史 — 细粒度出价调整记录."""
    __tablename__ = "bid_histories"
    __table_args__ = (Index("idx_bid_sku_time", "sku_id", "bid_time"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sku_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    keyword: Mapped[str | None] = mapped_column(String(300))
    bid_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # keyword_bid | search_premium | recommendation_premium | daily_budget
    old_bid: Mapped[float | None] = mapped_column(Numeric(10, 2))
    new_bid: Mapped[float | None] = mapped_column(Numeric(10, 2))
    change_reason: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(50), default="engine")
    # engine | plugin | manual | ai_agent
    bid_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AIRecommendation(AsyncAttrs, Base):
    """AI 建议记录 — 专家 Agent 的每日运营建议."""
    __tablename__ = "ai_recommendations"
    __table_args__ = (Index("idx_ai_rec_sku_type", "sku_id", "rec_type"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sku_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    rec_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # priority_sku | budget_adjust | keyword_suggest | diagnosis | replace_suggestion
    content: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    # pending | applied | rejected | expired
    source: Mapped[str] = mapped_column(String(50), default="ad_expert_agent")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
