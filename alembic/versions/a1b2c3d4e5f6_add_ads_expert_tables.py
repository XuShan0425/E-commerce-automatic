"""add_ads_expert_tables — 推广评分、关键词表现、巡检报告、策略、出价历史、AI建议

Revision ID: a1b2c3d4e5f6
Revises: 3667fdd49cd3
Create Date: 2026-06-02 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "3667fdd49cd3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── promotion_scores ────────────────────────────────────────
    op.create_table(
        "promotion_scores",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("sku_id", sa.String(100), nullable=False, index=True),
        sa.Column("score_date", sa.Date(), nullable=False),
        sa.Column("score", sa.SmallInteger(), nullable=False),
        sa.Column("category_match_score", sa.Numeric(5, 4), server_default="0", nullable=False),
        sa.Column("title_match_score", sa.Numeric(5, 4), server_default="0", nullable=False),
        sa.Column("ctr_factor", sa.Numeric(5, 4), server_default="0", nullable=False),
        sa.Column("has_penalty", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("factors", JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_promo_sku_date", "promotion_scores", ["sku_id", "score_date"])

    # ── keyword_performance ─────────────────────────────────────
    op.create_table(
        "keyword_performance",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("sku_id", sa.String(100), nullable=False, index=True),
        sa.Column("keyword", sa.String(300), nullable=False),
        sa.Column("stat_date", sa.Date(), nullable=False),
        sa.Column("promotion_score", sa.SmallInteger(), nullable=True),
        sa.Column("match_score", sa.SmallInteger(), nullable=True),
        sa.Column("impressions", sa.Integer(), server_default="0", nullable=False),
        sa.Column("clicks", sa.Integer(), server_default="0", nullable=False),
        sa.Column("ctr", sa.Numeric(7, 4), server_default="0", nullable=False),
        sa.Column("avg_cpc", sa.Numeric(10, 4), server_default="0", nullable=False),
        sa.Column("orders", sa.Integer(), server_default="0", nullable=False),
        sa.Column("revenue", sa.Numeric(10, 2), server_default="0", nullable=False),
        sa.Column("ad_spend", sa.Numeric(10, 2), server_default="0", nullable=False),
        sa.Column("roi", sa.Numeric(7, 4), server_default="0", nullable=False),
        sa.Column("keyword_type", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_kw_perf_sku_date", "keyword_performance", ["sku_id", "stat_date"])

    # ── inspection_reports ──────────────────────────────────────
    op.create_table(
        "inspection_reports",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("sku_id", sa.String(100), nullable=False, index=True),
        sa.Column("alert_type", sa.String(50), nullable=False),
        sa.Column("severity", sa.String(20), server_default="info", nullable=False),
        sa.Column("reason", sa.Text(), server_default="", nullable=False),
        sa.Column("suggestion", sa.Text(), nullable=True),
        sa.Column("detail_data", JSONB(), nullable=True),
        sa.Column("is_resolved", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_inspect_sku_alert", "inspection_reports", ["sku_id", "alert_type"])

    # ── campaign_strategies ─────────────────────────────────────
    op.create_table(
        "campaign_strategies",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("sku_id", sa.String(100), nullable=False, index=True),
        sa.Column("campaign_type", sa.String(50), nullable=False),
        sa.Column("strategy", sa.String(100), nullable=False),
        sa.Column("params", JSONB(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deactivated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_campaign_sku_active", "campaign_strategies", ["sku_id", "is_active"])

    # ── bid_histories ───────────────────────────────────────────
    op.create_table(
        "bid_histories",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("sku_id", sa.String(100), nullable=False, index=True),
        sa.Column("keyword", sa.String(300), nullable=True),
        sa.Column("bid_type", sa.String(50), nullable=False),
        sa.Column("old_bid", sa.Numeric(10, 2), nullable=True),
        sa.Column("new_bid", sa.Numeric(10, 2), nullable=True),
        sa.Column("change_reason", sa.Text(), nullable=True),
        sa.Column("source", sa.String(50), server_default="engine", nullable=False),
        sa.Column("bid_time", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_bid_sku_time", "bid_histories", ["sku_id", "bid_time"])

    # ── ai_recommendations ──────────────────────────────────────
    op.create_table(
        "ai_recommendations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("sku_id", sa.String(100), nullable=False, index=True),
        sa.Column("rec_type", sa.String(50), nullable=False),
        sa.Column("content", JSONB(), nullable=False),
        sa.Column("status", sa.String(20), server_default="pending", nullable=False),
        sa.Column("source", sa.String(50), server_default="ad_expert_agent", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_ai_rec_sku_type", "ai_recommendations", ["sku_id", "rec_type"])


def downgrade() -> None:
    op.drop_table("ai_recommendations")
    op.drop_table("bid_histories")
    op.drop_table("campaign_strategies")
    op.drop_table("inspection_reports")
    op.drop_table("keyword_performance")
    op.drop_table("promotion_scores")
