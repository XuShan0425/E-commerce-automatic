"""示例插件 — 用于测试的简单插件。"""
from App.plugins.base import PluginBase, PluginMetadata


class HelloPlugin(PluginBase):
    """一个简单的示例插件，用于验证插件系统的基本功能。"""

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="hello_plugin",
            version="1.0.0",
            description="示例插件，用于测试",
            author="test",
        )

    async def init(self) -> None:
        await super().init()

    async def start(self) -> None:
        await super().start()

    async def stop(self) -> None:
        await super().stop()
