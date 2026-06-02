"""Plugin system tests — base class, sandbox, loader, and registry.

Usage:
    pytest tests/test_plugins.py -v
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest import IsolatedAsyncioTestCase

from App.plugins.base import PluginBase, PluginMetadata
from App.plugins.hello_plugin import HelloPlugin
from App.services.plugin_loader import (
    BLOCKED_MODULES,
    SAFE_MODULES,
    PluginLoader,
    PluginStatus,
    PluginState,
    RestrictedImportError,
    _is_safe_module,
    _create_sandbox_globals,
)


# ============================================================
# PluginBase Tests
# ============================================================


class PluginBaseTests(IsolatedAsyncioTestCase):
    """Test the PluginBase abstract class with a concrete implementation."""

    async def asyncSetUp(self) -> None:
        self.plugin = HelloPlugin()

    def test_metadata(self) -> None:
        """Plugin should expose metadata."""
        meta = self.plugin.metadata
        self.assertEqual(meta.name, "hello_plugin")
        self.assertEqual(meta.version, "1.0.0")
        self.assertIsInstance(meta, PluginMetadata)

    def test_initial_state(self) -> None:
        """Plugin should start uninitialized."""
        self.assertFalse(self.plugin.is_initialized)
        self.assertFalse(self.plugin.is_started)

    async def test_init_lifecycle(self) -> None:
        """Init should set initialized flag."""
        self.assertFalse(self.plugin.is_initialized)
        await self.plugin.init()
        self.assertTrue(self.plugin.is_initialized)
        self.assertFalse(self.plugin.is_started)

    async def test_start_lifecycle(self) -> None:
        """Start should set started flag."""
        await self.plugin.init()
        await self.plugin.start()
        self.assertTrue(self.plugin.is_initialized)
        self.assertTrue(self.plugin.is_started)

    async def test_stop_lifecycle(self) -> None:
        """Stop should clear flags."""
        await self.plugin.init()
        await self.plugin.start()
        await self.plugin.stop()
        self.assertFalse(self.plugin.is_initialized)
        self.assertFalse(self.plugin.is_started)

    async def test_full_lifecycle(self) -> None:
        """Full init -> start -> stop cycle."""
        await self.plugin.init()
        self.assertTrue(self.plugin.is_initialized)

        await self.plugin.start()
        self.assertTrue(self.plugin.is_started)

        await self.plugin.stop()
        self.assertFalse(self.plugin.is_started)
        self.assertFalse(self.plugin.is_initialized)

    async def test_health_check_before_init(self) -> None:
        """Health check before init should report unhealthy."""
        result = await self.plugin.health_check()
        self.assertEqual(result["status"], "unhealthy")

    async def test_health_check_after_init_before_start(self) -> None:
        """Health check after init but before start should report degraded."""
        await self.plugin.init()
        result = await self.plugin.health_check()
        self.assertEqual(result["status"], "degraded")

    async def test_health_check_after_start(self) -> None:
        """Health check after start should report healthy."""
        await self.plugin.init()
        await self.plugin.start()
        result = await self.plugin.health_check()
        self.assertEqual(result["status"], "healthy")

    def test_api_context_get_set(self) -> None:
        """API context should be settable and retrievable."""
        ctx = {"db": "mock_db", "logger": "mock_logger"}
        self.plugin.api_context = ctx
        self.assertEqual(self.plugin.api_context, ctx)

    async def test_api_context_empty_by_default(self) -> None:
        """API context should be empty by default."""
        self.assertEqual(self.plugin.api_context, {})


# ============================================================
# Sandbox Tests
# ============================================================


class SandboxTests(IsolatedAsyncioTestCase):
    """Test the sandbox execution environment."""

    def test_safe_modules_allowed(self) -> None:
        """Safe modules should pass the check."""
        for mod in ["json", "datetime", "math", "typing"]:
            self.assertTrue(_is_safe_module(mod), f"{mod} should be safe")

    def test_blocked_modules_rejected(self) -> None:
        """Blocked modules should fail the check."""
        for mod in ["os", "subprocess", "socket", "ctypes"]:
            self.assertFalse(_is_safe_module(mod), f"{mod} should be blocked")

    def test_safe_submodule_allowed(self) -> None:
        """Submodules of safe modules should be allowed."""
        self.assertTrue(_is_safe_module("json.decoder"))
        self.assertTrue(_is_safe_module("datetime.timedelta"))

    def test_blocked_submodule_rejected(self) -> None:
        """Submodules of blocked modules should be rejected."""
        self.assertFalse(_is_safe_module("os.path"))
        self.assertFalse(_is_safe_module("os.environ"))

    def test_private_module_rejected(self) -> None:
        """Private modules (underscore-prefixed) should be rejected."""
        self.assertFalse(_is_safe_module("_internal"))
        self.assertFalse(_is_safe_module("__future__"))

    def test_unknown_module_rejected(self) -> None:
        """Unknown modules should be rejected."""
        self.assertFalse(_is_safe_module("requests"))
        self.assertFalse(_is_safe_module("aiohttp"))

    def test_sandbox_globals_has_api_context(self) -> None:
        """Sandbox globals should include api_context."""
        ctx = {"db": "test"}
        globals_dict = _create_sandbox_globals(ctx)
        self.assertEqual(globals_dict["api_context"], ctx)

    def test_sandbox_globals_no_dangerous_builtins(self) -> None:
        """Dangerous builtins should not be in sandbox globals."""
        globals_dict = _create_sandbox_globals({})
        builtins = globals_dict["__builtins__"]
        for dangerous in ("exec", "eval", "compile", "open", "__import__"):
            # __import__ is replaced, not removed
            if dangerous == "__import__":
                self.assertIn(dangerous, builtins)
                # but it should be our safe wrapper
                self.assertTrue(
                    callable(builtins[dangerous]),
                    "__import__ should be callable"
                )
            else:
                self.assertNotIn(dangerous, builtins,
                                 f"{dangerous} should not be in builtins")

    def test_sandbox_import_function_is_restricted(self) -> None:
        """The __import__ in sandbox should block dangerous imports."""
        globals_dict = _create_sandbox_globals({})
        safe_import = globals_dict["__builtins__"]["__import__"]

        # Should raise RestrictedImportError for blocked modules
        with self.assertRaises(RestrictedImportError):
            safe_import("os")

        with self.assertRaises(RestrictedImportError):
            safe_import("subprocess")

        # Should NOT raise for safe modules
        try:
            safe_import("json")
        except RestrictedImportError:
            self.fail("safe_import raised RestrictedImportError for safe module 'json'")


# ============================================================
# PluginLoader Tests
# ============================================================


class PluginLoaderTests(IsolatedAsyncioTestCase):
    """Test the PluginLoader class."""

    async def asyncSetUp(self) -> None:
        """Create a temporary plugin directory for testing."""
        self.temp_dir = tempfile.mkdtemp(prefix="plugin_test_")
        self.loader = PluginLoader(self.temp_dir, auto_enable=True)

    async def asyncTearDown(self) -> None:
        """Clean up temporary files."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    async def test_discover_empty_dir(self) -> None:
        """Discover on empty directory should return empty list."""
        discovered = await self.loader.discover()
        self.assertEqual(discovered, [])

    async def test_discover_no_py_files(self) -> None:
        """Discover should ignore non-.py files."""
        # Create a non-py file
        test_txt = os.path.join(self.temp_dir, "note.txt")
        with open(test_txt, "w") as f:
            f.write("not a plugin")

        discovered = await self.loader.discover()
        self.assertEqual(discovered, [])

    async def test_discover_ignores_init(self) -> None:
        """Discover should ignore __init__.py."""
        init_file = os.path.join(self.temp_dir, "__init__.py")
        with open(init_file, "w") as f:
            f.write("# package")

        discovered = await self.loader.discover()
        self.assertEqual(discovered, [])

    async def test_discover_finds_plugin(self) -> None:
        """Discover should find .py plugin files."""
        plugin_file = os.path.join(self.temp_dir, "test_plugin.py")
        with open(plugin_file, "w") as f:
            f.write("")
        # Copy the hello_plugin.py to our temp dir
        hello_content = open(
            os.path.join(os.path.dirname(__file__), "..", "App", "plugins", "hello_plugin.py"),
            encoding="utf-8"
        ).read()
        # But hello_plugin imports from App.plugins.base, which won't work in temp dir
        # Let's fix this: write a simple self-contained plugin
        plugin_content = '''
from App.plugins.base import PluginBase, PluginMetadata


class TempPlugin(PluginBase):
    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(name="temp_plugin", version="0.1.0")

    async def init(self):
        await super().init()

    async def start(self):
        await super().start()

    async def stop(self):
        await super().stop()
'''
        with open(plugin_file, "w", encoding="utf-8") as f:
            f.write(plugin_content)

        discovered = await self.loader.discover()
        self.assertIn("test_plugin", discovered)

    async def test_load_and_start_plugin(self) -> None:
        """Load and start a plugin from the temp directory."""
        # We need to actually test this by loading from App.plugins.hello_plugin
        # Instead of temp dir approach, test via direct loading

        # For the temp dir, write a self-contained plugin
        plugin_file = os.path.join(self.temp_dir, "simple_plugin.py")
        # This plugin needs to inherit from PluginBase which is importable
        plugin_content = '''
from App.plugins.base import PluginBase, PluginMetadata


class SimplePlugin(PluginBase):
    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(name="simple_plugin", version="1.0.0")

    async def init(self):
        await super().init()

    async def start(self):
        await super().start()

    async def stop(self):
        await super().stop()

    async def health_check(self):
        return {"status": "healthy", "message": "simple"}
'''
        with open(plugin_file, "w", encoding="utf-8") as f:
            f.write(plugin_content)

        await self.loader.discover()
        success = await self.loader.load_plugin("simple_plugin")
        # The import of App.plugins.base should work since App is in sys.path
        self.assertTrue(success, "Plugin should load successfully")

        plugin = self.loader.get_plugin("simple_plugin")
        self.assertIsNotNone(plugin)
        self.assertEqual(plugin.metadata.name, "simple_plugin")

        # Start
        start_ok = await self.loader.start_plugin("simple_plugin")
        self.assertTrue(start_ok)
        self.assertTrue(plugin.is_started)

    async def test_load_nonexistent_plugin(self) -> None:
        """Load a nonexistent plugin should return False."""
        success = await self.loader.load_plugin("nonexistent")
        self.assertFalse(success)

    async def test_registry_status_after_load(self) -> None:
        """Registry status should reflect loaded plugin info."""
        plugin_file = os.path.join(self.temp_dir, "status_plugin.py")
        with open(plugin_file, "w", encoding="utf-8") as f:
            f.write('''
from App.plugins.base import PluginBase, PluginMetadata


class StatusPlugin(PluginBase):
    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(name="status_plugin", version="1.0.0")

    async def init(self):
        await super().init()

    async def start(self):
        await super().start()

    async def stop(self):
        await super().stop()
''')

        await self.loader.discover()
        await self.loader.load_plugin("status_plugin")

        status_list = self.loader.get_registry_status()
        self.assertEqual(len(status_list), 1)
        entry = status_list[0]
        self.assertEqual(entry["name"], "status_plugin")
        self.assertEqual(entry["state"], "initialized")
        self.assertIsNotNone(entry["plugin_metadata"])

    async def test_disable_enable_plugin(self) -> None:
        """Disable and enable should toggle plugin status."""
        plugin_file = os.path.join(self.temp_dir, "toggle_plugin.py")
        with open(plugin_file, "w", encoding="utf-8") as f:
            f.write('''
from App.plugins.base import PluginBase, PluginMetadata


class TogglePlugin(PluginBase):
    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(name="toggle_plugin", version="1.0.0")

    async def init(self):
        await super().init()
''')

        await self.loader.discover()
        await self.loader.load_plugin("toggle_plugin")

        record = self.loader.get_registry()["toggle_plugin"]
        self.assertEqual(record.status, PluginStatus.ENABLED)

        self.loader.disable_plugin("toggle_plugin")
        self.assertEqual(record.status, PluginStatus.DISABLED)

        self.loader.enable_plugin("toggle_plugin")
        self.assertEqual(record.status, PluginStatus.ENABLED)

    async def test_disable_nonexistent_plugin(self) -> None:
        """Disable nonexistent plugin should return False."""
        result = self.loader.disable_plugin("nonexistent")
        self.assertFalse(result)

    async def test_get_plugin_status(self) -> None:
        """get_plugin_status should return correct status."""
        self.assertIsNone(self.loader.get_plugin_status("nonexistent"))

    async def test_loaded_count(self) -> None:
        """Loaded count should reflect total loaded plugins."""
        self.assertEqual(self.loader.get_loaded_count(), 0)

        # Write two plugins
        for name in ["alpha", "beta"]:
            fpath = os.path.join(self.temp_dir, f"{name}.py")
            with open(fpath, "w", encoding="utf-8") as f:
                f.write(f'''
from App.plugins.base import PluginBase, PluginMetadata


class {name.capitalize()}Plugin(PluginBase):
    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(name="{name}", version="1.0.0")

    async def init(self):
        await super().init()
''')

        await self.loader.discover()
        await self.loader.load_all()
        self.assertEqual(self.loader.get_loaded_count(), 2)

    async def test_unload_plugin(self) -> None:
        """Unload should remove plugin from registry."""
        plugin_file = os.path.join(self.temp_dir, "removable.py")
        with open(plugin_file, "w", encoding="utf-8") as f:
            f.write('''
from App.plugins.base import PluginBase, PluginMetadata


class RemovablePlugin(PluginBase):
    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(name="removable", version="1.0.0")
''')

        await self.loader.discover()
        await self.loader.load_plugin("removable")
        self.assertEqual(self.loader.get_loaded_count(), 1)

        unloaded = await self.loader.unload_plugin("removable")
        self.assertTrue(unloaded)
        self.assertEqual(self.loader.get_loaded_count(), 0)

    async def test_health_check_via_loader(self) -> None:
        """Health check through loader should work."""
        plugin_file = os.path.join(self.temp_dir, "healthy.py")
        with open(plugin_file, "w", encoding="utf-8") as f:
            f.write('''
from App.plugins.base import PluginBase, PluginMetadata


class HealthyPlugin(PluginBase):
    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(name="healthy", version="1.0.0")

    async def health_check(self):
        return {"status": "healthy", "since": "today"}
''')

        await self.loader.discover()
        await self.loader.load_plugin("healthy")
        await self.loader.start_plugin("healthy")

        result = await self.loader.health_check("healthy")
        self.assertEqual(result["status"], "healthy")

    async def test_health_check_unloaded_plugin(self) -> None:
        """Health check for unloaded plugin should return unhealthy."""
        result = await self.loader.health_check("nonexistent")
        self.assertEqual(result["status"], "unhealthy")

    async def test_reload_plugin(self) -> None:
        """Reload should stop, unload, and reload."""
        plugin_file = os.path.join(self.temp_dir, "reloadable.py")
        with open(plugin_file, "w", encoding="utf-8") as f:
            f.write('''
from App.plugins.base import PluginBase, PluginMetadata


class ReloadPlugin(PluginBase):
    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(name="reloadable", version="1.0.0")
''')

        await self.loader.discover()
        await self.loader.load_plugin("reloadable")
        self.assertEqual(self.loader.get_loaded_count(), 1)

        reloaded = await self.loader.reload_plugin("reloadable")
        self.assertTrue(reloaded)
        self.assertEqual(self.loader.get_loaded_count(), 1)

    async def test_set_api_context(self) -> None:
        """API context should propagate to loaded plugins."""
        plugin_file = os.path.join(self.temp_dir, "ctx_plugin.py")
        with open(plugin_file, "w", encoding="utf-8") as f:
            f.write('''
from App.plugins.base import PluginBase, PluginMetadata


class CtxPlugin(PluginBase):
    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(name="ctx_plugin", version="1.0.0")
''')

        await self.loader.discover()
        await self.loader.load_plugin("ctx_plugin")

        self.loader.set_api_context({"db_session": "mock", "logger": "mock"})
        plugin = self.loader.get_plugin("ctx_plugin")
        self.assertIsNotNone(plugin)
        self.assertEqual(plugin.api_context.get("db_session"), "mock")

    async def test_stop_all(self) -> None:
        """Stop all should stop all started plugins."""
        plugin_file = os.path.join(self.temp_dir, "stoppable.py")
        with open(plugin_file, "w", encoding="utf-8") as f:
            f.write('''
from App.plugins.base import PluginBase, PluginMetadata


class StoppablePlugin(PluginBase):
    def __init__(self):
        super().__init__()
        self.stop_called = False

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(name="stoppable", version="1.0.0")

    async def stop(self):
        self.stop_called = True
        await super().stop()
''')

        await self.loader.discover()
        await self.loader.load_plugin("stoppable")
        await self.loader.start_plugin("stoppable")

        results = await self.loader.stop_all()
        self.assertIn("stoppable", results)
        self.assertTrue(results["stoppable"])

        plugin = self.loader.get_plugin("stoppable")
        self.assertFalse(plugin.is_started)
