"""Centralized cache TTL configuration for API data.

TTL values are defined in hours for each data type:
- News: 1 hour (changes frequently, also helps manage NewsAPI rate limits)
- Members: 24 hours (basic legislator info doesn't change often)
- Bills: 24 hours (bill status can change but not rapidly)
- Votes: 24 hours (vote records are immutable once recorded)
- Finance: 168 hours (1 week - FEC data updates infrequently)
"""

from dataclasses import dataclass
from enum import Enum
from datetime import timedelta
from typing import Generic, TypeVar, Optional

T = TypeVar('T')


@dataclass
class CachedResponse(Generic[T]):
    """Wrapper for API responses that may come from cache.

    Attributes:
        data: The actual response data
        is_stale: True if data is from expired cache (served due to API failure)
        warning: Human-readable warning message if data is stale
    """

    data: T
    is_stale: bool = False
    warning: Optional[str] = None

    @classmethod
    def fresh(cls, data: T) -> "CachedResponse[T]":
        """Create a response with fresh data."""
        return cls(data=data, is_stale=False, warning=None)

    @classmethod
    def stale(cls, data: T, data_type: str = "data") -> "CachedResponse[T]":
        """Create a response with stale cached data."""
        return cls(
            data=data,
            is_stale=True,
            warning=f"This {data_type} may be outdated. Unable to fetch latest data from the source."
        )


class CacheTTL(Enum):
    """Cache TTL values in hours for different data types."""

    NEWS = 1           # 1 hour - changes frequently
    MEMBERS = 24       # 24 hours - basic info stable
    BILLS = 24         # 24 hours - status can change
    VOTES = 24         # 24 hours - immutable once recorded
    FINANCE = 168      # 1 week (7 * 24) - FEC updates infrequently


def get_ttl_timedelta(ttl: CacheTTL) -> timedelta:
    """Get timedelta for a cache TTL value.

    Args:
        ttl: CacheTTL enum value

    Returns:
        timedelta representing the TTL duration
    """
    return timedelta(hours=ttl.value)


def is_cache_valid(cached_at, ttl: CacheTTL) -> bool:
    """Check if cached data is still valid.

    Args:
        cached_at: datetime when data was cached
        ttl: CacheTTL enum value for this data type

    Returns:
        True if cache is still valid, False if expired
    """
    from datetime import datetime, timezone

    if cached_at is None:
        return False

    # Handle both naive and aware datetimes
    now = datetime.utcnow()
    if cached_at.tzinfo is not None:
        now = datetime.now(timezone.utc)

    return now - cached_at < get_ttl_timedelta(ttl)
