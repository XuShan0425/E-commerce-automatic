"""单元测试 — Webhook 分发服务。

覆盖:
  - HMAC 签名正确生成
  - 事件分发到匹配的订阅
  - 重试机制（成功 / 失败耗尽）
  - 测试 webhook 辅助方法
"""

from __future__ import annotations

import hashlib
import hmac
import json
from unittest import mock

import httpx
import pytest

from App.services.webhook_dispatcher import (
    MAX_RETRIES,
    build_signed_payload,
    compute_signature,
    dispatch_event,
    send_test_webhook,
)

# ═══════════════════════════════════════════════════════
#  HMAC 签名
# ═══════════════════════════════════════════════════════


class TestHMACSignature:
    def test_compute_signature_deterministic(self):
        secret = "test-secret-123"
        payload = b'{"hello": "world"}'
        sig1 = compute_signature(secret, payload)
        sig2 = compute_signature(secret, payload)
        assert sig1 == sig2

    def test_compute_signature_different_secret(self):
        payload = b'{"hello": "world"}'
        sig_a = compute_signature("secret-a", payload)
        sig_b = compute_signature("secret-b", payload)
        assert sig_a != sig_b

    def test_build_signed_payload_includes_timestamp(self):
        secret = "my-secret"
        payload_bytes, signature, headers = build_signed_payload(
            "alert_raised", {"msg": "test"}, secret,
        )
        body = json.loads(payload_bytes)
        assert "timestamp" in body
        assert body["event_type"] == "alert_raised"
        assert body["data"] == {"msg": "test"}

        # 验证签名与 headers 一致
        expected_sig = compute_signature(secret, payload_bytes)
        assert signature == expected_sig
        assert headers["X-Webhook-Signature"] == expected_sig
        assert headers["Content-Type"] == "application/json"

    def test_verify_signature_on_receiver_side(self):
        """模拟接收方验证签名。"""
        secret = "shared-secret"
        data = {"order_id": "12345", "status": "shipped"}
        payload_bytes, signature, headers = build_signed_payload(
            "data_collection_completed", data, secret,
        )

        # 接收方用同样的密钥和 payload 重新计算签名
        expected_sig = hmac.new(
            secret.encode("utf-8"),
            payload_bytes,
            hashlib.sha256,
        ).hexdigest()
        assert signature == expected_sig
        assert headers["X-Webhook-Signature"] == expected_sig


# ═══════════════════════════════════════════════════════
#  事件分发 & 重试
# ═══════════════════════════════════════════════════════


@pytest.fixture
def mock_db():
    """AsyncSession 模拟 — 自动处理 execute → scalars → all 链。"""
    # 构建 scalars().all() 链
    scalar_result = mock.MagicMock()
    scalar_result.all = mock.MagicMock(return_value=[])

    execute_result = mock.MagicMock()
    execute_result.scalars = mock.MagicMock(return_value=scalar_result)
    execute_result.scalar_one_or_none = mock.MagicMock(return_value=None)

    db = mock.AsyncMock()
    db.add = mock.AsyncMock()
    db.flush = mock.AsyncMock()
    db.refresh = mock.AsyncMock()
    db.execute = mock.AsyncMock(return_value=execute_result)
    return db


@pytest.fixture
def mock_scalar_list(mock_db):
    """为 mock_db 配置 scalars().all() 返回指定列表。"""
    def _configure(subscriptions):
        scalar_result = mock.MagicMock()
        scalar_result.all = mock.MagicMock(return_value=subscriptions)
        mock_db.execute.return_value.scalars.return_value = scalar_result
    return _configure


@pytest.fixture
def mock_scalar_one_or_none(mock_db):
    """为 mock_db 配置 scalar_one_or_none() 返回值。"""
    def _configure(value):
        mock_db.execute.return_value.scalar_one_or_none.return_value = value
    return _configure


class FakeSubscription:
    """模拟 SQLAlchemy WebhookSubscription 对象。"""
    def __init__(self, id=1, url="https://example.com/hook", secret="sec1",
                 events=None, is_active=True):
        self.id = id
        self.url = url
        self.secret = secret
        self.events = events or []
        self.is_active = is_active


class TestDispatchEvent:
    @pytest.mark.asyncio
    async def test_unknown_event_type_returns_empty(self, mock_db):
        """未知事件类型应直接返回空列表。"""
        result = await dispatch_event(mock_db, "nonexistent_event", {})
        assert result == []
        mock_db.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_matching_subscriptions(self, mock_db, mock_scalar_list):
        """无匹配订阅时返回空列表。"""
        mock_scalar_list([])
        result = await dispatch_event(mock_db, "alert_raised", {"msg": "test"})
        assert result == []
        # 应该查询了数据库
        mock_db.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_matches_subscription_with_empty_events(self, mock_db, mock_scalar_list):
        """events 为空列表的订阅应收到所有事件。"""
        sub = FakeSubscription(id=1, events=[])
        mock_scalar_list([sub])

        with mock.patch(
            "App.services.webhook_dispatcher._dispatch_single",
            new=mock.AsyncMock(),
        ) as mock_dispatch:
            mock_dispatch.return_value = mock.MagicMock()
            result = await dispatch_event(mock_db, "alert_raised", {"msg": "test"})

        assert len(result) == 1
        mock_dispatch.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_matches_subscription_with_matching_event(self, mock_db, mock_scalar_list):
        """订阅特定事件时应正确匹配。"""
        sub = FakeSubscription(id=1, events=["alert_raised"])
        mock_scalar_list([sub])

        with mock.patch(
            "App.services.webhook_dispatcher._dispatch_single",
            new=mock.AsyncMock(),
        ) as mock_dispatch:
            mock_dispatch.return_value = mock.MagicMock()
            result = await dispatch_event(mock_db, "alert_raised", {"msg": "test"})

        assert len(result) == 1
        mock_dispatch.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_skips_non_matching_event(self, mock_db, mock_scalar_list):
        """不匹配事件类型的订阅应被跳过。"""
        sub = FakeSubscription(id=1, events=["data_collection_completed"])
        mock_scalar_list([sub])

        with mock.patch(
            "App.services.webhook_dispatcher._dispatch_single",
            new=mock.AsyncMock(),
        ) as mock_dispatch:
            result = await dispatch_event(mock_db, "alert_raised", {"msg": "test"})

        assert len(result) == 0
        mock_dispatch.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_skips_inactive_subscription(self, mock_db, mock_scalar_list):
        """SQL WHERE is_active=true 过滤后，无结果则无分发。"""
        # 模拟数据库查询已过滤掉非活跃订阅，返回空列表
        mock_scalar_list([])

        with mock.patch(
            "App.services.webhook_dispatcher._dispatch_single",
            new=mock.AsyncMock(),
        ) as mock_dispatch:
            result = await dispatch_event(mock_db, "alert_raised", {"msg": "test"})

        assert len(result) == 0
        mock_dispatch.assert_not_awaited()


class TestRetryMechanism:
    """测试 _dispatch_single 的重试行为（通过 monkey-patch httpx）。"""

    @mock.patch("App.services.webhook_dispatcher._async_sleep", new=mock.AsyncMock())
    @pytest.mark.asyncio
    async def test_success_on_first_attempt(self, mock_db):
        """首次尝试成功时不应重试。"""
        sub = FakeSubscription(id=1)

        with mock.patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = mock.AsyncMock()
            mock_client_cls.return_value.__aenter__.return_value = mock_client

            mock_response = mock.MagicMock()
            mock_response.status_code = 200
            mock_client.post.return_value = mock_response

            from App.services.webhook_dispatcher import _dispatch_single

            log = await _dispatch_single(mock_db, sub, "alert_raised", {"test": True})

            assert log.status == "success"
            assert log.attempt == 1
            mock_client.post.assert_awaited_once()

    @mock.patch("App.services.webhook_dispatcher._async_sleep", new=mock.AsyncMock())
    @pytest.mark.asyncio
    async def test_retries_on_5xx_then_succeeds(self, mock_db):
        """5xx 错误后重试，最终成功。"""
        sub = FakeSubscription(id=1)

        with mock.patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = mock.AsyncMock()
            mock_client_cls.return_value.__aenter__.return_value = mock_client

            # 前两次 503，第三次 200
            mock_client.post = mock.AsyncMock(side_effect=[
                mock.MagicMock(status_code=503, text="Service Unavailable"),
                mock.MagicMock(status_code=503, text="Service Unavailable"),
                mock.MagicMock(status_code=200),
            ])

            from App.services.webhook_dispatcher import _dispatch_single

            log = await _dispatch_single(mock_db, sub, "alert_raised", {"test": True})

            assert log.status == "success"
            assert log.attempt == 3  # 第三次尝试成功
            assert mock_client.post.await_count == 3

    @mock.patch("App.services.webhook_dispatcher._async_sleep", new=mock.AsyncMock())
    @pytest.mark.asyncio
    async def test_retries_exhausted(self, mock_db):
        """所有重试耗尽时应标记为 exhausted。"""
        sub = FakeSubscription(id=1)

        with mock.patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = mock.AsyncMock()
            mock_client_cls.return_value.__aenter__.return_value = mock_client

            mock_client.post.return_value = mock.MagicMock(
                status_code=502, text="Bad Gateway",
            )

            from App.services.webhook_dispatcher import _dispatch_single

            log = await _dispatch_single(mock_db, sub, "alert_raised", {"test": True})

            assert log.status == "exhausted"
            assert log.attempt == MAX_RETRIES
            assert mock_client.post.await_count == MAX_RETRIES
            assert log.error_message is not None

    @mock.patch("App.services.webhook_dispatcher._async_sleep", new=mock.AsyncMock())
    @pytest.mark.asyncio
    async def test_retries_on_timeout(self, mock_db):
        """超时异常也应触发重试。"""
        sub = FakeSubscription(id=1)

        with mock.patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = mock.AsyncMock()
            mock_client_cls.return_value.__aenter__.return_value = mock_client

            mock_client.post = mock.AsyncMock(
                side_effect=httpx.TimeoutException("Connection timed out"),
            )

            from App.services.webhook_dispatcher import _dispatch_single

            log = await _dispatch_single(mock_db, sub, "alert_raised", {"test": True})

            assert log.status == "exhausted"
            assert log.attempt == MAX_RETRIES
            assert "超时" in (log.error_message or "")


class TestSendTestWebhook:
    @pytest.mark.asyncio
    async def test_send_test_to_existing_subscription(self, mock_db, mock_scalar_one_or_none):
        """向存在的订阅发送测试事件。"""
        sub = FakeSubscription(id=42)
        mock_scalar_one_or_none(sub)

        with mock.patch(
            "App.services.webhook_dispatcher._dispatch_single",
            new=mock.AsyncMock(),
        ) as mock_dispatch:
            mock_dispatch.return_value = mock.MagicMock()

            result = await send_test_webhook(mock_db, 42)
            assert result is not None
            mock_dispatch.assert_awaited_once_with(
                mock_db, sub, "alert_raised",
                {"test": True, "message": "This is a test webhook."},
            )

    @pytest.mark.asyncio
    async def test_send_test_to_nonexistent_subscription(self, mock_db, mock_scalar_one_or_none):
        """不存在的订阅应返回 None。"""
        mock_scalar_one_or_none(None)
        result = await send_test_webhook(mock_db, 999)
        assert result is None
