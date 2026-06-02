"""Tests for PluginLoader — 加载、发现、生命周期."""
from __future__ import annotations

from App.plugins.hello_plugin import HelloPlugin


class TestPluginBase:
    def test_metadata_must_be_defined(self):
        """Every plugin subclass must define metadata."""
        plugin = HelloPlugin()
        meta = plugin.metadata
        assert meta.name == "hello_plugin"
        assert meta.version == "1.0.0"

    def test_lifecycle_states(self):
        """PluginBase lifecycle: init → start → stop."""
        plugin = HelloPlugin()
        assert not plugin.is_initialized
        assert not plugin.is_started

    async def test_init_start_stop(self):
        plugin = HelloPlugin()
        await plugin.init()
        assert plugin.is_initialized
        assert not plugin.is_started

        await plugin.start()
        assert plugin.is_started

        await plugin.stop()
        assert not plugin.is_initialized
        assert not plugin.is_started

    async def test_health_check(self):
        plugin = HelloPlugin()
        health = await plugin.health_check()
        assert health["status"] == "unhealthy"

        await plugin.init()
        health = await plugin.health_check()
        assert health["status"] == "degraded"

        await plugin.start()
        health = await plugin.health_check()
        assert health["status"] == "healthy"

    def test_api_context(self):
        plugin = HelloPlugin()
        assert plugin.api_context == {}
        plugin.api_context = {"db": "mock"}
        assert plugin.api_context["db"] == "mock"

    async def test_process_default_returns_none(self):
        plugin = HelloPlugin()
        result = await plugin.process(None, "SKU001", {})
        assert result is None
