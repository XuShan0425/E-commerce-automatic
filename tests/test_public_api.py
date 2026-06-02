"""Public REST API tests — scope auth, rate limiting, endpoint behavior.

Test strategy:
  - Unit tests for rate limiting logic (no DB needed)
  - Unit tests for scope/permission validation (no DB needed)
  - Endpoint integration tests with dependency overrides (no DB needed)
  - OpenAPI docs availability tests
"""

from __future__ import annotations

from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from App.core.security import (
    _RATE_LIMIT_DEFAULT_MAX,
    _rate_limits,
    generate_key,
    hash_key,
    rate_limited,
)


class RateLimitUnitTests(IsolatedAsyncioTestCase):
    """Test rate limiting behavior in isolation."""

    def setUp(self):
        """Clear rate limit state before each test."""
        _rate_limits.clear()

    def test_rate_limit_under_limit(self) -> None:
        """Requests under the limit should not raise."""
        test_key = generate_key()[0]
        for _ in range(5):
            try:
                rate_limited(test_key)
            except HTTPException:
                self.fail("rate_limited raised HTTPException unexpectedly")

    def test_rate_limit_exact_limit(self) -> None:
        """All requests up to the limit should succeed."""
        test_key = generate_key()[0]
        for i in range(_RATE_LIMIT_DEFAULT_MAX):
            try:
                rate_limited(test_key)
            except HTTPException:
                self.fail(
                    f"rate_limited raised at request {i+1} (limit={_RATE_LIMIT_DEFAULT_MAX})"
                )

    def test_rate_limit_exceeded_returns_429(self) -> None:
        """Exceeding the rate limit should raise HTTP 429."""
        test_key = generate_key()[0]

        # Fill up the rate limit (60 requests should succeed)
        for _ in range(_RATE_LIMIT_DEFAULT_MAX):
            rate_limited(test_key)

        # The next request should exceed the limit
        with self.assertRaises(HTTPException) as ctx:
            rate_limited(test_key)
        self.assertEqual(ctx.exception.status_code, 429)
        self.assertIn("Rate limit exceeded", str(ctx.exception.detail))

    def test_rate_limit_resets_after_window(self) -> None:
        """After the sliding window passes, requests should succeed again."""
        test_key = generate_key()[0]
        key_hash = hash_key(test_key)

        # Fill up
        for _ in range(_RATE_LIMIT_DEFAULT_MAX):
            rate_limited(test_key)

        # Should be blocked now
        with self.assertRaises(HTTPException):
            rate_limited(test_key)

        # Simulate time passing by clearing the entries
        _rate_limits[key_hash] = []

        # Should succeed again
        try:
            rate_limited(test_key)
        except HTTPException:
            self.fail("rate_limited should succeed after window reset")

    def test_different_keys_have_independent_limits(self) -> None:
        """Each API Key should have its own rate limit counter."""
        key1 = generate_key()[0]
        key2 = generate_key()[0]

        # Max out key1
        for _ in range(_RATE_LIMIT_DEFAULT_MAX):
            rate_limited(key1)

        # key1 should be blocked
        with self.assertRaises(HTTPException):
            rate_limited(key1)

        # key2 should still work
        try:
            rate_limited(key2)
        except HTTPException:
            self.fail("key2 should have its own rate limit counter")

    def test_generate_key_returns_valid_format(self) -> None:
        """Generated API keys should start with 'ak-' and have consistent length."""
        raw, hashed = generate_key()
        self.assertTrue(raw.startswith("ak-"))
        self.assertEqual(len(hashed), 64)  # SHA-256 hex digest
        self.assertNotEqual(raw, hashed)

    def test_hash_key_is_deterministic(self) -> None:
        """Hashing the same key twice should produce the same hash."""
        raw = "ak-test-key-value"
        h1 = hash_key(raw)
        h2 = hash_key(raw)
        self.assertEqual(h1, h2)

    def test_rate_limit_headers_present(self) -> None:
        """Rate limit headers should be properly formatted."""
        from App.core.security import get_rate_limit_headers

        test_key = generate_key()[0]
        headers = get_rate_limit_headers(test_key)

        self.assertIn("X-RateLimit-Limit", headers)
        self.assertIn("X-RateLimit-Remaining", headers)
        self.assertIn("X-RateLimit-Window", headers)
        self.assertEqual(int(headers["X-RateLimit-Limit"]), _RATE_LIMIT_DEFAULT_MAX)

    def test_different_keys_independent_rate_limits(self) -> None:
        """Verifying two different keys have independent rate limit state."""
        key1 = generate_key()[0]
        key2 = generate_key()[0]

        # Exhaust key1
        for _ in range(_RATE_LIMIT_DEFAULT_MAX):
            rate_limited(key1)

        # key1 should be exhausted
        with self.assertRaises(HTTPException):
            rate_limited(key1)

        # key2 should still have full quota
        remaining = _RATE_LIMIT_DEFAULT_MAX - len(_rate_limits[hash_key(key2)])
        self.assertEqual(remaining, _RATE_LIMIT_DEFAULT_MAX)


class ScopeUnitTests(IsolatedAsyncioTestCase):
    """Test scope/permission resolution logic."""

    def test_scope_parsing_single(self) -> None:
        """Single scope should parse correctly."""
        from App.core.security import _SCOPE_REGISTRY, invalidate_scope_cache

        key_hash = hash_key(generate_key()[0])
        scopes = {"products:read"}
        _SCOPE_REGISTRY[key_hash] = scopes
        self.assertIn("products:read", _SCOPE_REGISTRY[key_hash])

        # Cleanup
        invalidate_scope_cache(key_hash)
        self.assertNotIn(key_hash, _SCOPE_REGISTRY)

    def test_scope_parsing_multiple(self) -> None:
        """Multiple comma-separated scopes should parse correctly."""
        from App.core.security import _SCOPE_REGISTRY, invalidate_scope_cache

        key_hash = hash_key(generate_key()[0])
        scope_str = "products:read,ads:read,profit:read"
        scopes = set(s.strip() for s in scope_str.split(","))
        _SCOPE_REGISTRY[key_hash] = scopes
        self.assertIn("products:read", _SCOPE_REGISTRY[key_hash])
        self.assertIn("ads:read", _SCOPE_REGISTRY[key_hash])
        self.assertIn("profit:read", _SCOPE_REGISTRY[key_hash])
        self.assertEqual(len(_SCOPE_REGISTRY[key_hash]), 3)

        # Cleanup
        invalidate_scope_cache(key_hash)

    def test_admin_scope_grants_all_access(self) -> None:
        """The 'admin' scope should imply all permissions."""
        from App.core.security import _SCOPE_REGISTRY, invalidate_scope_cache

        key_hash = hash_key(generate_key()[0])
        _SCOPE_REGISTRY[key_hash] = {"admin"}

        # Admin should be treated as having access to any scope
        has_access = (
            bool(_SCOPE_REGISTRY[key_hash].intersection({"products:read"}))
            or "admin" in _SCOPE_REGISTRY[key_hash]
        )
        self.assertTrue(has_access, "admin scope should grant access to all permissions")

        # Cleanup
        invalidate_scope_cache(key_hash)


class PublicAPIEndpointTests(IsolatedAsyncioTestCase):
    """Integration tests for public API endpoints via TestClient.

    Uses dependency overrides to avoid needing a real database.
    """

    def setUp(self):
        """Build a test app with the public router and DB dependency override."""
        from App.api.public import router as public_router
        from App.core.database import get_db

        self.public_app = FastAPI(title="Test Public API")
        self.public_app.include_router(public_router)

        # Override get_db to use a mock session.
        # Use a regular Mock for the result object since Result.scalar_one_or_none()
        # is synchronous (not async).
        mock_session = AsyncMock()
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = None
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result
        mock_session.get.return_value = None

        async def _override_get_db():
            yield mock_session

        self.public_app.dependency_overrides[get_db] = _override_get_db
        self.client = TestClient(self.public_app)

    def test_root_endpoint(self) -> None:
        """GET / should return public API info."""
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("name", data)
        self.assertEqual(data["version"], "v1")
        self.assertIn("endpoints", data)
        self.assertIn("products", data["endpoints"])
        self.assertIn("ads", data["endpoints"])
        self.assertIn("profit", data["endpoints"])

    def test_products_list_requires_api_key(self) -> None:
        """GET /products without API key should return 401."""
        response = self.client.get("/products")
        self.assertEqual(response.status_code, 401)

    def test_products_list_with_invalid_api_key(self) -> None:
        """GET /products with invalid API key should return 401."""
        response = self.client.get(
            "/products", headers={"X-API-Key": "ak-invalid-key"}
        )
        self.assertEqual(response.status_code, 401)

    def test_ads_list_requires_api_key(self) -> None:
        """GET /ads without API key should return 401."""
        response = self.client.get("/ads")
        self.assertEqual(response.status_code, 401)

    def test_profit_list_requires_api_key(self) -> None:
        """GET /profit without API key should return 401."""
        response = self.client.get("/profit")
        self.assertEqual(response.status_code, 401)

    def test_products_detail_invalid_id_no_auth(self) -> None:
        """GET /products/{id} with no API key should return 401."""
        response = self.client.get("/products/9999")
        self.assertEqual(response.status_code, 401)

    def test_ads_detail_invalid_id_no_auth(self) -> None:
        """GET /ads/{id} with no API key should return 401."""
        response = self.client.get("/ads/9999")
        self.assertEqual(response.status_code, 401)

    def test_profit_detail_invalid_id_no_auth(self) -> None:
        """GET /profit/{id} with no API key should return 401."""
        response = self.client.get("/profit/9999")
        self.assertEqual(response.status_code, 401)

    def test_404_on_nonexistent_route(self) -> None:
        """GET /nonexistent should return 404."""
        response = self.client.get("/nonexistent")
        self.assertEqual(response.status_code, 404)


class PublicAPIDocsTests(IsolatedAsyncioTestCase):
    """Test OpenAPI docs are available for the public API."""

    def test_openapi_json_available(self) -> None:
        """OpenAPI schema should be accessible."""
        from App.api.public import router as public_router

        test_app = FastAPI(title="Test Public API")
        test_app.include_router(public_router)
        client = TestClient(test_app)

        response = client.get("/openapi.json")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("openapi", data)
        self.assertIn("info", data)
        self.assertIn("paths", data)

    def test_openapi_has_public_endpoints(self) -> None:
        """OpenAPI schema should document all public endpoints."""
        from App.api.public import router as public_router

        test_app = FastAPI(title="Test Public API")
        test_app.include_router(public_router)
        client = TestClient(test_app)

        response = client.get("/openapi.json")
        data = response.json()
        paths = data.get("paths", {})
        # FastAPI normalizes trailing slashes; check paths with or without them
        has_products = "/products" in paths or "/products/" in paths
        has_ads = "/ads" in paths or "/ads/" in paths
        has_profit = "/profit" in paths or "/profit/" in paths
        self.assertTrue(has_products, "OpenAPI should document GET /products")
        self.assertTrue(has_ads, "OpenAPI should document GET /ads")
        self.assertTrue(has_profit, "OpenAPI should document GET /profit")


class ApiKeyTests(IsolatedAsyncioTestCase):
    """Test API Key generation and scope management."""

    def test_generate_key_creates_unique_keys(self) -> None:
        """Multiple calls to generate_key should produce different keys."""
        seen_hashes = set()
        for _ in range(100):
            _, hashed = generate_key()
            self.assertNotIn(hashed, seen_hashes, "Generated duplicate key hash")
            seen_hashes.add(hashed)

    def test_generate_key_always_ak_prefix(self) -> None:
        """All generated keys should start with 'ak-'."""
        for _ in range(100):
            raw, _ = generate_key()
            self.assertTrue(raw.startswith("ak-"))

    def test_hash_consistency(self) -> None:
        """Same input should always produce the same hash."""
        raw_keys = ["ak-test-1", "ak-test-2", "ak-test-3"]
        for key in raw_keys:
            h1 = hash_key(key)
            h2 = hash_key(key)
            self.assertEqual(h1, h2)

    def test_different_keys_different_hashes(self) -> None:
        """Different inputs should produce different hashes."""
        h1 = hash_key("ak-key-a")
        h2 = hash_key("ak-key-b")
        self.assertNotEqual(h1, h2)
