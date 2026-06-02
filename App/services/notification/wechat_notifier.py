"""企业微信通知通道 — 通过企业微信机器人 Webhook 发送 Markdown 消息。"""

from __future__ import annotations

from typing import Any

from App.core.config import settings
from App.core.http import http_post
from App.core.logging import get_logger
from App.services.notification.base import BaseNotifier, NotificationMessage

logger = get_logger(__name__)

SEVERITY_ICONS: dict[str, str] = {
    "critical": "\U0001f6a8",  # 🚨
    "warning": "⚠️",  # ⚠️
    "info": "ℹ️",  # ℹ️
}


class WeChatNotifier(BaseNotifier):
    """企业微信机器人通知通道。

    通过配置的企业微信机器人 Webhook URL 发送 Markdown 格式消息。
    """

    def __init__(self, webhook_url: str = "") -> None:
        self._webhook_url = webhook_url or settings.WECHAT_WEBHOOK_URL or ""

    @property
    def name(self) -> str:
        return "wechat"

    def format_message(self, message: NotificationMessage) -> dict[str, Any]:
        """格式化为企业微信机器人支持的 markdown 消息。"""
        icon = SEVERITY_ICONS.get(message.severity, "\U0001f4e2")  # 📢

        lines: list[str] = []
        if message.title:
            lines.append(f"# {icon} {message.title}")
        lines.append("")
        lines.append(message.body)

        if message.metadata:
            lines.append("")
            lines.append("---")
            for k, v in message.metadata.items():
                lines.append(f"> {k}: {v}")

        return {
            "msgtype": "markdown",
            "markdown": {
                "content": "\n".join(lines),
            },
        }

    async def health_check(self) -> bool:
        """检查 Webhook URL 是否已配置。"""
        return bool(self._webhook_url)

    async def send(self, message: NotificationMessage) -> bool:
        if not self._webhook_url:
            logger.warning("WeChat notifier: no webhook URL configured")
            return False
        try:
            payload = self.format_message(message)
            resp = await http_post(self._webhook_url, json=payload, timeout=15)
            result = resp.json()
            if result.get("errcode") != 0:
                logger.error(
                    "WeChat send failed: %s",
                    result.get("errmsg", "unknown"),
                )
                return False
            return True
        except Exception as exc:
            logger.error("WeChat send error: %s", exc)
            return False
