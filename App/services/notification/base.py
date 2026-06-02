"""通知基类 — 定义统一接口。

所有通知通道（微信 / Telegram / Slack）需继承 BaseNotifier 并实现：
- send()
- format_message()
- health_check()
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class NotificationMessage:
    """统一的通知消息结构。

    Attributes:
        title:   通知标题（可选）。
        body:    通知正文。
        alert_type: 通知类型，'alert' | 'report' | 'routine'。
        severity:   严重级别，'critical' | 'warning' | 'info'。
        metadata:   附加键值对，用于丰富展示（如 SKU ID、ROI 等）。
    """

    title: str = ""
    body: str = ""
    alert_type: str = "routine"
    severity: str = "info"
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def formatted_text(self) -> str:
        """返回格式化的纯文本标题 + 正文。"""
        if self.title:
            return f"{self.title}\n\n{self.body}"
        return self.body


class BaseNotifier(ABC):
    """通知通道基类。

    所有通知通道需继承此类并实现以下抽象方法。
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """通道名称，如 'wechat' / 'telegram' / 'slack'。"""

    @abstractmethod
    async def send(self, message: NotificationMessage) -> bool:
        """发送通知，返回是否成功。"""

    @abstractmethod
    def format_message(self, message: NotificationMessage) -> Any:
        """将统一消息格式化为各通道的专有负载格式。"""

    @abstractmethod
    async def health_check(self) -> bool:
        """检查通道是否可用（配置完整 + API 可达）。"""
