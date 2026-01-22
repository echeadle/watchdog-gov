"""Unit tests for cache configuration."""

import pytest
from datetime import datetime, timedelta

from app.services.cache_config import CacheTTL, get_ttl_timedelta, is_cache_valid


class TestCacheTTLValues:
    """Test that TTL values are configured correctly."""

    def test_news_ttl_is_one_hour(self):
        """News should have 1 hour TTL."""
        assert CacheTTL.NEWS.value == 1

    def test_members_ttl_is_24_hours(self):
        """Members should have 24 hour TTL."""
        assert CacheTTL.MEMBERS.value == 24

    def test_bills_ttl_is_24_hours(self):
        """Bills should have 24 hour TTL."""
        assert CacheTTL.BILLS.value == 24

    def test_votes_ttl_is_24_hours(self):
        """Votes should have 24 hour TTL."""
        assert CacheTTL.VOTES.value == 24

    def test_finance_ttl_is_one_week(self):
        """Finance should have 168 hour (1 week) TTL."""
        assert CacheTTL.FINANCE.value == 168
        assert CacheTTL.FINANCE.value == 7 * 24  # 7 days


class TestGetTTLTimedelta:
    """Test the get_ttl_timedelta function."""

    def test_news_timedelta(self):
        """News TTL should return 1 hour timedelta."""
        result = get_ttl_timedelta(CacheTTL.NEWS)
        assert result == timedelta(hours=1)

    def test_members_timedelta(self):
        """Members TTL should return 24 hour timedelta."""
        result = get_ttl_timedelta(CacheTTL.MEMBERS)
        assert result == timedelta(hours=24)

    def test_finance_timedelta(self):
        """Finance TTL should return 168 hour (1 week) timedelta."""
        result = get_ttl_timedelta(CacheTTL.FINANCE)
        assert result == timedelta(hours=168)
        assert result == timedelta(days=7)


class TestIsCacheValid:
    """Test the is_cache_valid function."""

    def test_none_cached_at_is_invalid(self):
        """None cached_at should return False."""
        assert is_cache_valid(None, CacheTTL.NEWS) is False

    def test_recent_cache_is_valid(self):
        """Cache from 1 minute ago should be valid."""
        cached_at = datetime.utcnow() - timedelta(minutes=1)
        assert is_cache_valid(cached_at, CacheTTL.NEWS) is True
        assert is_cache_valid(cached_at, CacheTTL.MEMBERS) is True
        assert is_cache_valid(cached_at, CacheTTL.FINANCE) is True

    def test_news_cache_expires_after_one_hour(self):
        """News cache should expire after 1 hour."""
        # Just under 1 hour - should be valid
        cached_at = datetime.utcnow() - timedelta(minutes=59)
        assert is_cache_valid(cached_at, CacheTTL.NEWS) is True

        # Just over 1 hour - should be invalid
        cached_at = datetime.utcnow() - timedelta(hours=1, minutes=1)
        assert is_cache_valid(cached_at, CacheTTL.NEWS) is False

    def test_members_cache_expires_after_24_hours(self):
        """Members cache should expire after 24 hours."""
        # Just under 24 hours - should be valid
        cached_at = datetime.utcnow() - timedelta(hours=23, minutes=59)
        assert is_cache_valid(cached_at, CacheTTL.MEMBERS) is True

        # Just over 24 hours - should be invalid
        cached_at = datetime.utcnow() - timedelta(hours=24, minutes=1)
        assert is_cache_valid(cached_at, CacheTTL.MEMBERS) is False

    def test_finance_cache_expires_after_one_week(self):
        """Finance cache should expire after 1 week (168 hours)."""
        # 6 days ago - should be valid
        cached_at = datetime.utcnow() - timedelta(days=6)
        assert is_cache_valid(cached_at, CacheTTL.FINANCE) is True

        # 8 days ago - should be invalid
        cached_at = datetime.utcnow() - timedelta(days=8)
        assert is_cache_valid(cached_at, CacheTTL.FINANCE) is False

    def test_different_ttls_same_timestamp(self):
        """Same timestamp should have different validity for different TTLs."""
        # 2 hours ago
        cached_at = datetime.utcnow() - timedelta(hours=2)

        # News (1hr) should be expired
        assert is_cache_valid(cached_at, CacheTTL.NEWS) is False

        # Members (24hr) should still be valid
        assert is_cache_valid(cached_at, CacheTTL.MEMBERS) is True

        # Finance (168hr) should still be valid
        assert is_cache_valid(cached_at, CacheTTL.FINANCE) is True

    def test_boundary_at_exactly_ttl(self):
        """Cache at exactly TTL boundary should be invalid (< not <=)."""
        # Exactly 1 hour ago for news
        cached_at = datetime.utcnow() - timedelta(hours=1)
        # At exactly the boundary, it should be invalid (strictly less than)
        assert is_cache_valid(cached_at, CacheTTL.NEWS) is False


class TestTTLRelativeValues:
    """Test that TTL values have correct relative ordering."""

    def test_news_is_shortest_ttl(self):
        """News should have the shortest TTL."""
        assert CacheTTL.NEWS.value < CacheTTL.MEMBERS.value
        assert CacheTTL.NEWS.value < CacheTTL.BILLS.value
        assert CacheTTL.NEWS.value < CacheTTL.VOTES.value
        assert CacheTTL.NEWS.value < CacheTTL.FINANCE.value

    def test_finance_is_longest_ttl(self):
        """Finance should have the longest TTL."""
        assert CacheTTL.FINANCE.value > CacheTTL.NEWS.value
        assert CacheTTL.FINANCE.value > CacheTTL.MEMBERS.value
        assert CacheTTL.FINANCE.value > CacheTTL.BILLS.value
        assert CacheTTL.FINANCE.value > CacheTTL.VOTES.value

    def test_congressional_data_has_same_ttl(self):
        """Members, bills, and votes should have the same TTL."""
        assert CacheTTL.MEMBERS.value == CacheTTL.BILLS.value
        assert CacheTTL.BILLS.value == CacheTTL.VOTES.value
