"""多平台统一调度与数据同步服务."""

from __future__ import annotations

from typing import Any

from App.core.logging import get_logger
from App.services.platform.base import (
    AdData,
    HealthCheckResult,
    PlatformAdapter,
    PlatformConfig,
    PlatformConnectionStatus,
    PlatformType,
)
from App.services.platform.amazon_adapter import AmazonAdapter

logger = get_logger(__name__)


class PlatformSyncService:
    """多平台统一调度服务.

    管理所有已注册的 PlatformAdapter 实例，提供统一的
    采集调度、数据聚合和健康检查入口。
    """

    def __init__(self) -> None:
        self._adapters: dict[PlatformType, PlatformAdapter] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        """注册默认平台适配器。"""
        # Amazon adapter — 按需启用
        self._adapters[PlatformType.AMAZON] = AmazonAdapter()

    def register_adapter(
        self,
        platform_type: PlatformType,
        adapter: PlatformAdapter,
    ) -> None:
        """注册自定义平台适配器。"""
        self._adapters[platform_type] = adapter
        logger.info("platform_sync: 已注册平台适配器 %s", platform_type.value)

    def get_adapter(self, platform_type: PlatformType) -> PlatformAdapter | None:
        """获取指定平台的适配器实例。"""
        return self._adapters.get(platform_type)

    def get_enabled_adapters(self) -> list[PlatformAdapter]:
        """获取所有已启用的平台适配器。"""
        return [
            a for a in self._adapters.values()
            if a.config.enabled
        ]

    def list_platforms(self) -> list[dict[str, Any]]:
        """列出所有已注册平台的信息。"""
        return [
            a.get_platform_info()
            for a in self._adapters.values()
        ]

    # ── 健康检查 ──────────────────────────────

    async def check_all_health(self) -> dict[str, HealthCheckResult]:
        """对所有已注册平台执行健康检查。"""
        results: dict[str, HealthCheckResult] = {}
        for ptype, adapter in self._adapters.items():
            try:
                result = await adapter.check_health()
                results[ptype.value] = result
            except Exception as exc:
                results[ptype.value] = HealthCheckResult(
                    is_healthy=False,
                    cookie_valid=False,
                    message=f"健康检查异常: {exc}",
                )
                logger.error(
                    "platform_sync: %s 健康检查失败: %s",
                    ptype.value,
                    exc,
                )
        return results

    # ── 数据采集 ──────────────────────────────

    async def collect_all(
        self,
        sku_ids: dict[str, list[str]] | None = None,
    ) -> dict[str, list[AdData]]:
        """对所有已启用平台执行数据采集。

        Args:
            sku_ids: 按平台分组需要采集的 SKU ID, None 表示全部。

        Returns:
            按平台分组的采集结果。
        """
        results: dict[str, list[AdData]] = {}
        for adapter in self.get_enabled_adapters():
            ptype = adapter.config.platform.value
            platform_skus = (
                sku_ids.get(ptype) if sku_ids else None
            )
            try:
                data = await adapter.collect_ad_data(sku_ids=platform_skus)
                results[ptype] = data
                logger.info(
                    "platform_sync: %s 采集完成, 共 %d 条",
                    ptype,
                    len(data),
                )
            except Exception as exc:
                results[ptype] = []
                logger.error(
                    "platform_sync: %s 采集失败: %s",
                    ptype,
                    exc,
                )
        return results

    # ── 平台管理 ──────────────────────────────

    async def enable_platform(self, platform_type: PlatformType) -> bool:
        """启用指定平台。"""
        adapter = self._adapters.get(platform_type)
        if adapter is None:
            logger.warning("platform_sync: 未知平台 %s", platform_type.value)
            return False
        adapter.config.enabled = True
        logger.info("platform_sync: 已启用平台 %s", platform_type.value)
        return True

    async def disable_platform(self, platform_type: PlatformType) -> bool:
        """禁用指定平台。"""
        adapter = self._adapters.get(platform_type)
        if adapter is None:
            logger.warning("platform_sync: 未知平台 %s", platform_type.value)
            return False
        adapter.config.enabled = False
        logger.info("platform_sync: 已禁用平台 %s", platform_type.value)
        return True

    async def reconnect_platform(self, platform_type: PlatformType) -> bool:
        """重新连接指定平台。"""
        adapter = self._adapters.get(platform_type)
        if adapter is None:
            return False
        return await adapter.reconnect()


# ── 全局单例 ────────────────────────────────

_platform_sync: PlatformSyncService | None = None


def get_platform_sync() -> PlatformSyncService:
    """获取全局 PlatformSyncService 单例。"""
    global _platform_sync
    if _platform_sync is None:
        _platform_sync = PlatformSyncService()
    return _platform_sync


def init_platform_sync() -> PlatformSyncService:
    """初始化全局 PlatformSyncService (可重复调用，幂等)。"""
    global _platform_sync
    if _platform_sync is None:
        _platform_sync = PlatformSyncService()
    return _platform_sync
