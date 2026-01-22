"""Rate limiting middleware for FastAPI.

Implements per-client rate limiting with configurable limits per endpoint pattern.
Uses in-memory storage (can be upgraded to Redis for distributed deployments).
"""

import time
import re
from dataclasses import dataclass
from typing import Optional
from collections import defaultdict

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse


@dataclass
class RateLimitConfig:
    """Configuration for a rate limit rule.

    Attributes:
        requests: Maximum number of requests allowed in the window.
        window_seconds: Time window in seconds.
        path_pattern: Regex pattern to match request paths (None = default).
    """

    requests: int
    window_seconds: int
    path_pattern: Optional[str] = None

    def __post_init__(self):
        """Compile the path pattern if provided."""
        self._compiled_pattern: Optional[re.Pattern] = None
        if self.path_pattern:
            self._compiled_pattern = re.compile(self.path_pattern)

    def matches_path(self, path: str) -> bool:
        """Check if this config matches the given path."""
        if self._compiled_pattern is None:
            return True  # Default rule matches everything
        return self._compiled_pattern.match(path) is not None


@dataclass
class RateLimitEntry:
    """Tracks rate limit state for a client-path combination."""

    count: int = 0
    window_start: float = 0.0


class RateLimitStore:
    """In-memory storage for rate limit tracking.

    Thread-safe for single-process deployments. For multi-process or
    distributed deployments, replace with Redis-backed storage.
    """

    def __init__(self):
        # Key: (client_id, path_pattern) -> RateLimitEntry
        self._entries: dict[tuple[str, str], RateLimitEntry] = defaultdict(RateLimitEntry)
        self._last_cleanup = time.time()
        self._cleanup_interval = 60  # Cleanup every 60 seconds

    def _cleanup_expired(self, current_time: float, max_window: int):
        """Remove expired entries to prevent memory growth."""
        if current_time - self._last_cleanup < self._cleanup_interval:
            return

        expired_keys = []
        for key, entry in self._entries.items():
            if current_time - entry.window_start > max_window:
                expired_keys.append(key)

        for key in expired_keys:
            del self._entries[key]

        self._last_cleanup = current_time

    def check_and_increment(
        self, client_id: str, pattern_key: str, limit: int, window: int
    ) -> tuple[bool, int, int]:
        """Check rate limit and increment counter.

        Returns:
            Tuple of (allowed, remaining, reset_time)
            - allowed: Whether the request should be allowed
            - remaining: Number of requests remaining in window
            - reset_time: Unix timestamp when the window resets
        """
        current_time = time.time()
        self._cleanup_expired(current_time, window * 2)

        key = (client_id, pattern_key)
        entry = self._entries[key]

        # Check if window has expired
        if current_time - entry.window_start >= window:
            entry.count = 0
            entry.window_start = current_time

        # Calculate reset time
        reset_time = int(entry.window_start + window)

        # Check if limit exceeded
        if entry.count >= limit:
            remaining = 0
            return False, remaining, reset_time

        # Increment counter
        entry.count += 1
        remaining = max(0, limit - entry.count)

        return True, remaining, reset_time


# Default rate limit configurations
DEFAULT_RATE_LIMITS = [
    # AI chat endpoints - stricter limits (expensive API calls)
    RateLimitConfig(requests=20, window_seconds=60, path_pattern=r"^/chat"),
    RateLimitConfig(requests=100, window_seconds=3600, path_pattern=r"^/chat"),
    # API endpoints - moderate limits
    RateLimitConfig(requests=60, window_seconds=60, path_pattern=r"^/api/"),
    # Search endpoints
    RateLimitConfig(requests=30, window_seconds=60, path_pattern=r"^/search"),
    # Default for all other endpoints - lenient
    RateLimitConfig(requests=120, window_seconds=60, path_pattern=None),
]


class RateLimitMiddleware(BaseHTTPMiddleware):
    """ASGI middleware for rate limiting requests.

    Features:
    - Per-client rate limiting based on IP address
    - Configurable limits per endpoint pattern
    - Standard rate limit headers (X-RateLimit-*)
    - In-memory storage with automatic cleanup
    """

    def __init__(
        self,
        app,
        configs: Optional[list[RateLimitConfig]] = None,
        store: Optional[RateLimitStore] = None,
    ):
        """Initialize the rate limit middleware.

        Args:
            app: The ASGI application.
            configs: List of rate limit configurations (uses defaults if None).
            store: Rate limit store (creates new one if None).
        """
        super().__init__(app)
        self.configs = configs if configs is not None else DEFAULT_RATE_LIMITS
        self.store = store if store is not None else RateLimitStore()

    def _get_client_id(self, request: Request) -> str:
        """Extract client identifier from request.

        Uses X-Forwarded-For header if behind a proxy, otherwise uses
        the direct client IP address.
        """
        # Check for proxy headers
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Take the first IP (original client)
            return forwarded_for.split(",")[0].strip()

        # Fall back to direct client IP
        if request.client:
            return request.client.host

        return "unknown"

    def _find_matching_config(self, path: str) -> RateLimitConfig:
        """Find the most specific rate limit config for a path.

        Returns the first matching config with a pattern, or the default
        config if no patterns match.
        """
        default_config = None

        for config in self.configs:
            if config.path_pattern is None:
                default_config = config
            elif config.matches_path(path):
                return config

        # Return default config or a fallback
        return default_config or RateLimitConfig(requests=120, window_seconds=60)

    def _add_rate_limit_headers(
        self, response: Response, limit: int, remaining: int, reset: int
    ) -> Response:
        """Add standard rate limit headers to the response."""
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(reset)
        return response

    async def dispatch(self, request: Request, call_next) -> Response:
        """Process the request through rate limiting."""
        # Skip rate limiting for certain paths (health checks, static files)
        path = request.url.path
        if path.startswith("/static") or path == "/health":
            return await call_next(request)

        client_id = self._get_client_id(request)
        config = self._find_matching_config(path)

        # Use pattern as key, or "default" for no pattern
        pattern_key = config.path_pattern or "default"

        allowed, remaining, reset_time = self.store.check_and_increment(
            client_id=client_id,
            pattern_key=pattern_key,
            limit=config.requests,
            window=config.window_seconds,
        )

        if not allowed:
            # Return 429 Too Many Requests
            response = JSONResponse(
                status_code=429,
                content={
                    "detail": "Rate limit exceeded. Please try again later.",
                    "retry_after": reset_time - int(time.time()),
                },
            )
            response.headers["Retry-After"] = str(reset_time - int(time.time()))
            return self._add_rate_limit_headers(
                response, config.requests, remaining, reset_time
            )

        # Process the request
        response = await call_next(request)

        # Add rate limit headers to successful responses
        return self._add_rate_limit_headers(
            response, config.requests, remaining, reset_time
        )
