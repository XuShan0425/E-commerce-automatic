"""多渠道通知服务包。"""

from App.services.notification.base import BaseNotifier, NotificationMessage
from App.services.notification.dispatcher import NotificationDispatcher
from App.services.notification.slack_notifier import SlackNotifier
from App.services.notification.telegram_notifier import TelegramNotifier
from App.services.notification.wechat_notifier import WeChatNotifier

__all__ = [
    "BaseNotifier",
    "NotificationDispatcher",
    "NotificationMessage",
    "SlackNotifier",
    "TelegramNotifier",
    "WeChatNotifier",
]
