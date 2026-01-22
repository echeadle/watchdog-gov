"""Unified cache invalidation service for per-section refresh buttons.

Provides a single interface for invalidating caches by data type, making it
easy for routes to implement refresh functionality.
"""

from enum import Enum
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.congress_api import congress_client
from app.services.fec_api import fec_client
from app.services.news_api import news_client
from app.services.cache_config import CachedResponse


class CacheSection(str, Enum):
    """Cacheable data sections that can be refreshed."""

    MEMBER = "member"
    BILLS = "bills"
    VOTES = "votes"
    FINANCE = "finance"
    NEWS = "news"


async def invalidate_cache(
    db: AsyncSession, bioguide_id: str, section: CacheSection
) -> None:
    """Invalidate cache for a specific section.

    Args:
        db: Database session
        bioguide_id: Legislator bioguide ID
        section: Which cache section to invalidate
    """
    if section == CacheSection.MEMBER:
        await congress_client.invalidate_member_cache(db, bioguide_id)
    elif section == CacheSection.BILLS:
        await congress_client.invalidate_bills_cache(db, bioguide_id)
    elif section == CacheSection.FINANCE:
        await fec_client.invalidate_finance_cache(db, bioguide_id)
    elif section == CacheSection.NEWS:
        await news_client.invalidate_cache(db, bioguide_id)
    # VOTES doesn't have dedicated cache per legislator currently


async def refresh_section(
    db: AsyncSession, bioguide_id: str, section: CacheSection
) -> CachedResponse[Any]:
    """Refresh a specific section, invalidating cache and fetching fresh data.

    Args:
        db: Database session
        bioguide_id: Legislator bioguide ID
        section: Which section to refresh

    Returns:
        CachedResponse with fresh data (or stale data if API fails)
    """
    if section == CacheSection.MEMBER:
        return await congress_client.refresh_member(db, bioguide_id)
    elif section == CacheSection.BILLS:
        bills = await congress_client.refresh_bills(db, bioguide_id)
        return CachedResponse.fresh(bills)
    elif section == CacheSection.FINANCE:
        return await fec_client.refresh_finances(db, bioguide_id)
    elif section == CacheSection.NEWS:
        return await news_client.refresh_news(db, bioguide_id)
    else:
        # Default for unsupported sections
        return CachedResponse.fresh(None)


async def refresh_all(db: AsyncSession, bioguide_id: str) -> dict[str, bool]:
    """Refresh all cacheable sections for a legislator.

    Returns:
        Dict mapping section name to success status
    """
    results = {}

    for section in CacheSection:
        try:
            await refresh_section(db, bioguide_id, section)
            results[section.value] = True
        except Exception:
            results[section.value] = False

    return results
