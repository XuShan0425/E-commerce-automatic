"""Telegram 通知通道 — 通过 Bot API 发送 HTML 格式消息。"""

from __future__ import annotations

from typing import Any

from App.core.config import settings
from App.core.http import http_get, http_post
from App.core.logging import get_logger
from App.services.notification.base import BaseNotifier, NotificationMessage

logger = get_logger(__name__)

TELEGRAM_API_BASE = "https://api.telegram.org/bot"

SEVERITY_EMOJIS: dict[str, str] = {
    "critical": "\U0001f534",  # 🔴
    "warning": "\U0001f7e1",  # 🟡
    "info": "\U0001f535",  # 🔵
}


class TelegramNotifier(BaseNotifier):
    """Telegram Bot 通知通道。

    通过 Bot API 发送 HTML 格式消息到指定聊天。
    """

    def __init__(self, bot_token: str = "", chat_id: str = "") -> None:
        self._bot_token = bot_token or settings.TELEGRAM_BOT_TOKEN or ""
        self._chat_id = chat_id or settings.TELEGRAM_CHAT_ID or ""

    @property
    def name(self) -> str:
        return "telegram"

    def format_message(self, message: NotificationMessage) -> dict[str, Any]:
        """格式化为 Telegram sendMessage API 参数（HTML parse_mode）。"""
        emoji = SEVERITY_EMOJIS.get(message.severity, "\U0001f7e3")  # 🟣

        lines: list[str] = []
        if message.title:
            lines.append(f"<b>{emoji} {message.title}</b>")
        lines.append("")
        lines.append(message.body)

        if message.metadata:
            lines.append("")
            lines.append("─" * 20)  # ────
            for k, v in message.metadata.items():
                lines.append(f"<b>{k}:</b> {v}")

        return {
            "chat_id": self._chat_id,
            "text": "\n".join(lines),
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }

    async def health_check(self) -> bool:
        """通过 getMe API 检查 Bot Token 有效性。"""
        if not self._bot_token or not self._chat_id:
            return False
        try:
            url = f"{TELEGRAM_API_BASE}{self._bot_token}/getMe"
            resp = await http_get(url, timeout=10)
            return resp.status_code == 200 and resp.json().get("ok", False)
        except Exception:
            return False

    async def send(self, message: NotificationMessage) -> bool:
        if not self._bot_token or not self._chat_id:
            logger.warning(
                "Telegram notifier: bot_token or chat_id not configured",
            )
            return False
        try:
            payload = self.format_message(message)
            url = f"{TELEGRAM_API_BASE}{self._bot_token}/sendMessage"
            resp = await http_post(url, json=payload, timeout=15)
            result = resp.json()
            if not result.get("ok", False):
                logger.error(
                    "Telegram send failed: %s",
                    result.get("description", "unknown"),
                )
                return False
            return True
        except Exception as exc:
            logger.error("Telegram send error: %s", exc)
            return False
