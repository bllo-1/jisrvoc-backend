"""HubSpot connector for syncing tickets, contacts, and companies."""

import json
import asyncio
from pathlib import Path
from typing import Any
from datetime import datetime

from hubspot import HubSpot
from hubspot.crm.tickets import ApiException as TicketsException
from hubspot.crm.contacts import ApiException as ContactsException
from hubspot.crm.companies import ApiException as CompaniesException

from app.core.config import settings


class HubSpotRateLimiter:
    """Token bucket rate limiter for HubSpot API (10 req/sec)."""

    def __init__(self, rate: int = 10, per_seconds: int = 1):
        """
        Initialize rate limiter.

        Args:
            rate: Number of requests allowed
            per_seconds: Time period in seconds
        """
        self.rate = rate
        self.per_seconds = per_seconds
        self.allowance = rate
        self.last_check = datetime.now()
        self.lock = asyncio.Lock()

    async def acquire(self):
        """Wait until a request is allowed."""
        async with self.lock:
            current = datetime.now()
            elapsed = (current - self.last_check).total_seconds()
            self.last_check = current

            # Add tokens based on time elapsed
            self.allowance += elapsed * (self.rate / self.per_seconds)
            if self.allowance > self.rate:
                self.allowance = self.rate

            # If not enough tokens, wait
            if self.allowance < 1.0:
                sleep_time = (1.0 - self.allowance) * (self.per_seconds / self.rate)
                await asyncio.sleep(sleep_time)
                self.allowance = 0.0
            else:
                self.allowance -= 1.0


class HubSpotConnectorError(Exception):
    """Base exception for HubSpot connector errors."""
    pass


class HubSpotAuthError(HubSpotConnectorError):
    """Authentication or authorization error."""
    pass


class HubSpotRateLimitError(HubSpotConnectorError):
    """Rate limit exceeded."""
    pass


class HubSpotConnector:
    """HubSpot API connector with field mapping and rate limiting."""

    def __init__(self, api_key: str | None = None):
        """
        Initialize HubSpot connector.

        Args:
            api_key: HubSpot API key (Private App token)

        Raises:
            HubSpotAuthError: If API key is not provided
        """
        self.api_key = api_key or settings.hubspot_api_key
        if not self.api_key:
            raise HubSpotAuthError("HUBSPOT_API_KEY not configured")

        self.client = HubSpot(access_token=self.api_key)
        self.rate_limiter = HubSpotRateLimiter(rate=10, per_seconds=1)

        # Load field mappings from JSON
        mapping_file = Path(__file__).parent / "hubspot_mapping.json"
        with open(mapping_file) as f:
            self.mappings = json.load(f)

    async def fetch_tickets(
        self,
        limit: int = 100,
        after: str | None = None,
    ) -> dict[str, Any]:
        """
        Fetch tickets from HubSpot.

        Args:
            limit: Maximum number of tickets to fetch (max 100)
            after: Pagination cursor from previous response

        Returns:
            Dictionary with 'results' list and optional 'paging' dict

        Raises:
            HubSpotRateLimitError: If rate limit is exceeded
            HubSpotConnectorError: For other API errors
        """
        await self.rate_limiter.acquire()

        try:
            # Get ticket properties from mapping
            properties = list(self.mappings["ticket_mapping"].keys())

            response = self.client.crm.tickets.basic_api.get_page(
                limit=min(limit, 100),
                after=after,
                properties=properties,
                associations=["contacts", "companies"],
            )

            # Transform tickets using field mapping
            transformed = [
                self._transform_ticket(ticket) for ticket in response.results
            ]

            result = {"results": transformed}

            # Include pagination info if available
            if response.paging:
                result["paging"] = {
                    "next": response.paging.next.dict() if response.paging.next else None
                }

            return result

        except TicketsException as e:
            if e.status == 429:
                raise HubSpotRateLimitError(f"Rate limit exceeded: {e}")
            elif e.status in (401, 403):
                raise HubSpotAuthError(f"Authentication failed: {e}")
            else:
                raise HubSpotConnectorError(f"Failed to fetch tickets: {e}")

    def _transform_ticket(self, ticket: Any) -> dict[str, Any]:
        """
        Transform HubSpot ticket to JisrVoC schema.

        Args:
            ticket: HubSpot ticket object

        Returns:
            Transformed ticket dictionary
        """
        props = ticket.properties
        mapping = self.mappings["ticket_mapping"]

        transformed = {
            "external_id": str(ticket.id),
            "source": "hubspot",
        }

        # Apply field mapping
        for hs_field, jisr_field in mapping.items():
            value = props.get(hs_field)
            if value is not None:
                transformed[jisr_field] = value

        # Add metadata with all original properties
        transformed["metadata"] = props

        # Extract customer email from associations (if available)
        if hasattr(ticket, "associations") and ticket.associations:
            # This will be filled when we query with association data
            transformed["customer_email"] = None  # TODO: Extract from associations

        return transformed

    async def fetch_contacts(
        self,
        limit: int = 100,
        after: str | None = None,
    ) -> dict[str, Any]:
        """
        Fetch contacts from HubSpot.

        Args:
            limit: Maximum number of contacts to fetch
            after: Pagination cursor

        Returns:
            Dictionary with 'results' and optional 'paging'
        """
        await self.rate_limiter.acquire()

        try:
            properties = list(self.mappings["contact_mapping"].keys())

            response = self.client.crm.contacts.basic_api.get_page(
                limit=min(limit, 100),
                after=after,
                properties=properties,
            )

            transformed = [
                self._transform_contact(contact) for contact in response.results
            ]

            result = {"results": transformed}
            if response.paging:
                result["paging"] = {
                    "next": response.paging.next.dict() if response.paging.next else None
                }

            return result

        except ContactsException as e:
            if e.status == 429:
                raise HubSpotRateLimitError(f"Rate limit exceeded: {e}")
            elif e.status in (401, 403):
                raise HubSpotAuthError(f"Authentication failed: {e}")
            else:
                raise HubSpotConnectorError(f"Failed to fetch contacts: {e}")

    def _transform_contact(self, contact: Any) -> dict[str, Any]:
        """Transform HubSpot contact to JisrVoC schema."""
        props = contact.properties
        mapping = self.mappings["contact_mapping"]

        transformed = {
            "external_id": str(contact.id),
            "source": "hubspot",
        }

        # Build full name from first + last
        first = props.get("firstname", "")
        last = props.get("lastname", "")
        transformed["name"] = f"{first} {last}".strip() or "Unknown"

        # Apply other mappings
        for hs_field, jisr_field in mapping.items():
            if hs_field not in ("firstname", "lastname"):  # Already handled
                value = props.get(hs_field)
                if value is not None:
                    transformed[jisr_field] = value

        transformed["metadata"] = props
        return transformed

    async def fetch_companies(
        self,
        limit: int = 100,
        after: str | None = None,
    ) -> dict[str, Any]:
        """
        Fetch companies from HubSpot.

        Args:
            limit: Maximum number of companies to fetch
            after: Pagination cursor

        Returns:
            Dictionary with 'results' and optional 'paging'
        """
        await self.rate_limiter.acquire()

        try:
            properties = list(self.mappings["company_mapping"].keys())

            response = self.client.crm.companies.basic_api.get_page(
                limit=min(limit, 100),
                after=after,
                properties=properties,
            )

            transformed = [
                self._transform_company(company) for company in response.results
            ]

            result = {"results": transformed}
            if response.paging:
                result["paging"] = {
                    "next": response.paging.next.dict() if response.paging.next else None
                }

            return result

        except CompaniesException as e:
            if e.status == 429:
                raise HubSpotRateLimitError(f"Rate limit exceeded: {e}")
            elif e.status in (401, 403):
                raise HubSpotAuthError(f"Authentication failed: {e}")
            else:
                raise HubSpotConnectorError(f"Failed to fetch companies: {e}")

    def _transform_company(self, company: Any) -> dict[str, Any]:
        """Transform HubSpot company to JisrVoC schema."""
        props = company.properties
        mapping = self.mappings["company_mapping"]

        transformed = {
            "external_id": str(company.id),
            "source": "hubspot",
        }

        for hs_field, jisr_field in mapping.items():
            value = props.get(hs_field)
            if value is not None:
                transformed[jisr_field] = value

        transformed["metadata"] = props
        return transformed

    async def close(self):
        """Clean up resources (placeholder for future connection pooling)."""
        pass

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
