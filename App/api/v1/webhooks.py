"""Webhook 管理 API — 注册、查询、删除、测试 Webhook 订阅。"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from App.core.database import get_db
from App.core.security import verify_api_key
from App.models.webhook import WebhookDeliveryLog, WebhookSubscription
from App.services.webhook_dispatcher import EVENT_TYPES, send_test_webhook

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


# ── Schemas ────────────────────────────────────────────


class WebhookCreate(BaseModel):
    url: str = Field(..., description="接收方 URL")
    secret: str = Field(..., min_length=8, max_length=256, description="HMAC 签名密钥")
    events: list[str] = Field(default_factory=list, description="订阅的事件类型列表，空=全部")
    description: str | None = Field(None, max_length=500)


class WebhookUpdate(BaseModel):
    url: str | None = None
    secret: str | None = Field(None, min_length=8, max_length=256)
    events: list[str] | None = None
    description: str | None = None
    is_active: bool | None = None


class WebhookRead(BaseModel):
    id: int
    url: str
    events: list[str]
    description: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WebhookDeliveryLogRead(BaseModel):
    id: int
    subscription_id: int
    event_type: str
    status: str
    attempt: int
    response_status: int | None
    error_message: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Endpoints ──────────────────────────────────────────


@router.get("/", response_model=list[WebhookRead])
async def list_webhooks(
    _api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
) -> list[WebhookRead]:
    """获取所有 webhook 订阅列表。"""
    result = await db.execute(
        select(WebhookSubscription).order_by(WebhookSubscription.created_at.desc()),
    )
    subs = list(result.scalars().all())
    return [WebhookRead.model_validate(s) for s in subs]


@router.post("/", response_model=WebhookRead, status_code=status.HTTP_201_CREATED)
async def create_webhook(
    body: WebhookCreate,
    _api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
) -> WebhookRead:
    """注册一个新的 webhook 订阅。"""
    # 校验事件类型
    if body.events:
        unknown = set(body.events) - EVENT_TYPES
        if unknown:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"未知事件类型: {', '.join(sorted(unknown))}",
            )

    sub = WebhookSubscription(
        url=str(body.url) if hasattr(body.url, "unicode_string") else body.url,
        secret=body.secret,
        events=body.events,
        description=body.description,
    )
    if hasattr(sub, "url") and not isinstance(sub.url, str):
        sub.url = str(sub.url)

    db.add(sub)
    await db.flush()
    await db.refresh(sub)
    return WebhookRead.model_validate(sub)


@router.get("/{webhook_id}", response_model=WebhookRead)
async def get_webhook(
    webhook_id: int,
    _api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
) -> WebhookRead:
    """获取单个 webhook 订阅详情。"""
    result = await db.execute(
        select(WebhookSubscription).where(WebhookSubscription.id == webhook_id),
    )
    sub = result.scalar_one_or_none()
    if sub is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook 订阅未找到")
    return WebhookRead.model_validate(sub)


@router.put("/{webhook_id}", response_model=WebhookRead)
async def update_webhook(
    webhook_id: int,
    body: WebhookUpdate,
    _api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
) -> WebhookRead:
    """更新 webhook 订阅。"""
    result = await db.execute(
        select(WebhookSubscription).where(WebhookSubscription.id == webhook_id),
    )
    sub = result.scalar_one_or_none()
    if sub is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook 订阅未找到")

    # 校验事件类型
    if body.events is not None:
        unknown = set(body.events) - EVENT_TYPES
        if unknown:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"未知事件类型: {', '.join(sorted(unknown))}",
            )

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(sub, field, value)

    await db.flush()
    await db.refresh(sub)
    return WebhookRead.model_validate(sub)


@router.delete("/{webhook_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_webhook(
    webhook_id: int,
    _api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
) -> None:
    """删除 webhook 订阅。"""
    result = await db.execute(
        select(WebhookSubscription).where(WebhookSubscription.id == webhook_id),
    )
    sub = result.scalar_one_or_none()
    if sub is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook 订阅未找到")

    await db.delete(sub)
    await db.flush()


@router.post("/{webhook_id}/test", response_model=WebhookDeliveryLogRead)
async def test_webhook(
    webhook_id: int,
    _api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
) -> WebhookDeliveryLogRead:
    """向指定 webhook 发送一条测试事件，验证连通性。"""
    log_entry = await send_test_webhook(db, webhook_id)
    if log_entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook 订阅未找到")
    return WebhookDeliveryLogRead.model_validate(log_entry)


@router.get("/{webhook_id}/logs", response_model=list[WebhookDeliveryLogRead])
async def list_webhook_logs(
    webhook_id: int,
    _api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
) -> list[WebhookDeliveryLogRead]:
    """获取指定 webhook 的投递日志。"""
    # 先验证 webhook 存在
    result = await db.execute(
        select(WebhookSubscription).where(WebhookSubscription.id == webhook_id),
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook 订阅未找到")

    result = await db.execute(
        select(WebhookDeliveryLog)
        .where(WebhookDeliveryLog.subscription_id == webhook_id)
        .order_by(WebhookDeliveryLog.created_at.desc())
        .limit(limit),
    )
    logs = list(result.scalars().all())
    return [WebhookDeliveryLogRead.model_validate(log) for log in logs]


@router.get("/events/types", response_model=list[str])
async def list_event_types(
    _api_key: str = Depends(verify_api_key),
) -> list[str]:
    """获取所有可用的事件类型。"""
    return sorted(EVENT_TYPES)
