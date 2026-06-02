"""Webhook 分发服务 — HMAC 签名、事件分发、重试与日志记录。

事件类型
--------
- data_collection_completed   : 数据采集完成
- ai_decision_generated       : AI 决策生成
- boundary_condition_triggered: 边界条件触发
- alert_raised                : 警报产生
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from datetime import UTC, datetime
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from App.models.webhook import WebhookDeliveryLog, WebhookSubscription

logger = logging.getLogger(__name__)

# ── 标准事件类型 ──────────────────────────────────────

EVENT_TYPES = frozenset({
    "data_collection_completed",
    "ai_decision_generated",
    "boundary_condition_triggered",
    "alert_raised",
})

# ── 重试配置 ──────────────────────────────────────────

MAX_RETRIES = 3
RETRY_BASE_DELAY_S = 1.0  # 指数退避基数（秒）
HTTP_TIMEOUT_S = 10.0


# ═══════════════════════════════════════════════════════
#  HMAC 签名
# ═══════════════════════════════════════════════════════


def compute_signature(secret: str, payload: bytes) -> str:
    """使用 HMAC-SHA256 计算 payload 的签名。"""
    return hmac.new(
        secret.encode("utf-8"),
        payload,
        hashlib.sha256,
    ).hexdigest()


def build_signed_payload(
    event_type: str, data: dict[str, Any], secret: str,
) -> tuple[bytes, str, dict[str, str]]:
    """构建带时间戳的 JSON payload 及其签名头部。

    Returns
    -------
    (payload_bytes, signature, headers)
    """
    timestamp = datetime.now(UTC).isoformat()
    body = {"event_type": event_type, "timestamp": timestamp, "data": data}
    payload_bytes = json.dumps(body, ensure_ascii=False, default=str).encode("utf-8")
    signature = compute_signature(secret, payload_bytes)
    headers = {
        "Content-Type": "application/json",
        "X-Webhook-Signature": signature,
        "X-Webhook-Timestamp": timestamp,
    }
    return payload_bytes, signature, headers


# ═══════════════════════════════════════════════════════
#  分发逻辑
# ═══════════════════════════════════════════════════════


async def dispatch_event(
    db: AsyncSession,
    event_type: str,
    data: dict[str, Any],
) -> list[WebhookDeliveryLog]:
    """将事件分发到所有匹配的活跃 webhook 订阅。

    1. 查询 ``is_active = true`` 且事件匹配的订阅
    2. 对每个订阅调用 ``_dispatch_single``
    3. 返回投递日志列表

    Parameters
    ----------
    db : AsyncSession
        数据库会话
    event_type : str
        事件类型（须在 ``EVENT_TYPES`` 中）
    data : dict
        事件载荷

    Returns
    -------
    list[WebhookDeliveryLog]
        本次分发的投递日志列表
    """
    if event_type not in EVENT_TYPES:
        logger.warning("未知事件类型: %s", event_type)
        return []

    # 查询匹配的订阅
    stmt = select(WebhookSubscription).where(
        WebhookSubscription.is_active.is_(True),
    )
    result = await db.execute(stmt)
    subscriptions: list[WebhookSubscription] = list(result.scalars().all())

    matched: list[WebhookSubscription] = []
    for sub in subscriptions:
        if not sub.events or event_type in sub.events:
            matched.append(sub)

    if not matched:
        logger.info("事件 %s 无匹配的 webhook 订阅", event_type)
        return []

    logs: list[WebhookDeliveryLog] = []
    for sub in matched:
        log_entry = await _dispatch_single(db, sub, event_type, data)
        logs.append(log_entry)

    await db.flush()
    return logs


async def _dispatch_single(
    db: AsyncSession,
    subscription: WebhookSubscription,
    event_type: str,
    data: dict[str, Any],
) -> WebhookDeliveryLog:
    """对单个订阅执行分发（含重试）。"""
    payload_bytes, signature, headers = build_signed_payload(
        event_type, data, subscription.secret,
    )

    delivery_log = WebhookDeliveryLog(
        subscription_id=subscription.id,
        event_type=event_type,
        payload={"event_type": event_type, "data": data},
        status="pending",
        attempt=0,
    )
    db.add(delivery_log)
    await db.flush()
    await db.refresh(delivery_log)

    last_error: str | None = None
    last_status: int | None = None

    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_S) as client:
        for attempt in range(1, MAX_RETRIES + 1):
            delivery_log.attempt = attempt
            try:
                response = await client.post(
                    subscription.url,
                    content=payload_bytes,
                    headers=headers,
                )
                last_status = response.status_code
                delivery_log.response_status = last_status

                if 200 <= response.status_code < 300:
                    delivery_log.status = "success"
                    delivery_log.error_message = None
                    logger.info(
                        "Webhook 投递成功: sub=%d url=%s event=%s attempt=%d status=%d",
                        subscription.id, subscription.url, event_type,
                        attempt, response.status_code,
                    )
                    return delivery_log

                # 非 2xx — 重试
                last_error = f"HTTP {response.status_code}: {response.text[:200]}"

            except httpx.TimeoutException as exc:
                last_error = f"超时: {exc}"
            except httpx.RequestError as exc:
                last_error = f"请求错误: {exc}"

            delivery_log.error_message = last_error
            logger.warning(
                "Webhook 投递失败: sub=%d url=%s event=%s attempt=%d/%d error=%s",
                subscription.id, subscription.url, event_type,
                attempt, MAX_RETRIES, last_error,
            )

            if attempt < MAX_RETRIES:
                delay = RETRY_BASE_DELAY_S * (2 ** (attempt - 1))
                await _async_sleep(delay)

    # 所有重试耗尽
    delivery_log.status = "exhausted"
    delivery_log.error_message = last_error
    logger.error(
        "Webhook 投递彻底失败: sub=%d url=%s event=%s attempts=%d last_error=%s",
        subscription.id, subscription.url, event_type, MAX_RETRIES, last_error,
    )
    return delivery_log


async def _async_sleep(seconds: float) -> None:
    """异步等待（不依赖 asyncio.sleep 以外的第三方）。"""
    import asyncio
    await asyncio.sleep(seconds)


# ═══════════════════════════════════════════════════════
#  测试辅助：发送测试 webhook
# ═══════════════════════════════════════════════════════


async def send_test_webhook(
    db: AsyncSession,
    subscription_id: int,
) -> WebhookDeliveryLog | None:
    """向指定订阅发送一条测试事件。

    Returns
    -------
    WebhookDeliveryLog | None
        投递日志，订阅不存在或已停用时返回 None
    """
    result = await db.execute(
        select(WebhookSubscription).where(WebhookSubscription.id == subscription_id),
    )
    sub = result.scalar_one_or_none()
    if sub is None:
        return None

    return await _dispatch_single(
        db, sub, "alert_raised", {"test": True, "message": "This is a test webhook."},
    )
