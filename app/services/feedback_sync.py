"""Feedback sync service - coordinates fetching and storing feedback from external sources."""

import logging
from datetime import datetime
from typing import Union, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.hubspot import HubSpotConnector
from app.connectors.zendesk import ZendeskConnector
from app.repositories.feedback import FeedbackRepository
from app.repositories.customer import CustomerRepository
from app.repositories.company import CompanyRepository
from app.models.feedback import Feedback


logger = logging.getLogger(__name__)


class FeedbackSyncService:
    """
    Service to sync feedback from external sources to database.

    Coordinates:
    1. Fetch feedback from connector (HubSpot, Zendesk)
    2. Upsert customer and company records
    3. Store feedback with relationships
    """

    def __init__(
        self,
        session: AsyncSession,
        connector: Union[HubSpotConnector, ZendeskConnector],
    ):
        """Initialize feedback sync service.

        Args:
            session: Database session
            connector: Connector instance (HubSpot or Zendesk)
        """
        self.session = session
        self.connector = connector
        self.feedback_repo = FeedbackRepository(session)
        self.customer_repo = CustomerRepository(session)
        self.company_repo = CompanyRepository(session)

    async def sync_feedback_item(
        self,
        external_id: str,
        title: str,
        content: str,
        customer_email: Optional[str] = None,
        customer_name: Optional[str] = None,
        company_domain: Optional[str] = None,
        company_name: Optional[str] = None,
        source_channel: Optional[str] = None,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        satisfaction_score: Optional[str] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
        metadata: Optional[dict] = None,
    ) -> Feedback:
        """
        Sync a single feedback item from external source.

        Args:
            external_id: External ID from source system
            title: Feedback title
            content: Feedback content
            customer_email: Customer email
            customer_name: Customer name
            company_domain: Company email domain
            company_name: Company name
            source_channel: Channel (email, chat, web, phone)
            status: Feedback status
            priority: Feedback priority
            satisfaction_score: Satisfaction score
            created_at: Creation timestamp
            updated_at: Update timestamp
            metadata: Raw metadata from source

        Returns:
            Feedback instance
        """
        source = self.connector.__class__.__name__.replace("Connector", "").lower()

        # Upsert company if we have company data
        company = None
        if company_domain:
            company = await self.company_repo.upsert_by_domain(
                domain=company_domain,
                company_name=company_name,
            )
            await self.company_repo.commit()

        # Upsert customer if we have customer data
        customer = None
        if customer_email:
            customer = await self.customer_repo.upsert_by_email(
                email=customer_email,
                name=customer_name,
                company_id=company.id if company else None,
            )
            await self.customer_repo.commit()

        # Check if feedback already exists
        existing = await self.feedback_repo.get_by_source_and_external_id(
            source=source,
            external_id=external_id,
        )

        if existing:
            # Update existing feedback
            feedback = await self.feedback_repo.update(
                existing,
                title=title,
                content=content,
                customer_id=customer.id if customer else None,
                customer_email=customer_email,
                company_id=company.id if company else None,
                source_channel=source_channel,
                status=status,
                priority=priority,
                satisfaction_score=satisfaction_score,
                updated_at=updated_at or datetime.utcnow(),
                source_metadata=metadata,
            )
            logger.info(f"Updated feedback {feedback.id} from {source}:{external_id}")
        else:
            # Create new feedback
            feedback = await self.feedback_repo.create(
                source=source,
                external_id=external_id,
                title=title,
                content=content,
                customer_id=customer.id if customer else None,
                customer_email=customer_email,
                company_id=company.id if company else None,
                source_channel=source_channel,
                status=status,
                priority=priority,
                satisfaction_score=satisfaction_score,
                created_at=created_at or datetime.utcnow(),
                updated_at=updated_at or datetime.utcnow(),
                source_metadata=metadata,
            )
            logger.info(f"Created feedback {feedback.id} from {source}:{external_id}")

        await self.feedback_repo.commit()
        return feedback

    async def sync_all_tickets(
        self,
        limit: int = 100,
        after: Optional[str] = None,
    ) -> list[Feedback]:
        """
        Sync all tickets from connector.

        Args:
            limit: Maximum number of items to sync per batch
            after: Pagination cursor

        Returns:
            List of synced feedback items
        """
        logger.info(f"Starting ticket sync from {self.connector.__class__.__name__}")

        # Fetch tickets from connector
        response = await self.connector.fetch_tickets(limit=limit, after=after)
        tickets = response.get("results", [])

        synced_feedback = []
        for ticket in tickets:
            try:
                feedback = await self.sync_feedback_item(
                    external_id=ticket["id"],
                    title=ticket["title"],
                    content=ticket["content"],
                    customer_email=ticket.get("customer_email"),
                    customer_name=ticket.get("customer_name"),
                    company_domain=ticket.get("company_domain"),
                    company_name=ticket.get("company_name"),
                    source_channel=ticket.get("source_channel"),
                    status=ticket.get("status"),
                    priority=ticket.get("priority"),
                    satisfaction_score=ticket.get("satisfaction_score"),
                    created_at=ticket.get("created_at"),
                    updated_at=ticket.get("updated_at"),
                    metadata=ticket,
                )
                synced_feedback.append(feedback)
            except Exception as e:
                logger.error(f"Error syncing ticket {ticket.get('id')}: {e}", exc_info=True)
                continue

        logger.info(f"Synced {len(synced_feedback)} tickets from {self.connector.__class__.__name__}")
        return synced_feedback
