"""单元测试 — PlatformAdapter 抽象基类、AmazonAdapter、PlatformSyncService."""

from __future__ import annotations

import json
from unittest import IsolatedAsyncioTestCase

from App.services.platform.base import (
    AdData,
    ExecutionAction,
    HealthCheckResult,
    PlatformAdapter,
    PlatformConfig,
    PlatformConnectionStatus,
    PlatformType,
)
from App.services.platform.amazon_adapter import AmazonAdapter
from App.services.platform_sync import PlatformSyncService, get_platform_sync


class PlatformTypesTests(IsolatedAsyncioTestCase):
    """Test platform type enums."""

    def test_platform_type_values(self) -> None:
        """PlatformType should have expected values."""
        self.assertEqual(PlatformType.ALIEXPRESS.value, "aliexpress")
        self.assertEqual(PlatformType.AMAZON.value, "amazon")

    def test_connection_status_values(self) -> None:
        """PlatformConnectionStatus should have expected values."""
        self.assertEqual(PlatformConnectionStatus.DISCONNECTED.value, "disconnected")
        self.assertEqual(PlatformConnectionStatus.CONNECTED.value, "connected")
        self.assertEqual(PlatformConnectionStatus.ERROR.value, "error")


class PlatformConfigTests(IsolatedAsyncioTestCase):
    """Test PlatformConfig data class."""

    def test_default_config(self) -> None:
        """PlatformConfig should have sensible defaults."""
        config = PlatformConfig(
            platform=PlatformType.AMAZON,
            label="Test",
        )
        self.assertTrue(config.enabled)
        self.assertEqual(config.cookie_status, PlatformConnectionStatus.DISCONNECTED)
        self.assertIsNone(config.last_sync_time)

    def test_config_with_extra(self) -> None:
        """PlatformConfig should support extra fields."""
        config = PlatformConfig(
            platform=PlatformType.ALIEXPRESS,
            label="Test",
            extra={"api_key": "test_123", "endpoint": "https://example.com"},
        )
        self.assertEqual(config.extra["api_key"], "test_123")


class AdDataTests(IsolatedAsyncioTestCase):
    """Test AdData data class."""

    def test_ad_data_defaults(self) -> None:
        """AdData should have zero defaults for numeric fields."""
        data = AdData(
            platform=PlatformType.AMAZON,
            sku_id="AMZ-001",
            snapshot_time="2026-06-01T10:00:00Z",
        )
        self.assertEqual(data.impressions, 0)
        self.assertEqual(data.clicks, 0)
        self.assertEqual(data.ctr, 0.0)
        self.assertEqual(data.orders, 0)
        self.assertEqual(data.ad_spend, 0.0)

    def test_ad_data_full(self) -> None:
        """AdData should accept all fields."""
        data = AdData(
            platform=PlatformType.AMAZON,
            sku_id="AMZ-001",
            snapshot_time="2026-06-01T10:00:00Z",
            impressions=1000,
            clicks=50,
            ctr=0.05,
            orders=5,
            conversion_rate=0.1,
            ad_spend=25.00,
            revenue=200.00,
            ad_type="sponsored_products",
        )
        self.assertEqual(data.ctr, 0.05)
        self.assertEqual(data.conversion_rate, 0.1)

    def test_ad_data_serializable(self) -> None:
        """AdData should be JSON-serializable."""
        data = AdData(
            platform=PlatformType.AMAZON,
            sku_id="AMZ-001",
            snapshot_time="2026-06-01T10:00:00Z",
            buyer_region_breakdown={"US": 0.6, "EU": 0.3, "OTHER": 0.1},
        )
        raw = json.dumps({
            "platform": data.platform.value,
            "sku_id": data.sku_id,
            "snapshot_time": data.snapshot_time,
            "impressions": data.impressions,
            "region": data.buyer_region_breakdown,
        })
        parsed = json.loads(raw)
        self.assertEqual(parsed["platform"], "amazon")
        self.assertEqual(parsed["region"]["US"], 0.6)


class PlatformAdapterBaseTests(IsolatedAsyncioTestCase):
    """Test PlatformAdapter base class behavior."""

    def test_cannot_instantiate_abc(self) -> None:
        """PlatformAdapter should not be directly instantiable."""
        config = PlatformConfig(platform=PlatformType.AMAZON, label="Test")
        with self.assertRaises(TypeError):
            PlatformAdapter(config)  # type: ignore


class AmazonAdapterUnitTests(IsolatedAsyncioTestCase):
    """Test AmazonAdapter without browser."""

    async def asyncSetUp(self):
        """Create an AmazonAdapter instance."""
        self.adapter = AmazonAdapter()

    async def test_adapter_type(self) -> None:
        """AmazonAdapter should have correct platform type."""
        self.assertEqual(self.adapter.config.platform, PlatformType.AMAZON)
        self.assertEqual(self.adapter.config.label, "Amazon 广告")

    async def test_initial_connection_status(self) -> None:
        """Initial status should be disconnected."""
        self.assertEqual(
            self.adapter.connection_status,
            PlatformConnectionStatus.DISCONNECTED,
        )

    async def test_get_platform_info(self) -> None:
        """get_platform_info should return expected structure."""
        info = self.adapter.get_platform_info()
        self.assertEqual(info["type"], "amazon")
        self.assertEqual(info["label"], "Amazon 广告")
        self.assertTrue(info["enabled"])
        self.assertIn("cookie_status", info)

    async def test_health_check_disconnected(self) -> None:
        """Health check without cookies should return unhealthy."""
        result = await self.adapter.check_health()
        self.assertFalse(result.is_healthy)
        self.assertFalse(result.cookie_valid)

    async def test_login_sets_connected(self) -> None:
        """Login should set connection status to connected."""
        success = await self.adapter.login(headless=True)
        self.assertTrue(success)
        self.assertEqual(
            self.adapter.connection_status,
            PlatformConnectionStatus.CONNECTED,
        )

    async def test_collect_after_login(self) -> None:
        """Collect should work after successful login."""
        await self.adapter.login(headless=True)
        data = await self.adapter.collect_ad_data(sku_ids=["AMZ-001"])
        self.assertIsInstance(data, list)

    async def test_execute_action_after_login(self) -> None:
        """Execute action should work after login."""
        await self.adapter.login(headless=True)
        action = ExecutionAction(
            action_type="adjust_bid",
            field="daily_budget",
            current_value=10.0,
            new_value=12.0,
            change_pct=0.2,
        )
        result = await self.adapter.execute_action(action)
        self.assertTrue(result)

    async def test_execute_action_without_login(self) -> None:
        """Execute action without login should fail."""
        action = ExecutionAction(
            action_type="adjust_bid",
            field="daily_budget",
            current_value=10.0,
            new_value=12.0,
        )
        result = await self.adapter.execute_action(action)
        self.assertFalse(result)

    async def test_double_login_is_idempotent(self) -> None:
        """Login should be idempotent."""
        await self.adapter.login(headless=True)
        status1 = self.adapter.connection_status
        await self.adapter.login(headless=True)
        self.assertEqual(self.adapter.connection_status, status1)

    async def test_disconnect_changes_status(self) -> None:
        """Disconnect should reset connection status."""
        await self.adapter.login(headless=True)
        await self.adapter.disconnect()
        self.assertEqual(
            self.adapter.connection_status,
            PlatformConnectionStatus.DISCONNECTED,
        )

    async def test_ping_after_disconnect(self) -> None:
        """Ping after disconnect should return False."""
        await self.adapter.disconnect()
        result = await self.adapter.ping()
        self.assertFalse(result)

    async def test_marketplace_default(self) -> None:
        """Default marketplace should be US."""
        self.assertEqual(self.adapter.get_marketplace_id(), "ATVPDKIKX0DER")

    async def test_set_marketplace(self) -> None:
        """set_marketplace should update the marketplace."""
        self.adapter.set_marketplace("A1F83G8C2ARO7P")
        self.assertEqual(self.adapter.get_marketplace_id(), "A1F83G8C2ARO7P")

    async def test_invalid_action_type_without_connection(self) -> None:
        """Unknown action type should still fail, not raise."""
        action = ExecutionAction(
            action_type="nonexistent_action",
            metadata={"some": "data"},
        )
        result = await self.adapter.execute_action(action)
        self.assertFalse(result)


class HealthCheckResultTests(IsolatedAsyncioTestCase):
    """Test HealthCheckResult data class."""

    def test_healthy_result(self) -> None:
        """Healthy health check result."""
        result = HealthCheckResult(is_healthy=True, cookie_valid=True)
        self.assertTrue(result.is_healthy)
        self.assertTrue(result.cookie_valid)

    def test_unhealthy_result(self) -> None:
        """Unhealthy health check result."""
        result = HealthCheckResult(
            is_healthy=False,
            cookie_valid=False,
            message="Cookie expired",
        )
        self.assertFalse(result.is_healthy)
        self.assertEqual(result.message, "Cookie expired")


class ExecutionActionTests(IsolatedAsyncioTestCase):
    """Test ExecutionAction data class."""

    def test_bid_action(self) -> None:
        """Bid adjustment action."""
        action = ExecutionAction(
            action_type="adjust_bid",
            field="daily_budget",
            current_value=10.0,
            new_value=12.50,
            change_pct=0.25,
        )
        self.assertEqual(action.action_type, "adjust_bid")
        self.assertEqual(action.change_pct, 0.25)
        self.assertEqual(action.new_value, 12.50)

    def test_pause_action(self) -> None:
        """Pause ad action with metadata."""
        action = ExecutionAction(
            action_type="pause_ad",
            metadata={"campaign_id": "camp-123", "reason": "roi_negative"},
        )
        self.assertEqual(action.action_type, "pause_ad")
        self.assertEqual(action.metadata["campaign_id"], "camp-123")


class PlatformSyncServiceTests(IsolatedAsyncioTestCase):
    """Test PlatformSyncService."""

    async def asyncSetUp(self):
        """Create a fresh sync service for each test."""
        self.sync = PlatformSyncService()

    async def test_list_platforms(self) -> None:
        """list_platforms should return registered platforms."""
        platforms = self.sync.list_platforms()
        # Should have at least Amazon registered
        self.assertTrue(any(p["type"] == "amazon" for p in platforms))

    async def test_get_adapter_amazon(self) -> None:
        """get_adapter should return AmazonAdapter for Amazon."""
        adapter = self.sync.get_adapter(PlatformType.AMAZON)
        self.assertIsNotNone(adapter)
        self.assertEqual(adapter.config.platform, PlatformType.AMAZON)

    async def test_get_adapter_aliexpress(self) -> None:
        """get_adapter should return None for unregistered platform."""
        adapter = self.sync.get_adapter(PlatformType.ALIEXPRESS)
        self.assertIsNone(adapter)

    async def test_get_enabled_adapters(self) -> None:
        """get_enabled_adapters should return enabled adapters."""
        adapters = self.sync.get_enabled_adapters()
        self.assertTrue(all(a.config.enabled for a in adapters))

    async def test_disable_platform(self) -> None:
        """disable_platform should set enabled to False."""
        success = await self.sync.disable_platform(PlatformType.AMAZON)
        self.assertTrue(success)
        adapter = self.sync.get_adapter(PlatformType.AMAZON)
        self.assertFalse(adapter.config.enabled)

    async def test_enable_platform(self) -> None:
        """enable_platform should set enabled to True."""
        await self.sync.disable_platform(PlatformType.AMAZON)
        success = await self.sync.enable_platform(PlatformType.AMAZON)
        self.assertTrue(success)
        adapter = self.sync.get_adapter(PlatformType.AMAZON)
        self.assertTrue(adapter.config.enabled)

    async def test_disable_unknown_platform(self) -> None:
        """disable_platform for unknown platform should return False."""
        success = await self.sync.disable_platform(PlatformType.ALIEXPRESS)
        self.assertFalse(success)

    async def test_reconnect_unknown_platform(self) -> None:
        """reconnect_platform for unknown platform should return False."""
        success = await self.sync.reconnect_platform(PlatformType.ALIEXPRESS)
        self.assertFalse(success)

    async def test_check_all_health(self) -> None:
        """check_all_health should return results for all platforms."""
        results = await self.sync.check_all_health()
        self.assertIn("amazon", results)
        self.assertFalse(results["amazon"].is_healthy)

    async def test_collect_all(self) -> None:
        """collect_all should return results by platform."""
        results = await self.sync.collect_all()
        self.assertIn("amazon", results)
        self.assertIsInstance(results["amazon"], list)

    async def test_register_adapter(self) -> None:
        """register_adapter should add a new adapter."""
        from App.services.platform.base import PlatformConfig

        config = PlatformConfig(
            platform=PlatformType.ALIEXPRESS,
            label="AliExpress 测试",
        )
        # Create a minimal test adapter
        adapter = AmazonAdapter(config)
        self.sync.register_adapter(PlatformType.ALIEXPRESS, adapter)

        retrieved = self.sync.get_adapter(PlatformType.ALIEXPRESS)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.config.label, "AliExpress 测试")

    async def test_reconnect_enabled_platform(self) -> None:
        """Reconnect should succeed for a connected platform."""
        # Login first so reconnect can work
        adapter = self.sync.get_adapter(PlatformType.AMAZON)
        await adapter.disconnect()
        # After disconnect, reconnect should log in again
        success = await self.sync.reconnect_platform(PlatformType.AMAZON)
        self.assertTrue(success)
        self.assertEqual(
            adapter.connection_status,
            PlatformConnectionStatus.CONNECTED,
        )
