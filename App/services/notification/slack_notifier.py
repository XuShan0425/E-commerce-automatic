"""Slack 通知通道 — 通过 Incoming Webhook 发送 Block Kit 消息。"""

from __future__ import annotations

from typing import Any

from App.core.config import settings
from App.core.http import http_post
from App.core.logging import get_logger
from App.services.notification.base import BaseNotifier, NotificationMessage

logger = get_logger(__name__)

SEVERITY_COLORS: dict[str, str] = {
    "critical": "#dc2626",
    "warning": "#f59e0b",
    "info": "#3b82f6",
}

SEVERITY_EMOJIS: dict[str, str] = {
    "critical": ":red_circle:",
    "warning": ":large_yellow_circle:",
    "info": ":large_blue_circle:",
}


class SlackNotifier(BaseNotifier):
    """Slack Incoming Webhook 通知通道。

    通过 Incoming Webhook URL 发送 Block Kit 格式消息。
    """

    def __init__(self, webhook_url: str = "") -> None:
        self._webhook_url = webhook_url or settings.SLACK_WEBHOOK_URL or ""

    @property
    def name(self) -> str:
        return "slack"

    def format_message(self, message: NotificationMessage) -> dict[str, Any]:
        """格式化为 Slack Block Kit 消息（含附件边栏颜色）。"""
        color = SEVERITY_COLORS.get(message.severity, "#6b7280")
        emoji = SEVERITY_EMOJIS.get(message.severity, ":large_purple_circle:")

        header_text = (
            f"{emoji} {message.title}" if message.title else "\U0001f514 Notification"
        )

        blocks: list[dict[str, Any]] = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": header_text,
                },
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": message.body,
                },
            },
        ]

        if message.metadata:
            fields: list[dict[str, Any]] = [
                {
                    "type": "mrkdwn",
                    "text": f"*{k}:* {v}",
                }
                for k, v in message.metadata.items()
            ]
            blocks.append({"type": "divider"})
            blocks.append({"type": "section", "fields": fields})

        blocks.append(
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": (
                            f"Type: `{message.alert_type}` "
                            f"| Severity: `{message.severity}`"
                        ),
                    }
                ],
            }
        )

        return {
            "attachments": [
                {
                    "color": color,
                    "blocks": blocks,
                }
            ],
        }

    async def health_check(self) -> bool:
        """检查 Webhook URL 是否已配置。"""
        return bool(self._webhook_url)

    async def send(self, message: NotificationMessage) -> bool:
        if not self._webhook_url:
            logger.warning("Slack notifier: no webhook URL configured")
            return False
        try:
            payload = self.format_message(message)
            resp = await http_post(self._webhook_url, json=payload, timeout=15)
            # Slack webhook returns 200 OK with empty body on success
            if resp.status_code == 200:
                return True
            logger.error(
                "Slack send failed: status=%s body=%s",
                resp.status_code,
                resp.text,
            )
            return False
        except Exception as exc:
            logger.error("Slack send error: %s", exc)
            return False
