"""HubSpot connector for syncing support tickets as feedback."""

import logging
from typing import Optional, List
from datetime import datetime

import httpx

from app.core.config import settings
from app.repositories.feedback import FeedbackRepository
from app.models.feedback import Feedback
from app.services.identity_resolution import IdentityResolutionService
from sqlalchemy.ext.asyncio import AsyncSession


logger = logging.getLogger(__name__)


class HubSpotConnector:
    """Connector for syncing HubSpot tickets to feedback."""

    def __init__(self, session: AsyncSession):
        """Initialize HubSpot connector.

        Args:
            session: Database session
        """
        self.session = session
        self.feedback_repo = FeedbackRepository(session)
        self.identity_service = IdentityResolutionService(session)
        self.api_key = settings.hubspot_api_key
        self.base_url = "https://api.hubapi.com"

    async def fetch_tickets(
        self,
        limit: int = 100,
        since: Optional[datetime] = None,
    ) -> List[dict]:
        """
        Fetch tickets from HubSpot.

        Args:
            limit: Maximum number of tickets to fetch
            since: Only fetch tickets created/updated after this time

        Returns:
            List of ticket dictionaries from HubSpot
        """
        logger.info(f"Fetching tickets from HubSpot (limit={limit})")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        # Build properties list - fields we want from each ticket
        properties = [
            "subject",
            "content",
            "hs_ticket_id",
            "hs_ticket_category",
            "hs_ticket_priority",
            "hs_pipeline_stage",
            "createdate",
            "hs_lastmodifieddate",
            "source_type",
        ]

        params = {
            "limit": limit,
            "properties": ",".join(properties),
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/crm/v3/objects/tickets",
                headers=headers,
                params=params,
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()

        tickets = data.get("results", [])
        logger.info(f"Fetched {len(tickets)} tickets from HubSpot")

        return tickets

    async def fetch_ticket_contact(self, ticket_id: str) -> Optional[dict]:
        """
        Fetch associated contact information for a HubSpot ticket.

        Args:
            ticket_id: HubSpot ticket ID

        Returns:
            Contact dictionary with email and name, or None if no contact found
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient() as client:
                # Get contact associations for this ticket
                response = await client.get(
                    f"{self.base_url}/crm/v3/objects/tickets/{ticket_id}/associations/contacts",
                    headers=headers,
                    timeout=30.0,
                )
                response.raise_for_status()
                associations = response.json()

                results = associations.get("results", [])
                if not results:
                    logger.debug(f"No contacts associated with ticket {ticket_id}")
                    return None

                # Get the first associated contact ID
                contact_id = results[0].get("id")
                if not contact_id:
                    return None

                # Fetch contact details
                contact_response = await client.get(
                    f"{self.base_url}/crm/v3/objects/contacts/{contact_id}",
                    headers=headers,
                    params={"properties": "email,firstname,lastname"},
                    timeout=30.0,
                )
                contact_response.raise_for_status()
                contact_data = contact_response.json()

                properties = contact_data.get("properties", {})
                email = properties.get("email")

                # Construct full name
                firstname = properties.get("firstname") or ""
                lastname = properties.get("lastname") or ""
                name = f"{firstname} {lastname}".strip() or None

                if email:
                    logger.info(f"Found contact for ticket {ticket_id}: {email}")
                    return {
                        "id": contact_id,
                        "email": email,
                        "name": name,
                    }

                return None

        except httpx.HTTPStatusError as e:
            logger.warning(f"Failed to fetch contact for ticket {ticket_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error fetching contact for ticket {ticket_id}: {e}", exc_info=True)
            return None

    async def sync_ticket_to_feedback(
        self,
        ticket: dict,
    ) -> Feedback:
        """
        Sync a single HubSpot ticket to feedback table.

        Args:
            ticket: HubSpot ticket dictionary

        Returns:
            Created or updated Feedback instance
        """
        ticket_id = ticket.get("id")
        properties = ticket.get("properties", {})

        # Extract ticket data - ensure content is never null
        title = properties.get("subject") or "Untitled ticket"
        content = properties.get("content") or "(No content provided)"
        external_id = str(ticket_id)

        # Check if feedback already exists
        existing = await self.feedback_repo.get_by_source_and_external_id(
            source="hubspot",
            external_id=external_id,
        )

        if existing:
            logger.info(f"Ticket {ticket_id} already exists as feedback {existing.id}, skipping")
            return existing

        # Parse timestamps from HubSpot (ISO 8601 format)
        created_at_str = properties.get("createdate")
        updated_at_str = properties.get("hs_lastmodifieddate")

        logger.info(f"HubSpot ticket {ticket_id} timestamps - createdate: {created_at_str}, lastmodified: {updated_at_str}")

        # Parse or use current time as fallback
        from dateutil import parser as date_parser
        created_at = None
        updated_at = None

        if created_at_str:
            try:
                parsed = date_parser.parse(created_at_str)
                # Convert to naive UTC datetime (remove timezone info)
                created_at = parsed.replace(tzinfo=None) if parsed.tzinfo else parsed
                logger.info(f"Parsed createdate: {created_at}")
            except (ValueError, TypeError) as e:
                logger.warning(f"Failed to parse createdate '{created_at_str}' for ticket {ticket_id}: {e}")

        if not created_at:
            created_at = datetime.utcnow()
            logger.info(f"Using current time for created_at: {created_at}")

        if updated_at_str:
            try:
                parsed = date_parser.parse(updated_at_str)
                # Convert to naive UTC datetime (remove timezone info)
                updated_at = parsed.replace(tzinfo=None) if parsed.tzinfo else parsed
                logger.info(f"Parsed lastmodifieddate: {updated_at}")
            except (ValueError, TypeError) as e:
                logger.warning(f"Failed to parse lastmodifieddate '{updated_at_str}' for ticket {ticket_id}: {e}")

        if not updated_at:
            updated_at = created_at
            logger.info(f"Using created_at for updated_at: {updated_at}")

        # Create new feedback
        feedback = await self.feedback_repo.create(
            source="hubspot",
            external_id=external_id,
            source_channel=properties.get("source_type") or "email",
            title=title,
            content=content,
            priority=properties.get("hs_ticket_priority"),
            status=properties.get("hs_pipeline_stage") or "open",
            created_at=created_at,
            updated_at=updated_at,
            metadata={
                "category": properties.get("hs_ticket_category"),
                "hubspot_createdate": created_at_str,
                "hubspot_lastmodifieddate": updated_at_str,
            },
        )

        await self.feedback_repo.commit()
        logger.info(f"Created feedback {feedback.id} from HubSpot ticket {ticket_id}")

        # Fetch associated contact and resolve customer identity
        contact = await self.fetch_ticket_contact(str(ticket_id))
        if contact:
            logger.info(f"Resolving identity for feedback {feedback.id} with contact {contact.get('email')}")
            customer = await self.identity_service.resolve_feedback_identity(
                feedback=feedback,
                email=contact.get("email"),
                name=contact.get("name"),
                hubspot_contact_id=contact.get("id"),
            )
            if customer:
                logger.info(f"Successfully linked feedback {feedback.id} to customer {customer.id}")
        else:
            logger.debug(f"No contact found for ticket {ticket_id}, skipping identity resolution")

        return feedback

    async def sync_tickets(
        self,
        limit: int = 100,
        since: Optional[datetime] = None,
    ) -> List[Feedback]:
        """
        Sync HubSpot tickets to feedback table.

        Args:
            limit: Maximum number of tickets to sync
            since: Only sync tickets created/updated after this time

        Returns:
            List of created/updated Feedback instances
        """
        logger.info(f"Starting HubSpot ticket sync (limit={limit})")

        # Fetch tickets from HubSpot
        tickets = await self.fetch_tickets(limit=limit, since=since)

        # Sync each ticket to feedback
        synced_feedback = []
        for ticket in tickets:
            try:
                feedback = await self.sync_ticket_to_feedback(ticket)
                synced_feedback.append(feedback)
            except Exception as e:
                logger.error(
                    f"Error syncing ticket {ticket.get('id')}: {e}",
                    exc_info=True,
                )
                # Rollback and continue with next ticket
                await self.session.rollback()
                continue

        logger.info(f"Synced {len(synced_feedback)} tickets from HubSpot")
        return synced_feedback
