"""通知模块单元测试。"""

from __future__ import annotations

import pytest

from App.services.notification.base import BaseNotifier, NotificationMessage
from App.services.notification.dispatcher import NotificationDispatcher
from App.services.notification.slack_notifier import SlackNotifier
from App.services.notification.telegram_notifier import TelegramNotifier
from App.services.notification.wechat_notifier import WeChatNotifier


class TestNotificationMessage:
    def test_formatted_text_with_title(self) -> None:
        msg = NotificationMessage(title="Test Alert", body="Something happened")
        assert msg.formatted_text == "Test Alert\n\nSomething happened"

    def test_formatted_text_without_title(self) -> None:
        msg = NotificationMessage(body="Just a body")
        assert msg.formatted_text == "Just a body"

    def test_default_values(self) -> None:
        msg = NotificationMessage()
        assert msg.title == ""
        assert msg.body == ""
        assert msg.alert_type == "routine"
        assert msg.severity == "info"
        assert msg.metadata == {}


class TestWeChatNotifier:
    def test_name(self) -> None:
        notifier = WeChatNotifier(webhook_url="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=test")
        assert notifier.name == "wechat"

    @pytest.mark.asyncio
    async def test_health_check_unconfigured(self) -> None:
        notifier = WeChatNotifier(webhook_url="")
        result = await notifier.health_check()
        assert result is False

    @pytest.mark.asyncio
    async def test_health_check_configured(self) -> None:
        notifier = WeChatNotifier(webhook_url="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=test")
        result = await notifier.health_check()
        assert result is True

    def test_format_message(self) -> None:
        notifier = WeChatNotifier(webhook_url="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=test")
        msg = NotificationMessage(
            title="Test Alert",
            body="Something happened",
            alert_type="alert",
            severity="critical",
            metadata={"sku": "123", "roi": "-0.05"},
        )
        result = notifier.format_message(msg)
        assert result["msgtype"] == "markdown"
        assert "Test Alert" in result["markdown"]["content"]
        assert "Something happened" in result["markdown"]["content"]
        assert "sku" in result["markdown"]["content"]
        assert "roi" in result["markdown"]["content"]

    def test_format_message_no_metadata(self) -> None:
        notifier = WeChatNotifier(webhook_url="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=test")
        msg = NotificationMessage(body="Simple message")
        result = notifier.format_message(msg)
        assert result["msgtype"] == "markdown"
        assert "Simple message" in result["markdown"]["content"]

    @pytest.mark.asyncio
    async def test_send_unconfigured(self) -> None:
        notifier = WeChatNotifier(webhook_url="")
        result = await notifier.send(NotificationMessage(body="test"))
        assert result is False


class TestTelegramNotifier:
    def test_name(self) -> None:
        notifier = TelegramNotifier(bot_token="123:ABC", chat_id="456")
        assert notifier.name == "telegram"

    @pytest.mark.asyncio
    async def test_health_check_unconfigured(self) -> None:
        notifier = TelegramNotifier(bot_token="", chat_id="")
        result = await notifier.health_check()
        assert result is False

    def test_format_message(self) -> None:
        notifier = TelegramNotifier(bot_token="123:ABC", chat_id="456")
        msg = NotificationMessage(
            title="Test",
            body="Body text",
            alert_type="alert",
            severity="warning",
            metadata={"key": "value"},
        )
        result = notifier.format_message(msg)
        assert result["chat_id"] == "456"
        assert result["parse_mode"] == "HTML"
        assert "Test" in result["text"]
        assert "Body text" in result["text"]
        assert "key" in result["text"]
        assert result["disable_web_page_preview"] is True

    def test_format_message_no_title(self) -> None:
        notifier = TelegramNotifier(bot_token="123:ABC", chat_id="456")
        msg = NotificationMessage(body="Just body")
        result = notifier.format_message(msg)
        assert "Just body" in result["text"]

    @pytest.mark.asyncio
    async def test_send_unconfigured(self) -> None:
        notifier = TelegramNotifier(bot_token="", chat_id="")
        result = await notifier.send(NotificationMessage(body="test"))
        assert result is False


class TestSlackNotifier:
    def test_name(self) -> None:
        notifier = SlackNotifier(webhook_url="https://hooks.slack.com/services/T00/B00/xxx")
        assert notifier.name == "slack"

    @pytest.mark.asyncio
    async def test_health_check_unconfigured(self) -> None:
        notifier = SlackNotifier(webhook_url="")
        result = await notifier.health_check()
        assert result is False

    @pytest.mark.asyncio
    async def test_health_check_configured(self) -> None:
        notifier = SlackNotifier(webhook_url="https://hooks.slack.com/services/T00/B00/xxx")
        result = await notifier.health_check()
        assert result is True

    def test_format_message(self) -> None:
        notifier = SlackNotifier(webhook_url="https://hooks.slack.com/services/T00/B00/xxx")
        msg = NotificationMessage(
            title="Alert!",
            body="Something broke",
            alert_type="alert",
            severity="critical",
            metadata={"sku_id": "PROD-001"},
        )
        result = notifier.format_message(msg)
        assert "attachments" in result
        assert len(result["attachments"]) == 1
        blocks = result["attachments"][0]["blocks"]
        assert any("Alert!" in str(b) for b in blocks)
        assert any("Something broke" in str(b) for b in blocks)
        assert any("sku_id" in str(b) for b in blocks)

    def test_format_message_no_metadata(self) -> None:
        notifier = SlackNotifier(webhook_url="https://hooks.slack.com/services/T00/B00/xxx")
        msg = NotificationMessage(body="Just body")
        result = notifier.format_message(msg)
        assert "attachments" in result

    @pytest.mark.asyncio
    async def test_send_unconfigured(self) -> None:
        notifier = SlackNotifier(webhook_url="")
        result = await notifier.send(NotificationMessage(body="test"))
        assert result is False


class DummyNotifier(BaseNotifier):
    """用于测试的假通知通道。"""

    def __init__(self, name: str, should_succeed: bool = True) -> None:
        self._name = name
        self._should_succeed = should_succeed
        self.sent_messages: list[NotificationMessage] = []

    @property
    def name(self) -> str:
        return self._name

    async def send(self, message: NotificationMessage) -> bool:
        self.sent_messages.append(message)
        return self._should_succeed

    def format_message(self, message: NotificationMessage) -> str:
        return message.formatted_text

    async def health_check(self) -> bool:
        return True


class TestNotificationDispatcher:
    @pytest.mark.asyncio
    async def test_register_and_send_primary_success(self) -> None:
        primary = DummyNotifier("primary", should_succeed=True)
        backup = DummyNotifier("backup", should_succeed=True)
        dispatcher = NotificationDispatcher(routes={"alert": ["primary", "backup"]})
        dispatcher.register(primary)
        dispatcher.register(backup)

        msg = NotificationMessage(body="test", alert_type="alert")
        results = await dispatcher.send(msg)

        assert results == {"primary": True}
        assert len(primary.sent_messages) == 1
        assert len(backup.sent_messages) == 0  # 主通道成功，备用未触发

    @pytest.mark.asyncio
    async def test_fallback_on_primary_failure(self) -> None:
        primary = DummyNotifier("primary", should_succeed=False)
        backup = DummyNotifier("backup", should_succeed=True)
        dispatcher = NotificationDispatcher(routes={"alert": ["primary", "backup"]})
        dispatcher.register(primary)
        dispatcher.register(backup)

        msg = NotificationMessage(body="test", alert_type="alert")
        results = await dispatcher.send(msg)

        assert results == {"primary": False, "backup": True}
        assert len(primary.sent_messages) == 1
        assert len(backup.sent_messages) == 1

    @pytest.mark.asyncio
    async def test_all_channels_fail(self) -> None:
        primary = DummyNotifier("primary", should_succeed=False)
        backup = DummyNotifier("backup", should_succeed=False)
        dispatcher = NotificationDispatcher(routes={"alert": ["primary", "backup"]})
        dispatcher.register(primary)
        dispatcher.register(backup)

        msg = NotificationMessage(body="test", alert_type="alert")
        results = await dispatcher.send(msg)

        assert results == {"primary": False, "backup": False}

    @pytest.mark.asyncio
    async def test_routing_by_alert_type(self) -> None:
        alert_chan = DummyNotifier("alert_chan", should_succeed=True)
        report_chan = DummyNotifier("report_chan", should_succeed=True)

        dispatcher = NotificationDispatcher(
            routes={
                "alert": ["alert_chan"],
                "report": ["report_chan"],
            },
        )
        dispatcher.register(alert_chan)
        dispatcher.register(report_chan)

        msg = NotificationMessage(body="report data", alert_type="report")
        results = await dispatcher.send(msg)

        assert results == {"report_chan": True}
        assert len(report_chan.sent_messages) == 1
        assert len(alert_chan.sent_messages) == 0

    @pytest.mark.asyncio
    async def test_fallback_unknown_alert_type_uses_routine(self) -> None:
        routine_chan = DummyNotifier("routine_chan", should_succeed=True)
        dispatcher = NotificationDispatcher(
            routes={"routine": ["routine_chan"]},
        )
        dispatcher.register(routine_chan)

        msg = NotificationMessage(body="unknown type", alert_type="nonexistent")
        results = await dispatcher.send(msg)

        assert results == {"routine_chan": True}

    @pytest.mark.asyncio
    async def test_health_check_all(self) -> None:
        healthy = DummyNotifier("healthy", should_succeed=True)
        dispatcher = NotificationDispatcher()
        dispatcher.register(healthy)

        results = await dispatcher.health_check_all()
        assert results == {"healthy": {"healthy": True, "configured": True}}

    @pytest.mark.asyncio
    async def test_degraded_channel_skipped(self) -> None:
        primary = DummyNotifier("primary", should_succeed=False)
        backup = DummyNotifier("backup", should_succeed=True)
        dispatcher = NotificationDispatcher(routes={"alert": ["primary", "backup"]})
        dispatcher.register(primary)
        dispatcher.register(backup)

        # 第一次发送：primary 失败，fallback 到 backup
        msg1 = NotificationMessage(body="first", alert_type="alert")
        await dispatcher.send(msg1)

        # 通道健康缓存中 primary 已标记为不可用
        assert dispatcher.channel_health.get("primary") is False

        # 第二次发送：primary 应被跳过，直接尝试 backup
        msg2 = NotificationMessage(body="second", alert_type="alert")
        results = await dispatcher.send(msg2)

        assert results == {"primary": False, "backup": True}
        # primary 第二次未被实际调用（仅两次发送中第一次被调用了）
        assert len(primary.sent_messages) == 1
        assert len(backup.sent_messages) == 2
