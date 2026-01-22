"""Unit tests for rate limiting middleware."""

import time
import pytest
from unittest.mock import MagicMock, AsyncMock

from app.middleware.rate_limit import (
    RateLimitConfig,
    RateLimitEntry,
    RateLimitStore,
    RateLimitMiddleware,
    DEFAULT_RATE_LIMITS,
)


class TestRateLimitConfig:
    """Tests for RateLimitConfig class."""

    def test_config_without_pattern_matches_all(self):
        """Config without pattern should match any path."""
        config = RateLimitConfig(requests=100, window_seconds=60)
        assert config.matches_path("/") is True
        assert config.matches_path("/api/users") is True
        assert config.matches_path("/chat") is True

    def test_config_with_pattern_matches_specific_paths(self):
        """Config with pattern should only match specific paths."""
        config = RateLimitConfig(
            requests=20, window_seconds=60, path_pattern=r"^/chat"
        )
        assert config.matches_path("/chat") is True
        assert config.matches_path("/chat/send") is True
        assert config.matches_path("/api/chat") is False
        assert config.matches_path("/") is False

    def test_config_with_api_pattern(self):
        """Test API path pattern matching."""
        config = RateLimitConfig(
            requests=60, window_seconds=60, path_pattern=r"^/api/"
        )
        assert config.matches_path("/api/users") is True
        assert config.matches_path("/api/legislators/123") is True
        assert config.matches_path("/chat") is False
        assert config.matches_path("/") is False

    def test_config_stores_limit_values(self):
        """Config should store requests and window values."""
        config = RateLimitConfig(requests=50, window_seconds=120)
        assert config.requests == 50
        assert config.window_seconds == 120


class TestRateLimitStore:
    """Tests for RateLimitStore class."""

    def test_first_request_is_allowed(self):
        """First request should always be allowed."""
        store = RateLimitStore()
        allowed, remaining, reset_time = store.check_and_increment(
            client_id="client1", pattern_key="default", limit=10, window=60
        )
        assert allowed is True
        assert remaining == 9

    def test_requests_up_to_limit_are_allowed(self):
        """Requests up to the limit should be allowed."""
        store = RateLimitStore()
        for i in range(10):
            allowed, remaining, _ = store.check_and_increment(
                client_id="client1", pattern_key="default", limit=10, window=60
            )
            assert allowed is True
            assert remaining == 10 - i - 1

    def test_request_over_limit_is_blocked(self):
        """Request exceeding limit should be blocked."""
        store = RateLimitStore()
        # Make 10 requests (the limit)
        for _ in range(10):
            store.check_and_increment(
                client_id="client1", pattern_key="default", limit=10, window=60
            )

        # 11th request should be blocked
        allowed, remaining, _ = store.check_and_increment(
            client_id="client1", pattern_key="default", limit=10, window=60
        )
        assert allowed is False
        assert remaining == 0

    def test_different_clients_have_separate_limits(self):
        """Different clients should have independent rate limits."""
        store = RateLimitStore()

        # Exhaust client1's limit
        for _ in range(10):
            store.check_and_increment(
                client_id="client1", pattern_key="default", limit=10, window=60
            )

        # client1 is blocked
        allowed1, _, _ = store.check_and_increment(
            client_id="client1", pattern_key="default", limit=10, window=60
        )
        assert allowed1 is False

        # client2 should still be allowed
        allowed2, remaining2, _ = store.check_and_increment(
            client_id="client2", pattern_key="default", limit=10, window=60
        )
        assert allowed2 is True
        assert remaining2 == 9

    def test_different_patterns_have_separate_limits(self):
        """Different path patterns should have independent rate limits."""
        store = RateLimitStore()

        # Exhaust limit for "chat" pattern
        for _ in range(5):
            store.check_and_increment(
                client_id="client1", pattern_key="^/chat", limit=5, window=60
            )

        # Chat pattern is blocked
        allowed_chat, _, _ = store.check_and_increment(
            client_id="client1", pattern_key="^/chat", limit=5, window=60
        )
        assert allowed_chat is False

        # API pattern should still be allowed
        allowed_api, remaining_api, _ = store.check_and_increment(
            client_id="client1", pattern_key="^/api/", limit=60, window=60
        )
        assert allowed_api is True
        assert remaining_api == 59

    def test_reset_time_is_in_future(self):
        """Reset time should be in the future."""
        store = RateLimitStore()
        _, _, reset_time = store.check_and_increment(
            client_id="client1", pattern_key="default", limit=10, window=60
        )
        assert reset_time > time.time()
        assert reset_time <= time.time() + 60

    def test_window_expires_and_resets(self):
        """Rate limit should reset after window expires."""
        store = RateLimitStore()

        # Use a very short window for testing
        window = 1  # 1 second

        # Exhaust the limit
        for _ in range(5):
            store.check_and_increment(
                client_id="client1", pattern_key="default", limit=5, window=window
            )

        # Should be blocked
        allowed, _, _ = store.check_and_increment(
            client_id="client1", pattern_key="default", limit=5, window=window
        )
        assert allowed is False

        # Wait for window to expire
        time.sleep(1.1)

        # Should be allowed again
        allowed, remaining, _ = store.check_and_increment(
            client_id="client1", pattern_key="default", limit=5, window=window
        )
        assert allowed is True
        assert remaining == 4


class TestRateLimitEntry:
    """Tests for RateLimitEntry dataclass."""

    def test_default_values(self):
        """Entry should have sensible defaults."""
        entry = RateLimitEntry()
        assert entry.count == 0
        assert entry.window_start == 0.0

    def test_custom_values(self):
        """Entry should accept custom values."""
        entry = RateLimitEntry(count=5, window_start=1000.0)
        assert entry.count == 5
        assert entry.window_start == 1000.0


class TestDefaultRateLimits:
    """Tests for default rate limit configurations."""

    def test_chat_has_strictest_per_minute_limit(self):
        """Chat endpoints should have stricter limits."""
        chat_configs = [c for c in DEFAULT_RATE_LIMITS if c.path_pattern and "chat" in c.path_pattern]
        default_config = next(c for c in DEFAULT_RATE_LIMITS if c.path_pattern is None)

        # Find the per-minute chat limit
        chat_per_minute = next(c for c in chat_configs if c.window_seconds == 60)

        assert chat_per_minute.requests < default_config.requests

    def test_default_config_exists(self):
        """There should be a default config without pattern."""
        default_configs = [c for c in DEFAULT_RATE_LIMITS if c.path_pattern is None]
        assert len(default_configs) == 1

    def test_all_configs_have_positive_values(self):
        """All configs should have positive request limits and windows."""
        for config in DEFAULT_RATE_LIMITS:
            assert config.requests > 0
            assert config.window_seconds > 0


class TestRateLimitMiddleware:
    """Tests for RateLimitMiddleware class."""

    def test_get_client_id_from_direct_connection(self):
        """Should extract client ID from request.client."""
        middleware = RateLimitMiddleware(app=MagicMock())

        request = MagicMock()
        request.headers = {}
        request.client.host = "192.168.1.100"

        client_id = middleware._get_client_id(request)
        assert client_id == "192.168.1.100"

    def test_get_client_id_from_forwarded_for(self):
        """Should prefer X-Forwarded-For header when present."""
        middleware = RateLimitMiddleware(app=MagicMock())

        request = MagicMock()
        request.headers = {"X-Forwarded-For": "203.0.113.50, 70.41.3.18"}
        request.client.host = "127.0.0.1"

        client_id = middleware._get_client_id(request)
        assert client_id == "203.0.113.50"

    def test_get_client_id_unknown_fallback(self):
        """Should return 'unknown' if no client info available."""
        middleware = RateLimitMiddleware(app=MagicMock())

        request = MagicMock()
        request.headers = {}
        request.client = None

        client_id = middleware._get_client_id(request)
        assert client_id == "unknown"

    def test_find_matching_config_uses_specific_pattern(self):
        """Should find the most specific matching config."""
        configs = [
            RateLimitConfig(requests=20, window_seconds=60, path_pattern=r"^/chat"),
            RateLimitConfig(requests=100, window_seconds=60, path_pattern=None),
        ]
        middleware = RateLimitMiddleware(app=MagicMock(), configs=configs)

        chat_config = middleware._find_matching_config("/chat/send")
        assert chat_config.requests == 20

        default_config = middleware._find_matching_config("/other")
        assert default_config.requests == 100

    def test_add_rate_limit_headers(self):
        """Should add standard rate limit headers."""
        middleware = RateLimitMiddleware(app=MagicMock())

        response = MagicMock()
        response.headers = {}

        result = middleware._add_rate_limit_headers(response, limit=100, remaining=95, reset=1234567890)

        assert response.headers["X-RateLimit-Limit"] == "100"
        assert response.headers["X-RateLimit-Remaining"] == "95"
        assert response.headers["X-RateLimit-Reset"] == "1234567890"

    @pytest.mark.asyncio
    async def test_dispatch_allows_request_within_limit(self):
        """Should allow requests within the rate limit."""
        store = RateLimitStore()
        configs = [RateLimitConfig(requests=10, window_seconds=60)]
        middleware = RateLimitMiddleware(app=MagicMock(), configs=configs, store=store)

        request = MagicMock()
        request.url.path = "/api/test"
        request.headers = {}
        request.client.host = "192.168.1.1"

        expected_response = MagicMock()
        expected_response.headers = {}
        call_next = AsyncMock(return_value=expected_response)

        response = await middleware.dispatch(request, call_next)

        call_next.assert_called_once_with(request)
        assert "X-RateLimit-Limit" in response.headers

    @pytest.mark.asyncio
    async def test_dispatch_blocks_request_over_limit(self):
        """Should block requests that exceed the rate limit."""
        store = RateLimitStore()
        configs = [RateLimitConfig(requests=2, window_seconds=60)]
        middleware = RateLimitMiddleware(app=MagicMock(), configs=configs, store=store)

        request = MagicMock()
        request.url.path = "/api/test"
        request.headers = {}
        request.client.host = "192.168.1.1"

        call_next = AsyncMock()

        # Make requests up to the limit
        for _ in range(2):
            response = MagicMock()
            response.headers = {}
            call_next.return_value = response
            await middleware.dispatch(request, call_next)

        # Third request should be blocked
        response = await middleware.dispatch(request, call_next)

        # call_next should only have been called twice (not for blocked request)
        assert call_next.call_count == 2
        assert response.status_code == 429

    @pytest.mark.asyncio
    async def test_dispatch_skips_health_endpoint(self):
        """Should skip rate limiting for health check endpoint."""
        store = RateLimitStore()
        configs = [RateLimitConfig(requests=1, window_seconds=60)]
        middleware = RateLimitMiddleware(app=MagicMock(), configs=configs, store=store)

        request = MagicMock()
        request.url.path = "/health"
        request.headers = {}
        request.client.host = "192.168.1.1"

        expected_response = MagicMock()
        call_next = AsyncMock(return_value=expected_response)

        # Multiple requests to health should all pass
        for _ in range(5):
            response = await middleware.dispatch(request, call_next)
            assert response == expected_response

        assert call_next.call_count == 5

    @pytest.mark.asyncio
    async def test_dispatch_skips_static_files(self):
        """Should skip rate limiting for static files."""
        store = RateLimitStore()
        configs = [RateLimitConfig(requests=1, window_seconds=60)]
        middleware = RateLimitMiddleware(app=MagicMock(), configs=configs, store=store)

        request = MagicMock()
        request.url.path = "/static/css/style.css"
        request.headers = {}
        request.client.host = "192.168.1.1"

        expected_response = MagicMock()
        call_next = AsyncMock(return_value=expected_response)

        # Multiple requests to static should all pass
        for _ in range(5):
            response = await middleware.dispatch(request, call_next)
            assert response == expected_response

        assert call_next.call_count == 5


class TestRateLimitIntegration:
    """Integration tests for rate limiting behavior."""

    def test_chat_and_api_independent_limits(self):
        """Chat and API endpoints should have independent limits."""
        store = RateLimitStore()

        # Simulate chat requests up to chat limit
        for _ in range(20):
            store.check_and_increment("client1", "^/chat", limit=20, window=60)

        # Chat should be blocked
        chat_allowed, _, _ = store.check_and_increment("client1", "^/chat", limit=20, window=60)
        assert chat_allowed is False

        # But API should still be allowed (different pattern)
        api_allowed, _, _ = store.check_and_increment("client1", "^/api/", limit=60, window=60)
        assert api_allowed is True

    def test_multiple_rate_limit_windows(self):
        """Different time windows should be tracked independently."""
        store = RateLimitStore()

        # This tests the scenario where chat has both per-minute and per-hour limits
        # Make 20 requests (hits per-minute limit)
        for _ in range(20):
            store.check_and_increment("client1", "chat_per_minute", limit=20, window=60)

        # Per-minute limit hit
        allowed_minute, _, _ = store.check_and_increment("client1", "chat_per_minute", limit=20, window=60)
        assert allowed_minute is False

        # Per-hour limit not yet hit (different pattern key)
        allowed_hour, _, _ = store.check_and_increment("client1", "chat_per_hour", limit=100, window=3600)
        assert allowed_hour is True
