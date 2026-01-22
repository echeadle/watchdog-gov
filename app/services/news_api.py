"""NewsAPI client for news articles about legislators."""

from datetime import datetime
from typing import Optional

import httpx
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import NewsArticle, Legislator
from app.services.cache_config import CacheTTL, CachedResponse, is_cache_valid

settings = get_settings()


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

        # Try to fetch fresh data from API
        try:
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
