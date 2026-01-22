"""NewsAPI client for news articles about legislators.

Implements request pooling to minimize API calls given the 500 req/day limit.
"""

import asyncio
from datetime import datetime
from typing import Optional

import httpx
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import NewsArticle, Legislator
from app.services.cache_config import CacheTTL, CachedResponse, is_cache_valid

settings = get_settings()

# Semaphore to limit concurrent NewsAPI requests (avoid rate limiting)
_request_semaphore = asyncio.Semaphore(3)


class NewsAPIClient:
    """Client for NewsAPI.org."""

    def __init__(self):
        self.base_url = settings.news_api_base_url
        self.api_key = settings.news_api_key

    def _get_headers(self) -> dict:
        return {"X-Api-Key": self.api_key}

    async def get_legislator_news(
        self, db: AsyncSession, bioguide_id: str, limit: int = 10
    ) -> CachedResponse[list[dict]]:
        """Get news articles mentioning a legislator.

        Returns:
            CachedResponse containing news articles. Check is_stale flag
            to determine if data may be outdated due to API failure.
        """
        # Check for fresh cached data first
        cached = await self._get_cached_news(db, bioguide_id)
        if cached:
            return CachedResponse.fresh([self._article_to_dict(a) for a in cached[:limit]])

        result = await db.execute(
            select(Legislator).where(Legislator.bioguide_id == bioguide_id)
        )
        legislator = result.scalar_one_or_none()
        if not legislator:
            return CachedResponse.fresh([])

        search_query = f'"{legislator.full_name}"'

        if not self.api_key:
            return CachedResponse.fresh([])

        # Try to fetch fresh data from API (with semaphore to limit concurrency)
        try:
            async with _request_semaphore:
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        f"{self.base_url}/everything",
                        headers=self._get_headers(),
                        params={
                            "q": search_query,
                            "language": "en",
                            "sortBy": "publishedAt",
                            "pageSize": limit,
                        },
                        timeout=30.0,
                    )
                    if response.status_code == 401:
                        # Auth error - try stale cache
                        raise httpx.HTTPStatusError(
                            "Unauthorized", request=response.request, response=response
                        )
                    response.raise_for_status()
                    data = response.json()

            articles = data.get("articles", [])

            await self._clear_old_cache(db, bioguide_id)
            for article in articles:
                await self._cache_article(db, bioguide_id, article)

            return CachedResponse.fresh(articles)

        except (httpx.HTTPError, httpx.TimeoutException):
            # API failed - try to return stale cached data
            stale_cached = await self._get_any_cached_news(db, bioguide_id)
            if stale_cached:
                return CachedResponse.stale(
                    [self._article_to_dict(a) for a in stale_cached[:limit]],
                    data_type="news articles"
                )
            # No cached data available
            return CachedResponse.fresh([])

    async def get_news_for_multiple_legislators(
        self, db: AsyncSession, bioguide_ids: list[str], limit: int = 5
    ) -> dict[str, CachedResponse[list[dict]]]:
        """Fetch news for multiple legislators concurrently with request pooling.

        This method efficiently batches requests using asyncio.gather and
        deduplicates requests for the same legislator. Use this when loading
        news for multiple legislators (e.g., search results, favorites list).

        Args:
            db: Database session
            bioguide_ids: List of legislator bioguide IDs
            limit: Max articles per legislator (default 5 for batch queries)

        Returns:
            Dict mapping bioguide_id to CachedResponse with news articles
        """
        # Deduplicate bioguide_ids
        unique_ids = list(dict.fromkeys(bioguide_ids))

        # Create tasks for all legislators
        async def fetch_one(bioguide_id: str) -> tuple[str, CachedResponse[list[dict]]]:
            result = await self.get_legislator_news(db, bioguide_id, limit=limit)
            return (bioguide_id, result)

        # Execute all requests concurrently (semaphore limits actual API calls)
        tasks = [fetch_one(bid) for bid in unique_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Build result dict, handling any exceptions
        output: dict[str, CachedResponse[list[dict]]] = {}
        for result in results:
            if isinstance(result, Exception):
                # Skip failed requests - they'll return empty in individual calls
                continue
            bioguide_id, response = result
            output[bioguide_id] = response

        return output

    async def invalidate_cache(self, db: AsyncSession, bioguide_id: str) -> None:
        """Invalidate cached news for a legislator.

        Call this when user explicitly requests a refresh. The next call to
        get_legislator_news will fetch fresh data from the API.
        """
        await self._clear_old_cache(db, bioguide_id)

    async def refresh_news(
        self, db: AsyncSession, bioguide_id: str, limit: int = 10
    ) -> CachedResponse[list[dict]]:
        """Force refresh news for a legislator, bypassing cache.

        Use this for explicit user-triggered refresh buttons.
        """
        # Clear existing cache first
        await self._clear_old_cache(db, bioguide_id)

        # Fetch fresh data (get_legislator_news will see no cache and fetch new)
        return await self.get_legislator_news(db, bioguide_id, limit)

    async def _get_cached_news(
        self, db: AsyncSession, bioguide_id: str
    ) -> list[NewsArticle]:
        """Get cached news if not expired (1 hour TTL)."""
        result = await db.execute(
            select(NewsArticle)
            .where(NewsArticle.legislator_bioguide_id == bioguide_id)
            .order_by(NewsArticle.published_at.desc())
        )
        articles = list(result.scalars().all())

        if articles and is_cache_valid(articles[0].cached_at, CacheTTL.NEWS):
            return articles

        return []

    async def _get_any_cached_news(
        self, db: AsyncSession, bioguide_id: str
    ) -> list[NewsArticle]:
        """Get cached news regardless of TTL (for fallback on API failure)."""
        result = await db.execute(
            select(NewsArticle)
            .where(NewsArticle.legislator_bioguide_id == bioguide_id)
            .order_by(NewsArticle.published_at.desc())
        )
        return list(result.scalars().all())

    async def _clear_old_cache(self, db: AsyncSession, bioguide_id: str) -> None:
        """Clear old cached articles for a legislator."""
        await db.execute(
            delete(NewsArticle).where(
                NewsArticle.legislator_bioguide_id == bioguide_id
            )
        )
        await db.commit()

    async def _cache_article(
        self, db: AsyncSession, bioguide_id: str, article_data: dict
    ) -> None:
        """Cache a news article."""
        published_str = article_data.get("publishedAt")
        published_at = None
        if published_str:
            try:
                published_at = datetime.fromisoformat(published_str.replace("Z", "+00:00"))
            except ValueError:
                pass

        article = NewsArticle(
            legislator_bioguide_id=bioguide_id,
            title=article_data.get("title", ""),
            description=article_data.get("description"),
            url=article_data.get("url", ""),
            source_name=article_data.get("source", {}).get("name"),
            author=article_data.get("author"),
            image_url=article_data.get("urlToImage"),
            published_at=published_at,
        )
        db.add(article)
        await db.commit()

    def _article_to_dict(self, article: NewsArticle) -> dict:
        """Convert NewsArticle model to dict."""
        return {
            "title": article.title,
            "description": article.description,
            "url": article.url,
            "source": {"name": article.source_name},
            "author": article.author,
            "urlToImage": article.image_url,
            "publishedAt": article.published_at.isoformat() if article.published_at else None,
        }


news_client = NewsAPIClient()
