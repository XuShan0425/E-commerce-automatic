"""Webhook 订阅模型 — 注册外部接收事件通知的端点."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from App.core.database import Base


class WebhookSubscription(AsyncAttrs, Base):
    """Webhook 订阅 — 记录第三方接收 URL 及其事件过滤配置。"""

    __tablename__ = "webhook_subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    url: Mapped[str] = mapped_column(String(1024), nullable=False, comment="接收方 URL")
    secret: Mapped[str] = mapped_column(
        String(256), nullable=False, comment="HMAC 签名密钥"
    )
    events: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=list,
        comment="订阅的事件类型列表，空列表表示全部事件",
    )
    description: Mapped[str | None] = mapped_column(
        String(500), comment="可选的描述信息"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        onupdate=func.now(), nullable=False,
    )


class WebhookDeliveryLog(AsyncAttrs, Base):
    """Webhook 投递日志 — 记录每次分发尝试及其结果。"""

    __tablename__ = "webhook_delivery_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    subscription_id: Mapped[int] = mapped_column(
        Integer, nullable=False, index=True,
        comment="关联的订阅 ID",
    )
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[dict | None] = mapped_column(JSONB, comment="原始事件载荷")
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending",
        comment="pending / success / failed / exhausted",
    )
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    response_status: Mapped[int | None] = mapped_column(Integer)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
