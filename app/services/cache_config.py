"""Centralized cache TTL configuration for API data.

TTL values are defined in hours for each data type:
- News: 1 hour (changes frequently, also helps manage NewsAPI rate limits)
- Members: 24 hours (basic legislator info doesn't change often)
- Bills: 24 hours (bill status can change but not rapidly)
- Votes: 24 hours (vote records are immutable once recorded)
- Finance: 168 hours (1 week - FEC data updates infrequently)
"""

from enum import Enum
from datetime import timedelta


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
