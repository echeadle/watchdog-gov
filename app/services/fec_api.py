"""OpenFEC API client for campaign finance data."""

from datetime import datetime
from typing import Optional

import httpx
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import CampaignFinance, Expenditure, Legislator
from app.services.cache_config import CacheTTL, CachedResponse, is_cache_valid

settings = get_settings()


class FECAPIClient:
    """Client for OpenFEC API."""

    def __init__(self):
        self.base_url = settings.fec_api_base_url
        self.api_key = settings.fec_api_key

    def _get_params(self, **kwargs) -> dict:
        params = {"api_key": self.api_key}
        params.update(kwargs)
        return params

    async def find_candidate_id(
        self, db: AsyncSession, legislator: Legislator
    ) -> Optional[str]:
        """Find FEC candidate ID for a legislator."""
        result = await db.execute(
            select(CampaignFinance).where(
                CampaignFinance.legislator_bioguide_id == legislator.bioguide_id
            )
        )
        existing = result.scalar_one_or_none()
        if existing and existing.fec_candidate_id:
            return existing.fec_candidate_id

        name = f"{legislator.last_name}, {legislator.first_name}"
        state = legislator.state

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/candidates/search/",
                params=self._get_params(
                    q=name,
                    state=state,
                    sort="-election_years",
                    per_page=5,
                ),
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()

        candidates = data.get("results", [])
        if candidates:
            return candidates[0].get("candidate_id")

        return None

    async def get_candidate_finances(
        self, db: AsyncSession, bioguide_id: str
    ) -> CachedResponse[Optional[dict]]:
        """Get campaign finance summary for a legislator.

        Returns:
            CachedResponse containing finance data. Check is_stale flag
            to determine if data may be outdated due to API failure.
        """
        # Check for fresh cached data first
        cached = await self._get_cached_finance(db, bioguide_id)
        if cached:
            return CachedResponse.fresh(self._finance_to_dict(cached))

        result = await db.execute(
            select(Legislator).where(Legislator.bioguide_id == bioguide_id)
        )
        legislator = result.scalar_one_or_none()
        if not legislator:
            return CachedResponse.fresh(None)

        # Try to fetch fresh data from API
        try:
            candidate_id = await self.find_candidate_id(db, legislator)
            if not candidate_id:
                return CachedResponse.fresh(None)

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/candidate/{candidate_id}/totals/",
                    params=self._get_params(per_page=1, sort="-cycle"),
                    timeout=30.0,
                )
                response.raise_for_status()
                data = response.json()

            totals = data.get("results", [])
            if not totals:
                return CachedResponse.fresh(None)

            finance_data = totals[0]
            await self._cache_finance(db, bioguide_id, candidate_id, finance_data)

            return CachedResponse.fresh(finance_data)

        except (httpx.HTTPError, httpx.TimeoutException):
            # API failed - try to return stale cached data
            stale_cached = await self._get_any_cached_finance(db, bioguide_id)
            if stale_cached:
                return CachedResponse.stale(
                    self._finance_to_dict(stale_cached),
                    data_type="campaign finance data"
                )
            # No cached data available
            return CachedResponse.fresh(None)

    async def get_expenditures(
        self, db: AsyncSession, bioguide_id: str, limit: int = 50
    ) -> list[dict]:
        """Get detailed expenditure records."""
        result = await db.execute(
            select(CampaignFinance).where(
                CampaignFinance.legislator_bioguide_id == bioguide_id
            )
        )
        finance = result.scalar_one_or_none()

        if not finance:
            await self.get_candidate_finances(db, bioguide_id)
            result = await db.execute(
                select(CampaignFinance).where(
                    CampaignFinance.legislator_bioguide_id == bioguide_id
                )
            )
            finance = result.scalar_one_or_none()

        if not finance or not finance.committee_id:
            return []

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/schedules/schedule_b/",
                params=self._get_params(
                    committee_id=finance.committee_id,
                    per_page=limit,
                    sort="-disbursement_date",
                ),
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()

        expenditures = data.get("results", [])

        for exp in expenditures:
            await self._cache_expenditure(db, finance.id, exp)

        return expenditures

    async def request_expenditure_details(
        self, db: AsyncSession, bioguide_id: str
    ) -> bool:
        """Request full expenditure details for a legislator."""
        finance = await self.get_candidate_finances(db, bioguide_id)
        if not finance:
            return False

        await self.get_expenditures(db, bioguide_id, limit=100)
        return True

    async def _get_cached_finance(
        self, db: AsyncSession, bioguide_id: str
    ) -> Optional[CampaignFinance]:
        """Get cached finance data if not expired (weekly TTL)."""
        result = await db.execute(
            select(CampaignFinance).where(
                CampaignFinance.legislator_bioguide_id == bioguide_id
            )
        )
        finance = result.scalar_one_or_none()

        if finance and is_cache_valid(finance.cached_at, CacheTTL.FINANCE):
            return finance

        return None

    async def _get_any_cached_finance(
        self, db: AsyncSession, bioguide_id: str
    ) -> Optional[CampaignFinance]:
        """Get cached finance data regardless of TTL (for fallback on API failure)."""
        result = await db.execute(
            select(CampaignFinance).where(
                CampaignFinance.legislator_bioguide_id == bioguide_id
            )
        )
        return result.scalar_one_or_none()

    async def invalidate_finance_cache(self, db: AsyncSession, bioguide_id: str) -> None:
        """Invalidate cached finance data for a legislator.

        Also clears associated expenditure records.
        """
        result = await db.execute(
            select(CampaignFinance).where(
                CampaignFinance.legislator_bioguide_id == bioguide_id
            )
        )
        finance = result.scalar_one_or_none()
        if finance:
            # Delete expenditures first (foreign key constraint)
            await db.execute(
                delete(Expenditure).where(Expenditure.campaign_finance_id == finance.id)
            )
            # Delete finance record
            await db.execute(
                delete(CampaignFinance).where(CampaignFinance.id == finance.id)
            )
            await db.commit()

    async def refresh_finances(
        self, db: AsyncSession, bioguide_id: str
    ) -> CachedResponse[Optional[dict]]:
        """Force refresh finance data, bypassing cache."""
        await self.invalidate_finance_cache(db, bioguide_id)
        return await self.get_candidate_finances(db, bioguide_id)

    async def _cache_finance(
        self,
        db: AsyncSession,
        bioguide_id: str,
        candidate_id: str,
        finance_data: dict,
    ) -> None:
        """Cache campaign finance data."""
        result = await db.execute(
            select(CampaignFinance).where(
                CampaignFinance.legislator_bioguide_id == bioguide_id
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.fec_candidate_id = candidate_id
            existing.committee_id = finance_data.get("committee_id")
            existing.cycle = finance_data.get("cycle")
            existing.total_receipts = finance_data.get("receipts")
            existing.total_disbursements = finance_data.get("disbursements")
            existing.cash_on_hand = finance_data.get("cash_on_hand_end_period")
            existing.debt = finance_data.get("debts_owed_by_committee")
            existing.individual_contributions = finance_data.get("individual_contributions")
            existing.pac_contributions = finance_data.get("other_political_committee_contributions")
            existing.party_contributions = finance_data.get("political_party_committee_contributions")
            existing.cached_at = datetime.utcnow()
        else:
            finance = CampaignFinance(
                legislator_bioguide_id=bioguide_id,
                fec_candidate_id=candidate_id,
                committee_id=finance_data.get("committee_id"),
                cycle=finance_data.get("cycle"),
                total_receipts=finance_data.get("receipts"),
                total_disbursements=finance_data.get("disbursements"),
                cash_on_hand=finance_data.get("cash_on_hand_end_period"),
                debt=finance_data.get("debts_owed_by_committee"),
                individual_contributions=finance_data.get("individual_contributions"),
                pac_contributions=finance_data.get("other_political_committee_contributions"),
                party_contributions=finance_data.get("political_party_committee_contributions"),
            )
            db.add(finance)

        await db.commit()

    async def _cache_expenditure(
        self, db: AsyncSession, campaign_finance_id: int, exp_data: dict
    ) -> None:
        """Cache individual expenditure record."""
        disbursement_date = None
        date_str = exp_data.get("disbursement_date")
        if date_str:
            try:
                disbursement_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                pass

        expenditure = Expenditure(
            campaign_finance_id=campaign_finance_id,
            payee_name=exp_data.get("recipient_name"),
            purpose=exp_data.get("disbursement_description"),
            amount=exp_data.get("disbursement_amount"),
            expenditure_date=disbursement_date,
            category=exp_data.get("disbursement_type_description"),
        )
        db.add(expenditure)
        await db.commit()

    def _finance_to_dict(self, finance: CampaignFinance) -> dict:
        """Convert CampaignFinance model to dict."""
        return {
            "candidate_id": finance.fec_candidate_id,
            "committee_id": finance.committee_id,
            "cycle": finance.cycle,
            "receipts": finance.total_receipts,
            "disbursements": finance.total_disbursements,
            "cash_on_hand_end_period": finance.cash_on_hand,
            "debts_owed_by_committee": finance.debt,
            "individual_contributions": finance.individual_contributions,
            "other_political_committee_contributions": finance.pac_contributions,
            "political_party_committee_contributions": finance.party_contributions,
        }


fec_client = FECAPIClient()
