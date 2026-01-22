"""Congress.gov API client for member, bill, and vote data."""

from datetime import datetime
from typing import Optional

import httpx
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import Legislator, Bill, Vote, VotePosition
from app.services.cache_config import CacheTTL, CachedResponse, is_cache_valid
from app.services.fuzzy_search import fuzzy_search_legislators, fuzzy_search

settings = get_settings()


class CongressAPIClient:
    """Client for Congress.gov API."""

    def __init__(self):
        self.base_url = settings.congress_api_base_url
        self.api_key = settings.congress_api_key

    def _get_headers(self) -> dict:
        return {"X-Api-Key": self.api_key}

    async def search_members(
        self, db: AsyncSession, query: Optional[str] = None, state: Optional[str] = None,
        use_fuzzy: bool = True, limit: int = 20
    ) -> list[dict]:
        """Search for members by name or state with fuzzy matching.

        Args:
            db: Database session
            query: Search query (name, partial name, or state)
            state: Optional state filter (2-letter code)
            use_fuzzy: Enable fuzzy matching for typo tolerance (default True)
            limit: Maximum results to return

        Returns:
            List of matching members sorted by relevance
        """
        params = {"format": "json", "limit": 100}  # Fetch more for better fuzzy results

        if state:
            params["currentMember"] = "true"

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/member",
                headers=self._get_headers(),
                params=params,
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()

        members = data.get("members", [])

        # Filter by state first if specified
        if state:
            state_upper = state.upper()
            members = [m for m in members if m.get("state") == state_upper]

        # Apply fuzzy matching if query provided
        if query and use_fuzzy:
            # Use fuzzy search for better matching
            matched = fuzzy_search_legislators(query, members, threshold=0.3, limit=limit)
            members = [m for m, score in matched]
        elif query:
            # Fall back to simple substring matching
            query_lower = query.lower()
            members = [
                m for m in members
                if query_lower in m.get("name", "").lower()
                or query_lower in m.get("state", "").lower()
            ][:limit]

        # Cache all matched members
        for member in members:
            await self._cache_member(db, member)

        return members

    async def search_cached_members(
        self, db: AsyncSession, query: str, limit: int = 10
    ) -> list[dict]:
        """Search cached legislators in database with fuzzy matching.

        This is faster than API search and works offline. Use for autocomplete.
        """
        # Get all cached legislators
        result = await db.execute(
            select(Legislator).where(Legislator.is_current == True).limit(500)
        )
        legislators = result.scalars().all()

        if not legislators:
            return []

        # Convert to dicts for fuzzy search
        leg_dicts = [self._member_to_dict(leg) for leg in legislators]

        # Fuzzy search
        matched = fuzzy_search(
            query=query,
            items=leg_dicts,
            key_func=lambda m: m.get("directOrderName", ""),
            state_func=lambda m: m.get("state", ""),
            threshold=0.3,
            limit=limit,
        )

        return [m for m, score in matched]

    async def get_member(
        self, db: AsyncSession, bioguide_id: str
    ) -> CachedResponse[Optional[dict]]:
        """Get detailed member information.

        Returns:
            CachedResponse containing member data. Check is_stale flag
            to determine if data may be outdated due to API failure.
        """
        # Check for fresh cached data first
        cached = await self._get_cached_member(db, bioguide_id)
        if cached:
            return CachedResponse.fresh(self._member_to_dict(cached))

        # Try to fetch fresh data from API
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/member/{bioguide_id}",
                    headers=self._get_headers(),
                    params={"format": "json"},
                    timeout=30.0,
                )
                if response.status_code == 404:
                    return CachedResponse.fresh(None)
                response.raise_for_status()
                data = response.json()

            member = data.get("member")
            if member:
                await self._cache_member_detail(db, member)
                return CachedResponse.fresh(member)

            return CachedResponse.fresh(None)

        except (httpx.HTTPError, httpx.TimeoutException):
            # API failed - try to return stale cached data
            stale_cached = await self._get_any_cached_member(db, bioguide_id)
            if stale_cached:
                return CachedResponse.stale(
                    self._member_to_dict(stale_cached),
                    data_type="legislator information"
                )
            # No cached data available, return None
            return CachedResponse.fresh(None)

    async def get_member_bills(
        self, db: AsyncSession, bioguide_id: str, limit: int = 20
    ) -> list[dict]:
        """Get bills sponsored by a member."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/member/{bioguide_id}/sponsored-legislation",
                headers=self._get_headers(),
                params={"format": "json", "limit": limit},
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()

        bills = data.get("sponsoredLegislation", [])

        for bill in bills:
            await self._cache_bill(db, bill, bioguide_id, is_cosponsored=False)

        return bills

    async def get_member_cosponsored_bills(
        self, db: AsyncSession, bioguide_id: str, limit: int = 20
    ) -> list[dict]:
        """Get bills cosponsored by a member."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/member/{bioguide_id}/cosponsored-legislation",
                headers=self._get_headers(),
                params={"format": "json", "limit": limit},
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()

        bills = data.get("cosponsoredLegislation", [])

        for bill in bills:
            await self._cache_bill(db, bill, bioguide_id, is_cosponsored=True)

        return bills

    async def get_recent_votes(
        self, db: AsyncSession, chamber: str = "senate", limit: int = 20
    ) -> list[dict]:
        """Get recent roll call votes for a chamber."""
        chamber_path = "senate" if chamber.lower() == "senate" else "house"

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/roll-call-vote/{chamber_path}",
                headers=self._get_headers(),
                params={"format": "json", "limit": limit},
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()

        return data.get("roll-call-votes", [])

    async def _get_cached_member(
        self, db: AsyncSession, bioguide_id: str
    ) -> Optional[Legislator]:
        """Get cached member if not expired."""
        result = await db.execute(
            select(Legislator).where(Legislator.bioguide_id == bioguide_id)
        )
        member = result.scalar_one_or_none()

        if member and is_cache_valid(member.cached_at, CacheTTL.MEMBERS):
            return member

        return None

    async def _get_any_cached_member(
        self, db: AsyncSession, bioguide_id: str
    ) -> Optional[Legislator]:
        """Get cached member regardless of TTL (for fallback on API failure)."""
        result = await db.execute(
            select(Legislator).where(Legislator.bioguide_id == bioguide_id)
        )
        return result.scalar_one_or_none()

    async def invalidate_member_cache(self, db: AsyncSession, bioguide_id: str) -> None:
        """Invalidate cached data for a member by resetting cached_at.

        This forces the next request to fetch fresh data from the API.
        """
        result = await db.execute(
            select(Legislator).where(Legislator.bioguide_id == bioguide_id)
        )
        member = result.scalar_one_or_none()
        if member:
            member.cached_at = None
            await db.commit()

    async def invalidate_bills_cache(self, db: AsyncSession, bioguide_id: str) -> None:
        """Invalidate cached bills for a member."""
        await db.execute(
            delete(Bill).where(Bill.sponsor_bioguide_id == bioguide_id)
        )
        await db.commit()

    async def refresh_member(
        self, db: AsyncSession, bioguide_id: str
    ) -> CachedResponse[Optional[dict]]:
        """Force refresh member data, bypassing cache."""
        await self.invalidate_member_cache(db, bioguide_id)
        return await self.get_member(db, bioguide_id)

    async def refresh_bills(
        self, db: AsyncSession, bioguide_id: str, limit: int = 20
    ) -> list[dict]:
        """Force refresh bills for a member, bypassing cache."""
        await self.invalidate_bills_cache(db, bioguide_id)
        return await self.get_member_bills(db, bioguide_id, limit)

    async def _cache_member(self, db: AsyncSession, member_data: dict) -> None:
        """Cache member data from search results."""
        bioguide_id = member_data.get("bioguideId")
        if not bioguide_id:
            return

        result = await db.execute(
            select(Legislator).where(Legislator.bioguide_id == bioguide_id)
        )
        existing = result.scalar_one_or_none()

        name = member_data.get("name", "")
        parts = name.split(", ")
        last_name = parts[0] if parts else ""
        first_name = parts[1] if len(parts) > 1 else ""

        terms = member_data.get("terms", {}).get("item", [])
        latest_term = terms[-1] if terms else {}

        if existing:
            existing.first_name = first_name
            existing.last_name = last_name
            existing.full_name = name
            existing.party = member_data.get("partyName")
            existing.state = member_data.get("state")
            existing.chamber = latest_term.get("chamber")
            existing.cached_at = datetime.utcnow()
        else:
            legislator = Legislator(
                bioguide_id=bioguide_id,
                first_name=first_name,
                last_name=last_name,
                full_name=name,
                party=member_data.get("partyName"),
                state=member_data.get("state"),
                chamber=latest_term.get("chamber"),
                image_url=member_data.get("depiction", {}).get("imageUrl"),
                url=member_data.get("url"),
            )
            db.add(legislator)

        await db.commit()

    async def _cache_member_detail(self, db: AsyncSession, member_data: dict) -> None:
        """Cache detailed member data."""
        bioguide_id = member_data.get("bioguideId")
        if not bioguide_id:
            return

        result = await db.execute(
            select(Legislator).where(Legislator.bioguide_id == bioguide_id)
        )
        existing = result.scalar_one_or_none()

        direct_name = member_data.get("directOrderName", "")
        first_name = member_data.get("firstName", "")
        last_name = member_data.get("lastName", "")

        terms = member_data.get("terms", [])
        latest_term = terms[-1] if terms else {}

        address = member_data.get("addressInformation", {})
        office_address = address.get("officeAddress")
        phone = address.get("phoneNumber")

        depiction = member_data.get("depiction", {})
        image_url = depiction.get("imageUrl") if depiction else None

        if existing:
            existing.first_name = first_name
            existing.last_name = last_name
            existing.full_name = direct_name
            existing.party = member_data.get("partyHistory", [{}])[-1].get("partyName")
            existing.state = latest_term.get("stateCode")
            existing.district = str(latest_term.get("district")) if latest_term.get("district") else None
            existing.chamber = latest_term.get("chamber")
            existing.image_url = image_url
            existing.url = member_data.get("officialWebsiteUrl")
            existing.office_address = office_address
            existing.phone = phone
            existing.cached_at = datetime.utcnow()
        else:
            legislator = Legislator(
                bioguide_id=bioguide_id,
                first_name=first_name,
                last_name=last_name,
                full_name=direct_name,
                party=member_data.get("partyHistory", [{}])[-1].get("partyName"),
                state=latest_term.get("stateCode"),
                district=str(latest_term.get("district")) if latest_term.get("district") else None,
                chamber=latest_term.get("chamber"),
                image_url=image_url,
                url=member_data.get("officialWebsiteUrl"),
                office_address=office_address,
                phone=phone,
            )
            db.add(legislator)

        await db.commit()

    async def _cache_bill(
        self, db: AsyncSession, bill_data: dict, sponsor_bioguide_id: str, is_cosponsored: bool
    ) -> None:
        """Cache bill data."""
        congress = bill_data.get("congress")
        bill_type = bill_data.get("type", "").lower()
        bill_number = bill_data.get("number")

        if not all([congress, bill_type, bill_number]):
            return

        result = await db.execute(
            select(Bill).where(
                Bill.congress == congress,
                Bill.bill_type == bill_type,
                Bill.bill_number == bill_number,
            )
        )
        existing = result.scalar_one_or_none()

        latest_action = bill_data.get("latestAction", {})

        if existing:
            existing.title = bill_data.get("title", "")
            existing.latest_action_text = latest_action.get("text")
            existing.cached_at = datetime.utcnow()
        else:
            introduced_str = bill_data.get("introducedDate")
            introduced_date = None
            if introduced_str:
                try:
                    introduced_date = datetime.strptime(introduced_str, "%Y-%m-%d").date()
                except ValueError:
                    pass

            action_date_str = latest_action.get("actionDate")
            action_date = None
            if action_date_str:
                try:
                    action_date = datetime.strptime(action_date_str, "%Y-%m-%d").date()
                except ValueError:
                    pass

            bill = Bill(
                congress=congress,
                bill_type=bill_type,
                bill_number=bill_number,
                title=bill_data.get("title", ""),
                introduced_date=introduced_date,
                latest_action_date=action_date,
                latest_action_text=latest_action.get("text"),
                policy_area=bill_data.get("policyArea", {}).get("name") if bill_data.get("policyArea") else None,
                url=bill_data.get("url"),
                sponsor_bioguide_id=sponsor_bioguide_id if not is_cosponsored else None,
                is_cosponsored=is_cosponsored,
            )
            db.add(bill)

        await db.commit()

    def _member_to_dict(self, member: Legislator) -> dict:
        """Convert Legislator model to dict."""
        return {
            "bioguideId": member.bioguide_id,
            "firstName": member.first_name,
            "lastName": member.last_name,
            "directOrderName": member.full_name,
            "partyName": member.party,
            "state": member.state,
            "district": member.district,
            "chamber": member.chamber,
            "depiction": {"imageUrl": member.image_url} if member.image_url else None,
            "officialWebsiteUrl": member.url,
            "addressInformation": {
                "officeAddress": member.office_address,
                "phoneNumber": member.phone,
            },
        }


congress_client = CongressAPIClient()
