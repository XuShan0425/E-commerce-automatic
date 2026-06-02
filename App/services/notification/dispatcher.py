"""通知分发器 — 按类型路由 + 通道健康检查与自动降级。"""

from __future__ import annotations

from App.core.logging import get_logger
from App.services.notification.base import BaseNotifier, NotificationMessage
from App.services.notification.slack_notifier import SlackNotifier
from App.services.notification.telegram_notifier import TelegramNotifier
from App.services.notification.wechat_notifier import WeChatNotifier

logger = get_logger(__name__)

# 默认路由规则：通知类型 → [主通道, 备用通道1, 备用通道2, ...]
# 分发器按优先级顺序尝试，第一个发送成功的通道即止。
DEFAULT_ROUTES: dict[str, list[str]] = {
    "alert": ["slack", "telegram", "wechat"],
    "report": ["wechat", "slack"],
    "routine": ["telegram", "wechat"],
}


class NotificationDispatcher:
    """通知分发器。

    职责：
    1. 按通知类型（alert / report / routine）将消息路由到不同通道。
    2. 主通道发送失败时自动降级到备用通道。
    3. 缓存通道健康状态，避免重复请求不可用的通道。
    """

    def __init__(self, routes: dict[str, list[str]] | None = None) -> None:
        self._notifiers: dict[str, BaseNotifier] = {}
        self._routes: dict[str, list[str]] = routes or dict(DEFAULT_ROUTES)
        self._channel_health: dict[str, bool] = {}

    def register(self, notifier: BaseNotifier) -> None:
        """注册一个通知通道。"""
        self._notifiers[notifier.name] = notifier

    def _ensure_default_notifiers(self) -> None:
        """如果尚未注册任何通道，使用 .env 配置自动注册可用通道。"""
        if self._notifiers:
            return
        wechat = WeChatNotifier()
        telegram = TelegramNotifier()
        slack = SlackNotifier()
        # 只注册已配置的通道
        if wechat.health_check():
            self.register(wechat)
        if telegram.health_check():
            self.register(telegram)
        if slack.health_check():
            self.register(slack)

    async def send(self, message: NotificationMessage) -> dict[str, bool]:
        """发送通知，按类型路由，主通道失败时自动降级。

        Returns:
            {通道名: 是否成功} 字典，其中发送成功的通道对应 True。
        """
        self._ensure_default_notifiers()
        route = self._routes.get(
            message.alert_type,
            self._routes.get("routine", []),
        )
        results: dict[str, bool] = {}

        for channel_name in route:
            notifier = self._notifiers.get(channel_name)
            if notifier is None:
                continue

            # 缓存中标记为不可用的通道直接跳过
            if (
                channel_name in self._channel_health
                and not self._channel_health[channel_name]
            ):
                logger.info("Skipping degraded channel: %s", channel_name)
                results[channel_name] = False
                continue

            ok = await notifier.send(message)
            results[channel_name] = ok

            if ok:
                self._channel_health[channel_name] = True
                break  # 主通道成功，不再尝试备用
            else:
                self._channel_health[channel_name] = False
                logger.warning(
                    "Channel %s failed, trying backup...",
                    channel_name,
                )

        return results

    async def health_check_all(self) -> dict[str, dict[str, bool]]:
        """检查所有已注册通道的健康状态。"""
        self._ensure_default_notifiers()
        results: dict[str, dict[str, bool]] = {}
        for name, notifier in self._notifiers.items():
            ok = await notifier.health_check()
            results[name] = {"healthy": ok, "configured": ok}
            self._channel_health[name] = ok
        return results

    @property
    def channel_health(self) -> dict[str, bool]:
        """返回当前缓存的通道健康状态。"""
        return dict(self._channel_health)
