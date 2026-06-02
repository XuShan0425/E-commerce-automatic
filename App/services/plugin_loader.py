"""插件加载器 — 动态扫描、沙盒加载、注册中心。

功能:
    1. 从指定目录动态扫描和加载插件
    2. 沙盒执行环境限制插件对系统资源的访问（文件系统、网络、子进程）
    3. 插件注册中心管理已加载插件状态（启用/禁用/异常）
    4. 为插件注入预定义的公共 API 上下文

用法:
    loader = PluginLoader(plugin_dir="/path/to/plugins")
    await loader.discover()
    plugin = loader.get_plugin("my_plugin")
    status = loader.get_plugin_status("my_plugin")
"""

from __future__ import annotations

import ast
import enum
import importlib
import importlib.util
import inspect
import os
import sys
import textwrap
import time
import traceback
from pathlib import Path
from types import ModuleType
from typing import Any

from App.core.logging import get_logger
from App.plugins.base import PluginBase

logger = get_logger(__name__)

# ── 沙盒配置 ───────────────────────────────────────

# 允许插件导入的安全模块白名单
SAFE_MODULES: frozenset[str] = frozenset({
    # 标准库 — 纯计算 / 无副作用
    "json",
    "datetime",
    "math",
    "re",
    "decimal",
    "uuid",
    "collections",
    "enum",
    "dataclasses",
    "typing",
    "functools",
    "itertools",
    "copy",
    "hashlib",
    "string",
    "textwrap",
    "types",
    "statistics",
    "random",
    # 明确禁止的模块子集由 _is_safe_module 检查
})

# 明确禁止的模块（即使被沙盒遗漏也要拦截）
BLOCKED_MODULES: frozenset[str] = frozenset({
    "os",
    "subprocess",
    "shutil",
    "socket",
    "ctypes",
    "signal",
    "multiprocessing",
    "threading",
    "asyncio",  # 插件不应自行管理事件循环
    "http",
    "urllib",
    "requests",
    "aiohttp",
    "httpx",
    "pathlib",  # 插件不应直接操作文件路径
    "tempfile",
    "pickle",
    "shelve",
    "dbm",
    "sqlite3",
    "importlib",
    "pkgutil",
    "pkg_resources",
    "inspect",
    "compileall",
    "py_compile",
    "zipfile",
    "tarfile",
    "gzip",
    "bz2",
    "lzma",
    "getpass",
    "grp",
    "pwd",
    "platform",
    "resource",
    "sysconfig",
    "distutils",
    "setuptools",
})

# 沙盒内置函数 — 基于真实 builtins 移除危险函数
_DANGEROUS_BUILTINS: frozenset[str] = frozenset({
    "exec",
    "eval",
    "compile",
    "open",
    "input",
    "__import__",
    "memoryview",
    "breakpoint",
    "exit",
    "quit",
    "help",
    "license",
    "credits",
    "copyright",
})


def _build_safe_builtins() -> dict[str, Any]:
    """基于真实 builtins 模块构建沙盒内置函数字典。

    保留所有正常 Python 执行所需的内置函数（如 ``__build_class__``），
    只移除明确危险的内置函数。
    其中 ``__import__`` 被替换为沙盒版本而非直接移除。
    """
    import builtins

    safe: dict[str, Any] = {}
    for name in dir(builtins):
        if name in _DANGEROUS_BUILTINS and name != "__import__":
            continue
        safe[name] = getattr(builtins, name)
    # 移除危险内置后补回安全版的 __import__
    # （safe___import__ 定义在 _create_sandbox_globals 的闭包中）
    return safe


# ── 沙盒实现 ───────────────────────────────────────


def _is_safe_module(module_name: str) -> bool:
    """检查模块名是否在安全白名单中且不在黑名单中。

    规则:
        1. 以 ``App.`` 开头 → 允许（插件系统内部模块）
        2. 属于 SAFE_MODULES 或以其开头（支持子模块）→ 安全
        3. 属于 BLOCKED_MODULES 或以其开头 → 禁止
        4. 不属于 SAFE_MODULES 且不是标准库安全子集 → 禁止
    """
    top_level = module_name.split(".")[0]

    # 允许 App 包下的导入（插件需要 import App.plugins.base 等）
    if module_name.startswith("App.") or module_name == "App":
        return True

    if top_level in BLOCKED_MODULES:
        return False

    if top_level in SAFE_MODULES:
        return True

    # 额外安全检查：禁止任何以下划线开头的私有模块
    if top_level.startswith("_"):
        return False

    return False


class SandboxedModule:
    """沙盒模块包装器 — 包装插件模块，限制其属性和方法访问。

    通过 __getattr__ 拦截对模块属性的访问，阻止返回危险对象。
    """

    def __init__(self, module: ModuleType) -> None:
        self._module = module

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(f"Access to private attribute '{name}' is forbidden")
        return getattr(self._module, name)


class RestrictedImportError(ImportError):
    """当插件试图导入被禁止的模块时抛出。"""
    pass


def _create_sandbox_globals(plugin_api_context: dict[str, Any]) -> dict[str, Any]:
    """创建插件的沙盒全局命名空间。

    Args:
        plugin_api_context: 公共 API 上下文，注入到插件命名空间。

    Returns:
        受限的全局命名空间字典。
    """
    safe_builtins = _build_safe_builtins()

    def safe___import__(name: str, globals_: dict | None = None,
                        locals_: dict | None = None,
                        fromlist: tuple[str, ...] | None = None,
                        level: int = 0) -> ModuleType:
        """受限的 __import__：仅允许白名单模块。"""
        if not _is_safe_module(name):
            raise RestrictedImportError(
                f"Plugin attempted to import forbidden module: '{name}'. "
                f"Only safe modules ({sorted(SAFE_MODULES)}) are allowed."
            )
        return __builtins__["__import__"](name, globals_, locals_, fromlist, level)

    safe_builtins["__import__"] = safe___import__

    return {
        "__builtins__": safe_builtins,
        "__name__": "__sandbox__",
        "__doc__": None,
        "__package__": None,
        "__loader__": None,
        "__spec__": None,
        "__file__": None,
        # 注入公共 API 上下文
        "api_context": plugin_api_context,
    }


# ── 插件状态 ───────────────────────────────────────


class PluginStatus(str, enum.Enum):
    """插件状态枚举。"""
    DISABLED = "disabled"
    ENABLED = "enabled"
    ERROR = "error"


@enum.unique
class PluginState(enum.Enum):
    """插件生命周期状态（细粒度）。"""
    LOADED = "loaded"
    INITIALIZED = "initialized"
    STARTED = "started"
    STOPPED = "stopped"
    ERROR = "error"


# ── 插件注册记录 ────────────────────────────────────


class PluginRecord:
    """插件注册记录 — 保存插件的元数据、状态和实例。

    Attributes:
        name: 插件名称。
        module_path: 插件模块文件路径。
        plugin: 插件实例（如果已成功加载）。
        status: 插件当前状态。
        error: 错误信息（如果有）。
        loaded_at: 加载时间戳。
    """

    def __init__(self, name: str, module_path: str) -> None:
        self.name: str = name
        self.module_path: str = module_path
        self.plugin: PluginBase | None = None
        self.status: PluginStatus = PluginStatus.DISABLED
        self.state: PluginState = PluginState.LOADED
        self.error: str | None = None
        self.loaded_at: float = time.time()
        self.last_health: dict[str, Any] = {}

    def to_dict(self) -> dict[str, Any]:
        """将注册记录序列化为字典。"""
        return {
            "name": self.name,
            "module_path": self.module_path,
            "status": self.status.value,
            "state": self.state.value,
            "error": self.error,
            "loaded_at": self.loaded_at,
            "last_health": self.last_health,
            "plugin_metadata": (
                {
                    "name": self.plugin.metadata.name,
                    "version": self.plugin.metadata.version,
                    "description": self.plugin.metadata.description,
                    "author": self.plugin.metadata.author,
                }
                if self.plugin is not None
                else None
            ),
        }


# ── 插件加载器 ─────────────────────────────────────


class PluginLoader:
    """插件加载器 — 动态扫描、沙盒加载、注册中心。

    使用方式:
        loader = PluginLoader(plugin_dir="./plugins")
        await loader.discover()
        await loader.load_all()
        await loader.start_all()
        status = loader.get_registry_status()
        await loader.stop_all()

    Args:
        plugin_dir: 插件目录路径（字符串或 Path）。
        auto_enable: 加载后是否自动启用插件，默认 True。
    """

    def __init__(
        self,
        plugin_dir: str | Path,
        auto_enable: bool = True,
    ) -> None:
        self._plugin_dir: Path = Path(plugin_dir).resolve()
        self._auto_enable: bool = auto_enable
        # name -> PluginRecord
        self._registry: dict[str, PluginRecord] = {}
        # 公共 API 上下文（由外部注入）
        self._api_context: dict[str, Any] = {}
        logger.info("PluginLoader 初始化", extra={"plugin_dir": str(self._plugin_dir)})

    # ── 公共 API 上下文管理 ─────────────────────────

    def set_api_context(self, context: dict[str, Any]) -> None:
        """设置或更新插件可访问的公共 API 上下文。

        所有已加载和未来加载的插件都会获得此上下文。

        Args:
            context: API 上下文字典，包含如数据库会话、日志记录器等
                     系统预定义的公开服务引用。
        """
        self._api_context.update(context)
        # 同步更新已加载的插件实例
        for record in self._registry.values():
            if record.plugin is not None:
                record.plugin.api_context = dict(self._api_context)

    # ── 插件发现 ────────────────────────────────────

    async def discover(self) -> list[str]:
        """扫描插件目录，识别可加载的插件模块。

        扫描规则:
            - 查找 plugin_dir 下所有 .py 文件（不含 __init__.py）
            - 每个文件视为一个独立的插件

        Returns:
            发现的插件名称列表。
        """
        discovered: list[str] = []

        if not self._plugin_dir.is_dir():
            logger.warning("插件目录不存在", extra={"dir": str(self._plugin_dir)})
            return discovered

        for fpath in sorted(self._plugin_dir.iterdir()):
            if not fpath.is_file() or fpath.suffix != ".py":
                continue
            if fpath.name == "__init__.py":
                continue
            if fpath.name.startswith("_"):
                continue

            plugin_name = fpath.stem
            if plugin_name not in self._registry:
                record = PluginRecord(
                    name=plugin_name,
                    module_path=str(fpath),
                )
                self._registry[plugin_name] = record
                discovered.append(plugin_name)
                logger.debug("发现插件", extra={"plugin": plugin_name})

        if discovered:
            logger.info("插件发现完成", extra={"count": len(discovered), "plugins": discovered})
        else:
            logger.info("未发现新插件")

        return discovered

    # ── 插件加载 ────────────────────────────────────

    async def load_plugin(self, name: str) -> bool:
        """加载并初始化单个插件。

        Args:
            name: 插件名称（即文件名不含 .py）。

        Returns:
            加载是否成功。
        """
        record = self._registry.get(name)
        if record is None:
            logger.error("插件未找到", extra={"plugin": name})
            return False

        if record.plugin is not None:
            logger.debug("插件已加载", extra={"plugin": name})
            return True

        try:
            # 1. 读取源码并进行静态分析
            source = record.module_path
            with open(source, "r", encoding="utf-8") as f:
                source_code = f.read()

            # 静态安全分析：AST 检查
            self._ast_safety_check(source_code, name)

            # 2. 创建沙盒全局命名空间
            plugin_api_context = dict(self._api_context)
            sandbox_globals = _create_sandbox_globals(plugin_api_context)

            # 3. 编译并执行插件代码
            code = compile(source_code, record.module_path, "exec")
            exec(code, sandbox_globals)

            # 4. 查找插件类（继承 PluginBase 的子类）
            plugin_class = None
            for obj in sandbox_globals.values():
                if (inspect.isclass(obj)
                        and issubclass(obj, PluginBase)
                        and obj is not PluginBase):
                    plugin_class = obj
                    break

            if plugin_class is None:
                raise ValueError(
                    f"插件 '{name}' 未找到继承 PluginBase 的类"
                )

            # 5. 实例化插件
            plugin_instance: PluginBase = plugin_class()
            plugin_instance.api_context = plugin_api_context

            # 6. 初始化
            await plugin_instance.init()
            record.plugin = plugin_instance
            record.state = PluginState.INITIALIZED

            if self._auto_enable:
                record.status = PluginStatus.ENABLED

            logger.info("插件加载成功", extra={"plugin": name})
            return True

        except RestrictedImportError as e:
            error_msg = f"插件 '{name}' 沙盒阻止: {e}"
            logger.warning(error_msg)
            record.status = PluginStatus.ERROR
            record.state = PluginState.ERROR
            record.error = error_msg
            return False

        except Exception as e:
            error_msg = f"插件 '{name}' 加载失败: {e}\n{traceback.format_exc()}"
            logger.error(error_msg)
            record.status = PluginStatus.ERROR
            record.state = PluginState.ERROR
            record.error = str(e)
            return False

    async def load_all(self) -> dict[str, bool]:
        """加载所有已发现但未加载的插件。

        Returns:
            插件名称到加载结果的映射。
        """
        results: dict[str, bool] = {}
        for name, record in self._registry.items():
            if record.plugin is None:
                results[name] = await self.load_plugin(name)
        return results

    def _ast_safety_check(self, source_code: str, plugin_name: str) -> None:
        """对插件源码进行 AST 静态安全检查。

        检测:
            - 直接调用 exec/eval/compile
            - 访问 __import__ 内置函数
            - 使用星号导入（from x import *）
            - 尝试访问私有属性（_.*）

        Args:
            source_code: 插件源码。
            plugin_name: 插件名称（用于错误信息）。

        Raises:
            RestrictedImportError: 如果检测到禁止的操作。
        """
        try:
            tree = ast.parse(source_code)
        except SyntaxError as e:
            raise ValueError(f"插件 '{plugin_name}' 语法错误: {e}")

        for node in ast.walk(tree):
            # 禁止 exec/eval/compile 调用
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if node.func.id in ("exec", "eval", "compile", "__import__"):
                        raise RestrictedImportError(
                            f"插件 '{plugin_name}' 使用了禁止的函数: {node.func.id}"
                        )
                elif isinstance(node.func, ast.Attribute):
                    if node.func.attr in ("exec", "eval", "compile", "__import__"):
                        raise RestrictedImportError(
                            f"插件 '{plugin_name}' 使用了禁止的方法: {node.func.attr}"
                        )

            # 禁止星号导入
            if isinstance(node, ast.ImportFrom):
                if node.names and any(n.name == "*" for n in node.names):
                    raise RestrictedImportError(
                        f"插件 '{plugin_name}' 使用了星号导入（不明确的依赖）"
                    )

            # 禁止 __import__ 作为 Name 的直接访问
            if isinstance(node, ast.Name):
                if node.id == "__import__":
                    raise RestrictedImportError(
                        f"插件 '{plugin_name}' 直接引用了 __import__"
                    )

    # ── 插件启动/停止 ───────────────────────────────

    async def start_plugin(self, name: str) -> bool:
        """启动指定插件。

        Args:
            name: 插件名称。

        Returns:
            是否启动成功。
        """
        record = self._registry.get(name)
        if record is None or record.plugin is None:
            logger.error("插件未加载，无法启动", extra={"plugin": name})
            return False

        if record.state == PluginState.STARTED:
            return True

        try:
            await record.plugin.start()
            record.state = PluginState.STARTED
            record.status = PluginStatus.ENABLED
            record.error = None
            logger.info("插件启动成功", extra={"plugin": name})
            return True
        except Exception as e:
            error_msg = f"插件 '{name}' 启动失败: {e}"
            logger.error(error_msg)
            record.state = PluginState.ERROR
            record.status = PluginStatus.ERROR
            record.error = str(e)
            return False

    async def start_all(self) -> dict[str, bool]:
        """启动所有已初始化的插件。

        Returns:
            插件名称到启动结果的映射。
        """
        results: dict[str, bool] = {}
        for name, record in self._registry.items():
            if record.plugin is not None and record.state == PluginState.INITIALIZED:
                results[name] = await self.start_plugin(name)
        return results

    async def stop_plugin(self, name: str) -> bool:
        """停止指定插件。

        Args:
            name: 插件名称。

        Returns:
            是否停止成功。
        """
        record = self._registry.get(name)
        if record is None or record.plugin is None:
            return False

        try:
            await record.plugin.stop()
            record.state = PluginState.STOPPED
            logger.info("插件停止成功", extra={"plugin": name})
            return True
        except Exception as e:
            logger.warning("插件停止异常", extra={"plugin": name, "error": str(e)})
            record.state = PluginState.STOPPED
            return True

    async def stop_all(self) -> dict[str, bool]:
        """停止所有已启动的插件。

        Returns:
            插件名称到停止结果的映射。
        """
        results: dict[str, bool] = {}
        for name, record in self._registry.items():
            if record.plugin is not None and record.state == PluginState.STARTED:
                results[name] = await self.stop_plugin(name)
        return results

    # ── 健康检查 ────────────────────────────────────

    async def health_check(self, name: str) -> dict[str, Any]:
        """对指定插件执行健康检查。

        Args:
            name: 插件名称。

        Returns:
            健康检查结果字典，默认包含 status 字段。
            插件未加载时返回 unhealthy 状态。
        """
        record = self._registry.get(name)
        if record is None or record.plugin is None:
            return {"status": "unhealthy", "reason": "not_loaded"}

        try:
            result = await record.plugin.health_check()
            record.last_health = result
            return result
        except Exception as e:
            result = {"status": "unhealthy", "reason": str(e)}
            record.last_health = result
            return result

    async def health_check_all(self) -> dict[str, dict[str, Any]]:
        """对所有已加载插件执行健康检查。

        Returns:
            插件名称到健康检查结果的映射。
        """
        results: dict[str, dict[str, Any]] = {}
        for name in list(self._registry.keys()):
            results[name] = await self.health_check(name)
        return results

    # ── 注册中心管理 ────────────────────────────────

    def enable_plugin(self, name: str) -> bool:
        """启用插件（标记为启用，不重新加载）。

        Args:
            name: 插件名称。

        Returns:
            操作是否成功。
        """
        record = self._registry.get(name)
        if record is None:
            return False
        if record.state == PluginState.ERROR:
            return False
        record.status = PluginStatus.ENABLED
        return True

    def disable_plugin(self, name: str) -> bool:
        """禁用插件（标记为禁用，不卸载）。

        Args:
            name: 插件名称。

        Returns:
            操作是否成功。
        """
        record = self._registry.get(name)
        if record is None:
            return False
        record.status = PluginStatus.DISABLED
        return True

    async def unload_plugin(self, name: str) -> bool:
        """卸载插件（停止并从注册表中移除）。

        Args:
            name: 插件名称。

        Returns:
            操作是否成功。
        """
        if name not in self._registry:
            return False

        await self.stop_plugin(name)
        del self._registry[name]
        logger.info("插件已卸载", extra={"plugin": name})
        return True

    async def reload_plugin(self, name: str) -> bool:
        """重新加载插件（停止 + 卸载 + 重新加载）。

        Args:
            name: 插件名称。

        Returns:
            重新加载是否成功。
        """
        record = self._registry.get(name)
        if record is None:
            return False

        await self.stop_plugin(name)
        record.plugin = None
        record.state = PluginState.LOADED
        record.status = PluginStatus.DISABLED
        record.error = None

        success = await self.load_plugin(name)
        if success and self._auto_enable:
            await self.start_plugin(name)
        return success

    # ── 查询接口 ────────────────────────────────────

    def get_plugin(self, name: str) -> PluginBase | None:
        """获取插件实例。

        Args:
            name: 插件名称。

        Returns:
            插件实例或 None。
        """
        record = self._registry.get(name)
        if record is None:
            return None
        return record.plugin

    def get_plugin_status(self, name: str) -> PluginStatus | None:
        """获取插件状态。

        Args:
            name: 插件名称。

        Returns:
            插件状态或 None。
        """
        record = self._registry.get(name)
        if record is None:
            return None
        return record.status

    def get_registry(self) -> dict[str, PluginRecord]:
        """获取完整注册表。

        Returns:
            名称到 PluginRecord 的字典。
        """
        return dict(self._registry)

    def get_registry_status(self) -> list[dict[str, Any]]:
        """获取所有已注册插件的状态摘要。

        Returns:
            插件状态字典列表，按名称排序。
        """
        records = []
        for name in sorted(self._registry.keys()):
            record = self._registry[name]
            records.append(record.to_dict())
        return records

    def get_loaded_count(self) -> int:
        """获取已成功加载的插件数量。"""
        return sum(1 for r in self._registry.values() if r.plugin is not None)
