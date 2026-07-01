"""Identity resolution service - matches feedback to customers across sources."""

import logging
from typing import Optional
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.customer import CustomerRepository
from app.repositories.feedback import FeedbackRepository
from app.models.feedback import Feedback
from app.models.customer_new import Customer


logger = logging.getLogger(__name__)


class IdentityResolutionService:
    """
    Service to resolve customer identities across feedback sources.

    Matches feedback to customers by:
    1. Email address (primary identifier)
    2. External IDs (HubSpot contact ID, Zendesk user ID)
    3. Creates new customer records for unknown identities
    """

    def __init__(self, session: AsyncSession):
        """Initialize identity resolution service.

        Args:
            session: Database session
        """
        self.session = session
        self.customer_repo = CustomerRepository(session)
        self.feedback_repo = FeedbackRepository(session)

    async def resolve_feedback_identity(
        self,
        feedback: Feedback,
        email: Optional[str] = None,
        name: Optional[str] = None,
        hubspot_contact_id: Optional[str] = None,
        zendesk_user_id: Optional[str] = None,
    ) -> Optional[Customer]:
        """
        Resolve customer identity for a feedback item.

        Args:
            feedback: Feedback instance to resolve
            email: Customer email address
            name: Customer name
            hubspot_contact_id: HubSpot contact ID
            zendesk_user_id: Zendesk user ID

        Returns:
            Customer instance (existing or newly created), or None if no identity info provided
        """
        # Use existing email from feedback if not provided
        email = email or feedback.customer_email

        if not email and not hubspot_contact_id and not zendesk_user_id:
            logger.debug(f"No identity information provided for feedback {feedback.id}")
            return None

        customer = None

        # Try to find customer by email first (primary identifier)
        if email:
            customer = await self.customer_repo.get_by_email(email)
            if customer:
                logger.info(f"Matched feedback {feedback.id} to customer {customer.id} by email")

        # Try HubSpot ID if not found by email
        if not customer and hubspot_contact_id:
            customer = await self.customer_repo.get_by_hubspot_id(hubspot_contact_id)
            if customer:
                logger.info(f"Matched feedback {feedback.id} to customer {customer.id} by HubSpot ID")

        # Try Zendesk ID if still not found
        if not customer and zendesk_user_id:
            customer = await self.customer_repo.get_by_zendesk_id(zendesk_user_id)
            if customer:
                logger.info(f"Matched feedback {feedback.id} to customer {customer.id} by Zendesk ID")

        # Create new customer if not found
        if not customer and email:
            logger.info(f"Creating new customer for email {email}")
            customer = await self.customer_repo.upsert_by_email(
                email=email,
                name=name,
                hubspot_contact_id=hubspot_contact_id,
                zendesk_user_id=zendesk_user_id,
            )
            await self.session.commit()

        # Link feedback to customer
        if customer:
            feedback.customer_id = customer.id
            feedback.customer_email = email or customer.email
            await self.session.commit()
            logger.info(f"Linked feedback {feedback.id} to customer {customer.id}")

        return customer

    async def resolve_all_unlinked_feedback(self, limit: int = 100) -> int:
        """
        Resolve identities for all feedback without customer links.

        Args:
            limit: Maximum number of feedback items to process

        Returns:
            Number of feedback items successfully linked to customers
        """
        logger.info(f"Starting identity resolution for unlinked feedback (limit={limit})")

        # Get feedback with email but no customer_id
        from sqlalchemy import select, and_
        result = await self.session.execute(
            select(Feedback)
            .where(
                and_(
                    Feedback.customer_email.isnot(None),
                    Feedback.customer_id.is_(None)
                )
            )
            .order_by(Feedback.created_at.desc())
            .limit(limit)
        )
        unlinked = list(result.scalars().all())
        logger.info(f"Found {len(unlinked)} unlinked feedback items with emails")

        resolved_count = 0
        for feedback in unlinked:
            try:
                customer = await self.resolve_feedback_identity(feedback)
                if customer:
                    resolved_count += 1
            except Exception as e:
                logger.error(
                    f"Error resolving identity for feedback {feedback.id}: {e}",
                    exc_info=True,
                )
                await self.session.rollback()
                continue

        logger.info(f"Resolved identities for {resolved_count} feedback items")
        return resolved_count
