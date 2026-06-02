"""多平台适配器 — 抽象基类与平台状态枚举."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class PlatformType(str, Enum):
    """支持的平台类型."""
    ALIEXPRESS = "aliexpress"
    AMAZON = "amazon"


class PlatformConnectionStatus(str, Enum):
    """平台连接状态."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"
    EXPIRED = "expired"


@dataclass
class PlatformConfig:
    """平台配置信息."""
    platform: PlatformType
    label: str
    enabled: bool = True
    cookie_status: PlatformConnectionStatus = PlatformConnectionStatus.DISCONNECTED
    last_sync_time: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class AdData:
    """统一广告数据结构."""
    platform: PlatformType
    sku_id: str
    snapshot_time: str
    impressions: int = 0
    clicks: int = 0
    ctr: float = 0.0
    orders: int = 0
    conversion_rate: float = 0.0
    ad_spend: float = 0.0
    revenue: float = 0.0
    ad_type: str = "standard"
    buyer_region_breakdown: dict[str, Any] | None = None


@dataclass
class ExecutionAction:
    """统一执行操作结构."""
    action_type: str  # adjust_bid, adjust_price, pause_ad, resume_ad, etc.
    field: str | None = None
    current_value: float | None = None
    new_value: float | None = None
    change_pct: float | None = None
    metadata: dict[str, Any] | None = None


@dataclass
class HealthCheckResult:
    """健康检查结果."""
    is_healthy: bool
    cookie_valid: bool
    message: str = ""
    details: dict[str, Any] | None = None


class PlatformAdapter(ABC):
    """多平台适配器抽象基类.

    所有广告平台需要实现此接口来提供统一的:
    - 登录与 Cookie 管理
    - 广告数据采集
    - 广告操作执行 (出价调整 / 暂停 / 恢复)
    - 健康检查
    """

    def __init__(self, config: PlatformConfig) -> None:
        self.config = config
        self._connection_status: PlatformConnectionStatus = (
            config.cookie_status
        )

    # ── 抽象方法 ──────────────────────────────

    @abstractmethod
    async def login(self, headless: bool = True) -> bool:
        """执行平台登录流程。

        Args:
            headless: 是否使用无头浏览器。

        Returns:
            登录是否成功。
        """
        ...

    @abstractmethod
    async def collect_ad_data(self, sku_ids: list[str] | None = None) -> list[AdData]:
        """采集广告数据。

        Args:
            sku_ids: 需要采集的 SKU ID 列表, None 表示所有 SKU。

        Returns:
            广告数据列表。
        """
        ...

    @abstractmethod
    async def execute_action(self, action: ExecutionAction) -> bool:
        """在平台上执行广告操作。

        Args:
            action: 要执行的操作。

        Returns:
            操作是否成功执行。
        """
        ...

    @abstractmethod
    async def check_health(self) -> HealthCheckResult:
        """检查平台连接与 Cookie 健康状态。

        Returns:
            健康检查结果。
        """
        ...

    # ── 可选实现 ──────────────────────────────

    async def ping(self) -> bool:
        """轻量级连通性检查，默认调用健康检查。"""
        result = await self.check_health()
        return result.is_healthy

    async def disconnect(self) -> None:
        """断开平台连接并清理资源。"""
        self._connection_status = PlatformConnectionStatus.DISCONNECTED

    async def reconnect(self) -> bool:
        """重新连接平台。"""
        if self._connection_status == PlatformConnectionStatus.DISCONNECTED:
            return await self.login(headless=True)
        return True

    @property
    def connection_status(self) -> PlatformConnectionStatus:
        """获取当前连接状态。"""
        return self._connection_status

    def get_platform_info(self) -> dict[str, Any]:
        """获取平台展示信息。"""
        return {
            "type": self.config.platform.value,
            "label": self.config.label,
            "enabled": self.config.enabled,
            "cookie_status": self._connection_status.value,
            "last_sync_time": self.config.last_sync_time,
            "extra": self.config.extra,
        }
