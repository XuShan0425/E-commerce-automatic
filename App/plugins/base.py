"""Plugin 基类 — 定义生命周期接口与元数据规范。

所有自定义插件必须继承 `PluginBase` 并实现生命周期方法。
插件通过 `self.api_context` 访问系统提供的公共 API。
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any


@dataclass
class PluginMetadata:
    """插件元数据。"""

    name: str
    version: str = "0.1.0"
    description: str = ""
    author: str = ""


class PluginBase(abc.ABC):
    """插件基类 — 所有插件必须继承此类。

    生命周期顺序：__init__ → init → start → (health_check)* → stop
    异常状态：若 init/start 抛出异常，插件被标记为 error。

    Attributes:
        metadata: 插件元数据（名称、版本等）。
        api_context: 系统注入的公共 API 上下文，插件通过此接口
                     访问预定义的服务（日志、数据库查询等）。
    """

    def __init__(self) -> None:
        self._initialized: bool = False
        self._started: bool = False
        self._api_context: dict[str, Any] = {}

    # ── 属性 ────────────────────────────────────────

    @property
    @abc.abstractmethod
    def metadata(self) -> PluginMetadata:
        """返回插件元数据。每个插件必须实现。"""
        ...

    @property
    def is_initialized(self) -> bool:
        """插件是否已完成初始化。"""
        return self._initialized

    @property
    def is_started(self) -> bool:
        """插件是否已启动。"""
        return self._started

    @property
    def api_context(self) -> dict[str, Any]:
        """获取公共 API 上下文。

        由插件加载器在注册时注入，包含插件可访问的系统服务引用。
        """
        return self._api_context

    @api_context.setter
    def api_context(self, ctx: dict[str, Any]) -> None:
        """设置公共 API 上下文（由加载器调用）。"""
        self._api_context = ctx

    # ── 生命周期方法 ────────────────────────────────

    async def init(self) -> None:
        """初始化插件。在加载后、启动前调用。

        子类可在此方法中执行配置加载、资源分配等一次性操作。
        抛出异常会使插件状态标记为 error。
        """
        self._initialized = True

    async def start(self) -> None:
        """启动插件。在初始化后调用。

        子类可在此方法中启动后台任务、注册回调等。
        抛出异常会使插件状态标记为 error。
        """
        self._started = True

    async def stop(self) -> None:
        """停止插件。在卸载前调用。

        子类应在此方法中清理资源、停止后台任务。
        此方法应尽量不抛出异常；若抛出，加载器会记录日志。
        """
        self._started = False
        self._initialized = False

    async def health_check(self) -> dict[str, Any]:
        """健康检查。返回插件当前运行状态。

        Returns:
            包含健康状态信息的字典，至少包含:
            - status: "healthy" | "degraded" | "unhealthy"
            - 可选的详细信息如 uptime, last_run, error_count 等。
        """
        if not self._initialized:
            return {"status": "unhealthy", "reason": "not_initialized"}
        if not self._started:
            return {"status": "degraded", "reason": "not_started"}
        return {"status": "healthy"}
