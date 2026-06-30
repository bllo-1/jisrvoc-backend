"""Company repository for database operations."""

from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company import Company
from app.repositories.base import BaseRepository


class CompanyRepository(BaseRepository[Company]):
    """Repository for Company model operations."""

    def __init__(self, session: AsyncSession):
        """Initialize company repository."""
        super().__init__(Company, session)

    async def get_by_domain(self, domain: str) -> Optional[Company]:
        """Get company by domain.

        Args:
            domain: Email domain (e.g., "example.com")

        Returns:
            Company instance or None if not found
        """
        result = await self.session.execute(
            select(Company).where(Company.domain == domain)
        )
        return result.scalar_one_or_none()

    async def get_by_hubspot_id(self, hubspot_company_id: str) -> Optional[Company]:
        """Get company by HubSpot company ID.

        Args:
            hubspot_company_id: HubSpot company ID

        Returns:
            Company instance or None if not found
        """
        result = await self.session.execute(
            select(Company).where(Company.hubspot_company_id == hubspot_company_id)
        )
        return result.scalar_one_or_none()

    async def get_by_zendesk_id(self, zendesk_org_id: str) -> Optional[Company]:
        """Get company by Zendesk organization ID.

        Args:
            zendesk_org_id: Zendesk organization ID

        Returns:
            Company instance or None if not found
        """
        result = await self.session.execute(
            select(Company).where(Company.zendesk_org_id == zendesk_org_id)
        )
        return result.scalar_one_or_none()

    async def upsert_by_domain(
        self,
        domain: str,
        company_name: Optional[str] = None,
        hubspot_company_id: Optional[str] = None,
        zendesk_org_id: Optional[str] = None,
        industry: Optional[str] = None,
        arr: Optional[int] = None,
        decision_maker_count: Optional[int] = None,
        tier: Optional[str] = None,
    ) -> Company:
        """Create or update company by domain.

        Args:
            domain: Email domain
            company_name: Company name
            hubspot_company_id: HubSpot company ID
            zendesk_org_id: Zendesk organization ID
            industry: Industry
            arr: Annual recurring revenue
            decision_maker_count: Number of decision makers
            tier: Company tier (enterprise, mid-market, smb)

        Returns:
            Company instance
        """
        existing = await self.get_by_domain(domain)

        if existing:
            # Update existing company (only update non-None values)
            update_data = {}
            if company_name is not None:
                update_data["company_name"] = company_name
            if hubspot_company_id is not None:
                update_data["hubspot_company_id"] = hubspot_company_id
            if zendesk_org_id is not None:
                update_data["zendesk_org_id"] = zendesk_org_id
            if industry is not None:
                update_data["industry"] = industry
            if arr is not None:
                update_data["arr"] = arr
            if decision_maker_count is not None:
                update_data["decision_maker_count"] = decision_maker_count
            if tier is not None:
                update_data["tier"] = tier

            if update_data:
                return await self.update(existing, **update_data)
            return existing
        else:
            # Create new company
            return await self.create(
                domain=domain,
                company_name=company_name,
                hubspot_company_id=hubspot_company_id,
                zendesk_org_id=zendesk_org_id,
                industry=industry,
                arr=arr,
                decision_maker_count=decision_maker_count,
                tier=tier,
            )
