"""Unit tests for the unified cache service."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.cache_service import (
    CacheSection,
    invalidate_cache,
    refresh_section,
    refresh_all,
)
from app.services.cache_config import CachedResponse


class TestCacheSection:
    """Tests for CacheSection enum."""

    def test_all_sections_defined(self):
        """All expected sections should be defined."""
        assert CacheSection.MEMBER == "member"
        assert CacheSection.BILLS == "bills"
        assert CacheSection.VOTES == "votes"
        assert CacheSection.FINANCE == "finance"
        assert CacheSection.NEWS == "news"

    def test_section_is_string_enum(self):
        """Sections should be string values."""
        for section in CacheSection:
            assert isinstance(section.value, str)


class TestInvalidateCache:
    """Tests for invalidate_cache function."""

    @pytest.mark.asyncio
    async def test_invalidate_member_cache(self):
        """Should call congress_client.invalidate_member_cache for MEMBER section."""
        mock_db = MagicMock()

        with patch("app.services.cache_service.congress_client") as mock_client:
            mock_client.invalidate_member_cache = AsyncMock()

            await invalidate_cache(mock_db, "A000001", CacheSection.MEMBER)

            mock_client.invalidate_member_cache.assert_called_once_with(mock_db, "A000001")

    @pytest.mark.asyncio
    async def test_invalidate_bills_cache(self):
        """Should call congress_client.invalidate_bills_cache for BILLS section."""
        mock_db = MagicMock()

        with patch("app.services.cache_service.congress_client") as mock_client:
            mock_client.invalidate_bills_cache = AsyncMock()

            await invalidate_cache(mock_db, "A000001", CacheSection.BILLS)

            mock_client.invalidate_bills_cache.assert_called_once_with(mock_db, "A000001")

    @pytest.mark.asyncio
    async def test_invalidate_finance_cache(self):
        """Should call fec_client.invalidate_finance_cache for FINANCE section."""
        mock_db = MagicMock()

        with patch("app.services.cache_service.fec_client") as mock_client:
            mock_client.invalidate_finance_cache = AsyncMock()

            await invalidate_cache(mock_db, "A000001", CacheSection.FINANCE)

            mock_client.invalidate_finance_cache.assert_called_once_with(mock_db, "A000001")

    @pytest.mark.asyncio
    async def test_invalidate_news_cache(self):
        """Should call news_client.invalidate_cache for NEWS section."""
        mock_db = MagicMock()

        with patch("app.services.cache_service.news_client") as mock_client:
            mock_client.invalidate_cache = AsyncMock()

            await invalidate_cache(mock_db, "A000001", CacheSection.NEWS)

            mock_client.invalidate_cache.assert_called_once_with(mock_db, "A000001")


class TestRefreshSection:
    """Tests for refresh_section function."""

    @pytest.mark.asyncio
    async def test_refresh_member_section(self):
        """Should call congress_client.refresh_member for MEMBER section."""
        mock_db = MagicMock()
        expected_response = CachedResponse.fresh({"name": "Test"})

        with patch("app.services.cache_service.congress_client") as mock_client:
            mock_client.refresh_member = AsyncMock(return_value=expected_response)

            result = await refresh_section(mock_db, "A000001", CacheSection.MEMBER)

            mock_client.refresh_member.assert_called_once_with(mock_db, "A000001")
            assert result == expected_response

    @pytest.mark.asyncio
    async def test_refresh_bills_section(self):
        """Should call congress_client.refresh_bills for BILLS section."""
        mock_db = MagicMock()
        mock_bills = [{"title": "Bill 1"}, {"title": "Bill 2"}]

        with patch("app.services.cache_service.congress_client") as mock_client:
            mock_client.refresh_bills = AsyncMock(return_value=mock_bills)

            result = await refresh_section(mock_db, "A000001", CacheSection.BILLS)

            mock_client.refresh_bills.assert_called_once_with(mock_db, "A000001")
            assert result.data == mock_bills
            assert result.is_stale is False

    @pytest.mark.asyncio
    async def test_refresh_finance_section(self):
        """Should call fec_client.refresh_finances for FINANCE section."""
        mock_db = MagicMock()
        expected_response = CachedResponse.fresh({"receipts": 1000000})

        with patch("app.services.cache_service.fec_client") as mock_client:
            mock_client.refresh_finances = AsyncMock(return_value=expected_response)

            result = await refresh_section(mock_db, "A000001", CacheSection.FINANCE)

            mock_client.refresh_finances.assert_called_once_with(mock_db, "A000001")
            assert result == expected_response

    @pytest.mark.asyncio
    async def test_refresh_news_section(self):
        """Should call news_client.refresh_news for NEWS section."""
        mock_db = MagicMock()
        expected_response = CachedResponse.fresh([{"title": "Article"}])

        with patch("app.services.cache_service.news_client") as mock_client:
            mock_client.refresh_news = AsyncMock(return_value=expected_response)

            result = await refresh_section(mock_db, "A000001", CacheSection.NEWS)

            mock_client.refresh_news.assert_called_once_with(mock_db, "A000001")
            assert result == expected_response


class TestRefreshAll:
    """Tests for refresh_all function."""

    @pytest.mark.asyncio
    async def test_refresh_all_returns_status_dict(self):
        """refresh_all should return dict with status for each section."""
        mock_db = MagicMock()

        with patch("app.services.cache_service.refresh_section") as mock_refresh:
            mock_refresh.return_value = CachedResponse.fresh({})

            result = await refresh_all(mock_db, "A000001")

            # Should have entry for each section
            assert "member" in result
            assert "bills" in result
            assert "votes" in result
            assert "finance" in result
            assert "news" in result

    @pytest.mark.asyncio
    async def test_refresh_all_marks_success(self):
        """refresh_all should mark successful refreshes as True."""
        mock_db = MagicMock()

        with patch("app.services.cache_service.refresh_section") as mock_refresh:
            mock_refresh.return_value = CachedResponse.fresh({})

            result = await refresh_all(mock_db, "A000001")

            # All should be successful
            for status in result.values():
                assert status is True

    @pytest.mark.asyncio
    async def test_refresh_all_handles_failures(self):
        """refresh_all should mark failed refreshes as False."""
        mock_db = MagicMock()

        with patch("app.services.cache_service.refresh_section") as mock_refresh:
            async def side_effect(db, bid, section):
                if section == CacheSection.FINANCE:
                    raise Exception("API Error")
                return CachedResponse.fresh({})

            mock_refresh.side_effect = side_effect

            result = await refresh_all(mock_db, "A000001")

            # Finance should have failed
            assert result["finance"] is False
            # Others should have succeeded
            assert result["member"] is True
            assert result["news"] is True
