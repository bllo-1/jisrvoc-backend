"""Customer repository for database operations."""

from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.customer_new import Customer
from app.repositories.base import BaseRepository


class CustomerRepository(BaseRepository[Customer]):
    """Repository for Customer model operations."""

    def __init__(self, session: AsyncSession):
        """Initialize customer repository."""
        super().__init__(Customer, session)

    async def get_by_email(self, email: str) -> Optional[Customer]:
        """Get customer by email.

        Args:
            email: Customer email address

        Returns:
            Customer instance or None if not found
        """
        result = await self.session.execute(
            select(Customer).where(Customer.email == email)
        )
        return result.scalar_one_or_none()

    async def get_by_hubspot_id(self, hubspot_contact_id: str) -> Optional[Customer]:
        """Get customer by HubSpot contact ID.

        Args:
            hubspot_contact_id: HubSpot contact ID

        Returns:
            Customer instance or None if not found
        """
        result = await self.session.execute(
            select(Customer).where(Customer.hubspot_contact_id == hubspot_contact_id)
        )
        return result.scalar_one_or_none()

    async def get_by_zendesk_id(self, zendesk_user_id: str) -> Optional[Customer]:
        """Get customer by Zendesk user ID.

        Args:
            zendesk_user_id: Zendesk user ID

        Returns:
            Customer instance or None if not found
        """
        result = await self.session.execute(
            select(Customer).where(Customer.zendesk_user_id == zendesk_user_id)
        )
        return result.scalar_one_or_none()

    async def upsert_by_email(
        self,
        email: str,
        name: Optional[str] = None,
        company_id: Optional[int] = None,
        hubspot_contact_id: Optional[str] = None,
        zendesk_user_id: Optional[str] = None,
        role: Optional[str] = None,
        tier: Optional[str] = None,
    ) -> Customer:
        """Create or update customer by email.

        Args:
            email: Customer email
            name: Customer name
            company_id: Company ID
            hubspot_contact_id: HubSpot contact ID
            zendesk_user_id: Zendesk user ID
            role: Customer role
            tier: Customer tier

        Returns:
            Customer instance
        """
        existing = await self.get_by_email(email)

        if existing:
            # Update existing customer (only update non-None values)
            update_data = {}
            if name is not None:
                update_data["name"] = name
            if company_id is not None:
                update_data["company_id"] = company_id
            if hubspot_contact_id is not None:
                update_data["hubspot_contact_id"] = hubspot_contact_id
            if zendesk_user_id is not None:
                update_data["zendesk_user_id"] = zendesk_user_id
            if role is not None:
                update_data["role"] = role
            if tier is not None:
                update_data["tier"] = tier

            if update_data:
                return await self.update(existing, **update_data)
            return existing
        else:
            # Create new customer
            return await self.create(
                email=email,
                name=name,
                company_id=company_id,
                hubspot_contact_id=hubspot_contact_id,
                zendesk_user_id=zendesk_user_id,
                role=role,
                tier=tier,
            )
