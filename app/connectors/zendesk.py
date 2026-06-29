"""Zendesk connector for syncing tickets, users, and organizations."""

import json
import asyncio
from pathlib import Path
from typing import Any
from datetime import datetime

import httpx

from app.core.config import settings


class ZendeskRateLimiter:
    """Token bucket rate limiter for Zendesk API (180 req/min)."""

    def __init__(self, rate: int = 180, per_seconds: int = 60):
        """
        Initialize rate limiter.

        Args:
            rate: Number of requests allowed (default 180 for safety buffer)
            per_seconds: Time period in seconds (default 60 for per-minute limit)
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


class ZendeskConnectorError(Exception):
    """Base exception for Zendesk connector errors."""
    pass


class ZendeskAuthError(ZendeskConnectorError):
    """Authentication or authorization error."""
    pass


class ZendeskRateLimitError(ZendeskConnectorError):
    """Rate limit exceeded."""
    pass


class ZendeskConnector:
    """Zendesk API connector with field mapping and rate limiting."""

    def __init__(
        self,
        subdomain: str | None = None,
        email: str | None = None,
        api_token: str | None = None,
    ):
        """
        Initialize Zendesk connector.

        Args:
            subdomain: Zendesk subdomain (e.g., 'mycompany' for mycompany.zendesk.com)
            email: Email address for authentication
            api_token: Zendesk API token

        Raises:
            ZendeskAuthError: If credentials are not provided
        """
        self.subdomain = subdomain or settings.zendesk_subdomain
        self.email = email or settings.zendesk_email
        self.api_token = api_token or settings.zendesk_api_token

        if not all([self.subdomain, self.email, self.api_token]):
            raise ZendeskAuthError(
                "Zendesk credentials not configured (subdomain, email, api_token required)"
            )

        self.base_url = f"https://{self.subdomain}.zendesk.com/api/v2"
        self.rate_limiter = ZendeskRateLimiter(rate=180, per_seconds=60)

        # Load field mappings from JSON
        mapping_file = Path(__file__).parent / "zendesk_mapping.json"
        with open(mapping_file) as f:
            self.mappings = json.load(f)

        # HTTP client with auth
        self.client = httpx.AsyncClient(
            auth=(f"{self.email}/token", self.api_token),
            timeout=30.0,
        )

    async def fetch_tickets(
        self,
        start_time: int | None = None,
        page_size: int = 100,
    ) -> dict[str, Any]:
        """
        Fetch tickets using incremental export API.

        Args:
            start_time: Unix timestamp for incremental sync (default: last 30 days)
            page_size: Number of tickets per page (max 1000)

        Returns:
            Dictionary with 'tickets' list and optional 'next_page' URL

        Raises:
            ZendeskRateLimitError: If rate limit is exceeded
            ZendeskAuthError: For authentication failures
            ZendeskConnectorError: For other API errors
        """
        await self.rate_limiter.acquire()

        # Default to last 30 days if no start_time provided
        if start_time is None:
            start_time = int(datetime.now().timestamp()) - (30 * 24 * 60 * 60)

        url = f"{self.base_url}/incremental/tickets.json"
        params = {
            "start_time": start_time,
            "per_page": min(page_size, 1000),
        }

        try:
            response = await self.client.get(url, params=params)

            if response.status_code == 429:
                raise ZendeskRateLimitError(
                    f"Rate limit exceeded. Retry-After: {response.headers.get('Retry-After', 'unknown')}"
                )
            elif response.status_code in (401, 403):
                raise ZendeskAuthError(
                    f"Authentication failed: {response.status_code} {response.text}"
                )
            elif response.status_code != 200:
                raise ZendeskConnectorError(
                    f"API request failed: {response.status_code} {response.text}"
                )

            data = response.json()

            # Transform tickets using field mapping
            transformed_tickets = [
                self._transform_ticket(ticket) for ticket in data.get("tickets", [])
            ]

            result = {"tickets": transformed_tickets}

            # Include pagination info if available
            if data.get("next_page"):
                result["next_page"] = data["next_page"]
            if data.get("end_time"):
                result["end_time"] = data["end_time"]

            return result

        except httpx.HTTPError as e:
            raise ZendeskConnectorError(f"HTTP error occurred: {e}")

    def _transform_ticket(self, ticket: dict[str, Any]) -> dict[str, Any]:
        """
        Transform Zendesk ticket to JisrVoC schema.

        Args:
            ticket: Zendesk ticket dictionary

        Returns:
            Transformed ticket dictionary
        """
        mapping = self.mappings["ticket_mapping"]

        transformed = {
            "external_id": str(ticket["id"]),
            "source": "zendesk",
        }

        # Apply field mapping
        for zd_field, jisr_field in mapping.items():
            # Handle nested fields (e.g., "via.channel")
            if "." in zd_field:
                parts = zd_field.split(".")
                value = ticket
                for part in parts:
                    value = value.get(part) if isinstance(value, dict) else None
                    if value is None:
                        break
            else:
                value = ticket.get(zd_field)

            if value is not None:
                transformed[jisr_field] = value

        # Add satisfaction score if available
        if ticket.get("satisfaction_rating"):
            score = ticket["satisfaction_rating"].get("score")
            if score:
                transformed["satisfaction_score"] = score

        # Add metadata with all original properties
        transformed["metadata"] = ticket

        # Extract customer email from requester_id (will need user lookup)
        if ticket.get("requester_id"):
            transformed["customer_external_id"] = str(ticket["requester_id"])

        return transformed

    async def fetch_users(
        self,
        page: int = 1,
        page_size: int = 100,
    ) -> dict[str, Any]:
        """
        Fetch users from Zendesk.

        Args:
            page: Page number
            page_size: Number of users per page

        Returns:
            Dictionary with 'users' list and pagination info
        """
        await self.rate_limiter.acquire()

        url = f"{self.base_url}/users.json"
        params = {
            "page": page,
            "per_page": min(page_size, 100),
        }

        try:
            response = await self.client.get(url, params=params)

            if response.status_code == 429:
                raise ZendeskRateLimitError("Rate limit exceeded")
            elif response.status_code in (401, 403):
                raise ZendeskAuthError(f"Authentication failed: {response.status_code}")
            elif response.status_code != 200:
                raise ZendeskConnectorError(f"API request failed: {response.status_code}")

            data = response.json()

            transformed_users = [
                self._transform_user(user) for user in data.get("users", [])
            ]

            result = {"users": transformed_users}

            # Include pagination info
            if data.get("next_page"):
                result["next_page"] = data["next_page"]

            return result

        except httpx.HTTPError as e:
            raise ZendeskConnectorError(f"HTTP error occurred: {e}")

    def _transform_user(self, user: dict[str, Any]) -> dict[str, Any]:
        """Transform Zendesk user to JisrVoC schema."""
        mapping = self.mappings["user_mapping"]

        transformed = {
            "external_id": str(user["id"]),
            "source": "zendesk",
        }

        for zd_field, jisr_field in mapping.items():
            value = user.get(zd_field)
            if value is not None:
                transformed[jisr_field] = value

        transformed["metadata"] = user
        return transformed

    async def fetch_organizations(
        self,
        page: int = 1,
        page_size: int = 100,
    ) -> dict[str, Any]:
        """
        Fetch organizations from Zendesk.

        Args:
            page: Page number
            page_size: Number of organizations per page

        Returns:
            Dictionary with 'organizations' list and pagination info
        """
        await self.rate_limiter.acquire()

        url = f"{self.base_url}/organizations.json"
        params = {
            "page": page,
            "per_page": min(page_size, 100),
        }

        try:
            response = await self.client.get(url, params=params)

            if response.status_code == 429:
                raise ZendeskRateLimitError("Rate limit exceeded")
            elif response.status_code in (401, 403):
                raise ZendeskAuthError(f"Authentication failed: {response.status_code}")
            elif response.status_code != 200:
                raise ZendeskConnectorError(f"API request failed: {response.status_code}")

            data = response.json()

            transformed_orgs = [
                self._transform_organization(org) for org in data.get("organizations", [])
            ]

            result = {"organizations": transformed_orgs}

            if data.get("next_page"):
                result["next_page"] = data["next_page"]

            return result

        except httpx.HTTPError as e:
            raise ZendeskConnectorError(f"HTTP error occurred: {e}")

    def _transform_organization(self, org: dict[str, Any]) -> dict[str, Any]:
        """Transform Zendesk organization to JisrVoC schema."""
        mapping = self.mappings["organization_mapping"]

        transformed = {
            "external_id": str(org["id"]),
            "source": "zendesk",
        }

        for zd_field, jisr_field in mapping.items():
            value = org.get(zd_field)

            # Special handling for domain_names array
            if zd_field == "domain_names" and isinstance(value, list) and len(value) > 0:
                transformed[jisr_field] = value[0]  # Take first domain
            elif value is not None:
                transformed[jisr_field] = value

        transformed["metadata"] = org
        return transformed

    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
