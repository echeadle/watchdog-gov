"""Unit tests for NewsAPI client request pooling and cache invalidation."""

import asyncio
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base
from app.models import Legislator, NewsArticle
from app.services.news_api import NewsAPIClient, _request_semaphore


# Use in-memory SQLite for testing
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture
async def db_session():
    """Create a fresh database session for each test."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def sample_legislators(db_session: AsyncSession):
    """Create sample legislators for testing."""
    legislators = [
        Legislator(
            bioguide_id="A000001",
            first_name="Alice",
            last_name="Adams",
            full_name="Alice Adams",
            party="D",
            state="CA",
        ),
        Legislator(
            bioguide_id="B000002",
            first_name="Bob",
            last_name="Brown",
            full_name="Bob Brown",
            party="R",
            state="TX",
        ),
        Legislator(
            bioguide_id="C000003",
            first_name="Carol",
            last_name="Chen",
            full_name="Carol Chen",
            party="D",
            state="NY",
        ),
    ]
    for leg in legislators:
        db_session.add(leg)
    await db_session.commit()
    return legislators


class TestNewsAPIRequestPooling:
    """Tests for NewsAPI request pooling functionality."""

    @pytest.mark.asyncio
    async def test_semaphore_limits_concurrent_requests(self):
        """Semaphore should limit concurrent API requests."""
        # The semaphore allows 3 concurrent requests
        assert _request_semaphore._value == 3

    @pytest.mark.asyncio
    async def test_batch_fetch_deduplicates_ids(self, db_session, sample_legislators):
        """Batch fetch should deduplicate bioguide IDs."""
        client = NewsAPIClient()

        with patch.object(client, "get_legislator_news") as mock_get:
            mock_get.return_value = MagicMock(data=[], is_stale=False)

            # Request same ID multiple times
            ids = ["A000001", "B000002", "A000001", "B000002", "A000001"]
            await client.get_news_for_multiple_legislators(db_session, ids)

            # Should only call get_legislator_news twice (unique IDs)
            assert mock_get.call_count == 2

    @pytest.mark.asyncio
    async def test_batch_fetch_returns_dict_mapping(self, db_session, sample_legislators):
        """Batch fetch should return dict mapping bioguide_id to response."""
        client = NewsAPIClient()

        with patch.object(client, "get_legislator_news") as mock_get:
            from app.services.cache_config import CachedResponse

            mock_get.side_effect = lambda db, bid, limit: CachedResponse.fresh(
                [{"title": f"News for {bid}"}]
            )

            ids = ["A000001", "B000002"]
            result = await client.get_news_for_multiple_legislators(db_session, ids)

            assert "A000001" in result
            assert "B000002" in result
            assert result["A000001"].data == [{"title": "News for A000001"}]
            assert result["B000002"].data == [{"title": "News for B000002"}]

    @pytest.mark.asyncio
    async def test_batch_fetch_handles_exceptions(self, db_session, sample_legislators):
        """Batch fetch should handle exceptions gracefully."""
        client = NewsAPIClient()

        with patch.object(client, "get_legislator_news") as mock_get:
            from app.services.cache_config import CachedResponse

            async def side_effect(db, bid, limit):
                if bid == "B000002":
                    raise Exception("API Error")
                return CachedResponse.fresh([{"title": f"News for {bid}"}])

            mock_get.side_effect = side_effect

            ids = ["A000001", "B000002", "C000003"]
            result = await client.get_news_for_multiple_legislators(db_session, ids)

            # Should have results for A and C, but not B
            assert "A000001" in result
            assert "B000002" not in result
            assert "C000003" in result

    @pytest.mark.asyncio
    async def test_batch_fetch_uses_lower_default_limit(self, db_session, sample_legislators):
        """Batch fetch should use lower article limit by default."""
        client = NewsAPIClient()

        with patch.object(client, "get_legislator_news") as mock_get:
            mock_get.return_value = MagicMock(data=[], is_stale=False)

            await client.get_news_for_multiple_legislators(
                db_session, ["A000001"]
            )

            # Should use limit=5 for batch queries (not 10)
            mock_get.assert_called_once()
            call_kwargs = mock_get.call_args
            assert call_kwargs[1]["limit"] == 5


class TestNewsAPICacheInvalidation:
    """Tests for NewsAPI cache invalidation."""

    @pytest.mark.asyncio
    async def test_invalidate_cache_clears_articles(self, db_session, sample_legislators):
        """invalidate_cache should clear cached articles."""
        client = NewsAPIClient()

        # Add some cached articles
        article = NewsArticle(
            legislator_bioguide_id="A000001",
            title="Test Article",
            url="https://example.com/article",
        )
        db_session.add(article)
        await db_session.commit()

        # Verify article exists
        from sqlalchemy import select
        result = await db_session.execute(
            select(NewsArticle).where(NewsArticle.legislator_bioguide_id == "A000001")
        )
        assert result.scalar_one_or_none() is not None

        # Invalidate cache
        await client.invalidate_cache(db_session, "A000001")

        # Verify article is gone
        result = await db_session.execute(
            select(NewsArticle).where(NewsArticle.legislator_bioguide_id == "A000001")
        )
        assert result.scalar_one_or_none() is None

    @pytest.mark.asyncio
    async def test_refresh_news_clears_and_fetches(self, db_session, sample_legislators):
        """refresh_news should clear cache and fetch fresh data."""
        client = NewsAPIClient()
        client.api_key = "test-key"  # Ensure API key is set

        # Add old cached article
        article = NewsArticle(
            legislator_bioguide_id="A000001",
            title="Old Article",
            url="https://example.com/old",
            cached_at=datetime.utcnow() - timedelta(days=1),
        )
        db_session.add(article)
        await db_session.commit()

        # Patch httpx at the module level where it's imported
        with patch("app.services.news_api.httpx.AsyncClient") as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.raise_for_status = MagicMock()
            mock_response.json.return_value = {
                "articles": [
                    {
                        "title": "New Article",
                        "url": "https://example.com/new",
                        "source": {"name": "Test Source"},
                    }
                ]
            }

            # Setup the async context manager mock
            mock_client_instance = MagicMock()
            mock_client_instance.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_class.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await client.refresh_news(db_session, "A000001")

            assert result.is_stale is False
            assert len(result.data) == 1
            assert result.data[0]["title"] == "New Article"


class TestNewsAPISemaphoreBehavior:
    """Tests for semaphore behavior in concurrent requests."""

    @pytest.mark.asyncio
    async def test_semaphore_allows_concurrent_up_to_limit(self):
        """Semaphore should allow up to 3 concurrent operations."""
        acquired_count = 0
        max_concurrent = 0

        async def acquire_and_hold():
            nonlocal acquired_count, max_concurrent
            async with _request_semaphore:
                acquired_count += 1
                max_concurrent = max(max_concurrent, acquired_count)
                await asyncio.sleep(0.1)
                acquired_count -= 1

        # Start 5 tasks concurrently
        tasks = [acquire_and_hold() for _ in range(5)]
        await asyncio.gather(*tasks)

        # Max concurrent should be limited to 3
        assert max_concurrent == 3
