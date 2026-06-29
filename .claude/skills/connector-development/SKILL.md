---
name: hubspot-zendesk-connectors
description: Build HubSpot and Zendesk connectors following JisrVoC patterns with OAuth, rate limiting, error handling, and data synchronization
---

# External API Connector Development

## When to Use This Skill

Use this skill when:
- Building new connectors for HubSpot, Zendesk, or Canny
- Implementing OAuth flows
- Handling API rate limits and pagination
- Syncing external data to JisrVoC database
- Debugging connector issues

## Overview

JisrVoC integrates with multiple external platforms to collect customer feedback:
- **HubSpot**: Support tickets, contacts, companies
- **Zendesk**: Support tickets, users, organizations
- **Canny**: Feature requests, votes, comments

All connectors follow a consistent pattern for maintainability.

## Connector Architecture

### Base Connector Pattern

All connectors inherit from a base class:

```python
# app/connectors/base.py

from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

class BaseConnector(ABC):
    """Base class for all external API connectors."""

    def __init__(self, api_key: str, base_url: str):
        self.api_key = api_key
        self.base_url = base_url
        self.client = httpx.AsyncClient(
            base_url=base_url,
            timeout=30.0,
            headers=self._get_auth_headers()
        )

    @abstractmethod
    def _get_auth_headers(self) -> dict[str, str]:
        """Return authentication headers."""
        pass

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    async def _make_request(
        self,
        method: str,
        endpoint: str,
        **kwargs
    ) -> dict[str, Any]:
        """Make HTTP request with retry logic."""
        response = await self.client.request(method, endpoint, **kwargs)
        response.raise_for_status()
        return response.json()

    async def _paginate(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Generic pagination handler."""
        pass

    async def close(self):
        """Clean up resources."""
        await self.client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
```

## HubSpot Connector

### Setup

```python
# app/connectors/hubspot.py

from hubspot import HubSpot
from hubspot.crm.contacts import ApiException as ContactsException
from app.connectors.base import BaseConnector

class HubSpotConnector(BaseConnector):
    """HubSpot API connector."""

    def __init__(self, api_key: str):
        # Use official SDK for OAuth complexity
        self.client = HubSpot(access_token=api_key)
        self.api_key = api_key

    async def fetch_tickets(
        self,
        limit: int = 100,
        after: str | None = None
    ) -> dict[str, Any]:
        """Fetch support tickets from HubSpot."""
        try:
            response = self.client.crm.tickets.basic_api.get_page(
                limit=limit,
                after=after,
                properties=["subject", "content", "hs_ticket_priority", "createdate"],
                associations=["contacts", "companies"]
            )
            return {
                "results": [self._transform_ticket(t) for t in response.results],
                "paging": response.paging.dict() if response.paging else None
            }
        except ContactsException as e:
            # Handle rate limits
            if e.status == 429:
                raise RateLimitError(f"HubSpot rate limit exceeded: {e}")
            raise

    def _transform_ticket(self, ticket: Any) -> dict[str, Any]:
        """Transform HubSpot ticket to JisrVoC format."""
        props = ticket.properties
        return {
            "external_id": ticket.id,
            "source": "hubspot",
            "title": props.get("subject"),
            "content": props.get("content"),
            "priority": props.get("hs_ticket_priority"),
            "created_at": props.get("createdate"),
            "customer_email": self._extract_contact_email(ticket.associations),
            "metadata": ticket.properties
        }

    async def fetch_contacts(
        self,
        limit: int = 100,
        after: str | None = None
    ) -> dict[str, Any]:
        """Fetch contacts from HubSpot."""
        response = self.client.crm.contacts.basic_api.get_page(
            limit=limit,
            after=after,
            properties=["email", "firstname", "lastname", "company"]
        )
        return {
            "results": [self._transform_contact(c) for c in response.results],
            "paging": response.paging.dict() if response.paging else None
        }

    def _transform_contact(self, contact: Any) -> dict[str, Any]:
        """Transform HubSpot contact to JisrVoC format."""
        props = contact.properties
        return {
            "external_id": contact.id,
            "source": "hubspot",
            "email": props.get("email"),
            "name": f"{props.get('firstname', '')} {props.get('lastname', '')}".strip(),
            "company": props.get("company"),
            "metadata": contact.properties
        }
```

### Rate Limiting

HubSpot has strict rate limits:
- **Free/Starter**: 100 requests per 10 seconds
- **Professional**: 120 requests per 10 seconds
- **Enterprise**: 150 requests per 10 seconds

**Implementation**:
```python
import asyncio
from collections import deque
from datetime import datetime, timedelta

class RateLimiter:
    """Token bucket rate limiter."""

    def __init__(self, rate: int = 10, per_seconds: int = 1):
        self.rate = rate
        self.per_seconds = per_seconds
        self.allowance = rate
        self.last_check = datetime.now()
        self.lock = asyncio.Lock()

    async def acquire(self):
        """Wait until request is allowed."""
        async with self.lock:
            current = datetime.now()
            elapsed = (current - self.last_check).total_seconds()
            self.last_check = current

            self.allowance += elapsed * (self.rate / self.per_seconds)
            if self.allowance > self.rate:
                self.allowance = self.rate

            if self.allowance < 1.0:
                sleep_time = (1.0 - self.allowance) * (self.per_seconds / self.rate)
                await asyncio.sleep(sleep_time)
                self.allowance = 0.0
            else:
                self.allowance -= 1.0

# Usage in connector
class HubSpotConnector(BaseConnector):
    def __init__(self, api_key: str):
        super().__init__(api_key, "https://api.hubapi.com")
        self.rate_limiter = RateLimiter(rate=10, per_seconds=1)

    async def _make_request(self, method: str, endpoint: str, **kwargs):
        await self.rate_limiter.acquire()
        return await super()._make_request(method, endpoint, **kwargs)
```

### OAuth Flow (Phase 1)

```python
# app/api/v1/integrations.py

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import RedirectResponse

router = APIRouter(prefix="/integrations", tags=["integrations"])

@router.get("/hubspot/authorize")
async def hubspot_authorize():
    """Redirect user to HubSpot OAuth page."""
    client_id = settings.hubspot_client_id
    redirect_uri = f"{settings.base_url}/integrations/hubspot/callback"
    scope = "crm.objects.contacts.read crm.objects.companies.read tickets"

    auth_url = (
        f"https://app.hubspot.com/oauth/authorize"
        f"?client_id={client_id}"
        f"&redirect_uri={redirect_uri}"
        f"&scope={scope}"
    )
    return RedirectResponse(auth_url)

@router.get("/hubspot/callback")
async def hubspot_callback(code: str, db: AsyncSession = Depends(get_db)):
    """Handle OAuth callback and store access token."""
    # Exchange code for access token
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.hubapi.com/oauth/v1/token",
            data={
                "grant_type": "authorization_code",
                "client_id": settings.hubspot_client_id,
                "client_secret": settings.hubspot_client_secret,
                "redirect_uri": f"{settings.base_url}/integrations/hubspot/callback",
                "code": code
            }
        )
        response.raise_for_status()
        tokens = response.json()

    # Store tokens in database (encrypt access_token!)
    # TODO: Create Integration model to store credentials

    return {"message": "HubSpot connected successfully"}
```

## Zendesk Connector

### Setup

```python
# app/connectors/zendesk.py

from zenpy import Zenpy
from zenpy.lib.api_objects import Ticket, User
from app.connectors.base import BaseConnector

class ZendeskConnector(BaseConnector):
    """Zendesk API connector."""

    def __init__(self, email: str, token: str, subdomain: str):
        # Use Zenpy SDK
        self.client = Zenpy(
            email=email,
            token=token,
            subdomain=subdomain
        )
        self.subdomain = subdomain

    async def fetch_tickets(
        self,
        start_time: datetime | None = None,
        status: list[str] | None = None
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Fetch tickets from Zendesk with pagination."""
        query_params = {}
        if start_time:
            query_params["start_time"] = int(start_time.timestamp())

        # Zenpy handles pagination automatically
        for ticket in self.client.tickets.incremental(start_time=start_time):
            if status and ticket.status not in status:
                continue

            yield self._transform_ticket(ticket)

    def _transform_ticket(self, ticket: Ticket) -> dict[str, Any]:
        """Transform Zendesk ticket to JisrVoC format."""
        return {
            "external_id": str(ticket.id),
            "source": "zendesk",
            "title": ticket.subject,
            "content": ticket.description,
            "priority": ticket.priority,
            "status": ticket.status,
            "created_at": ticket.created_at,
            "updated_at": ticket.updated_at,
            "customer_id": str(ticket.requester_id),
            "metadata": {
                "tags": ticket.tags,
                "custom_fields": ticket.custom_fields,
                "satisfaction_rating": ticket.satisfaction_rating
            }
        }

    async def fetch_users(self, user_ids: list[int]) -> list[dict[str, Any]]:
        """Fetch users by IDs."""
        users = self.client.users.show_many(user_ids)
        return [self._transform_user(u) for u in users]

    def _transform_user(self, user: User) -> dict[str, Any]:
        """Transform Zendesk user to JisrVoC format."""
        return {
            "external_id": str(user.id),
            "source": "zendesk",
            "email": user.email,
            "name": user.name,
            "organization_id": str(user.organization_id) if user.organization_id else None,
            "metadata": {
                "role": user.role,
                "verified": user.verified,
                "tags": user.tags
            }
        }
```

### Rate Limiting

Zendesk rate limits:
- **Standard**: 700 requests per minute (global limit)
- **Per-account**: 200 requests per minute

**Implementation**:
```python
class ZendeskConnector(BaseConnector):
    def __init__(self, email: str, token: str, subdomain: str):
        super().__init__()
        self.rate_limiter = RateLimiter(rate=180, per_seconds=60)  # Buffer of 20
```

## Data Synchronization

### Sync Service Pattern

```python
# app/services/sync_service.py

from sqlalchemy.ext.asyncio import AsyncSession
from app.connectors.hubspot import HubSpotConnector
from app.connectors.zendesk import ZendeskConnector
from app.repositories.feedback_repository import FeedbackRepository

class SyncService:
    """Orchestrate data synchronization from external sources."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.feedback_repo = FeedbackRepository()

    async def sync_hubspot_tickets(
        self,
        connector: HubSpotConnector,
        full_sync: bool = False
    ) -> dict[str, int]:
        """Sync HubSpot tickets to database."""
        stats = {"created": 0, "updated": 0, "skipped": 0}

        # Get last sync timestamp
        last_sync = None if full_sync else await self._get_last_sync("hubspot")

        # Fetch tickets
        after = None
        while True:
            response = await connector.fetch_tickets(limit=100, after=after)

            for ticket_data in response["results"]:
                # Check if ticket exists
                existing = await self.feedback_repo.get_by_external_id(
                    self.db,
                    external_id=ticket_data["external_id"],
                    source="hubspot"
                )

                if existing:
                    # Update if modified
                    if self._is_modified(existing, ticket_data):
                        await self.feedback_repo.update(self.db, existing.id, ticket_data)
                        stats["updated"] += 1
                    else:
                        stats["skipped"] += 1
                else:
                    # Create new
                    await self.feedback_repo.create(self.db, ticket_data)
                    stats["created"] += 1

            # Check pagination
            paging = response.get("paging")
            if not paging or not paging.get("next"):
                break
            after = paging["next"]["after"]

        # Update last sync timestamp
        await self._set_last_sync("hubspot", datetime.utcnow())

        return stats

    async def sync_zendesk_tickets(
        self,
        connector: ZendeskConnector,
        start_time: datetime | None = None
    ) -> dict[str, int]:
        """Sync Zendesk tickets to database."""
        stats = {"created": 0, "updated": 0, "skipped": 0}

        # Use incremental export for efficiency
        if not start_time:
            start_time = await self._get_last_sync("zendesk") or (
                datetime.utcnow() - timedelta(days=30)
            )

        async for ticket_data in connector.fetch_tickets(start_time=start_time):
            existing = await self.feedback_repo.get_by_external_id(
                self.db,
                external_id=ticket_data["external_id"],
                source="zendesk"
            )

            if existing:
                await self.feedback_repo.update(self.db, existing.id, ticket_data)
                stats["updated"] += 1
            else:
                await self.feedback_repo.create(self.db, ticket_data)
                stats["created"] += 1

        await self._set_last_sync("zendesk", datetime.utcnow())
        return stats
```

### Sync Endpoint

```python
# app/api/v1/sync.py

from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.deps import get_db
from app.services.sync_service import SyncService
from app.connectors.hubspot import HubSpotConnector

router = APIRouter(prefix="/sync", tags=["sync"])

@router.post("/hubspot")
async def sync_hubspot(
    full_sync: bool = False,
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_db)
):
    """Trigger HubSpot sync (runs in background)."""
    service = SyncService(db)
    connector = HubSpotConnector(api_key=settings.hubspot_api_key)

    async def run_sync():
        async with connector:
            stats = await service.sync_hubspot_tickets(connector, full_sync)
            # Log stats or send notification
            print(f"HubSpot sync complete: {stats}")

    background_tasks.add_task(run_sync)

    return {"message": "HubSpot sync started", "full_sync": full_sync}
```

## Error Handling

### Retry Logic

Use `tenacity` for robust retry handling:

```python
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)
import httpx

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException))
)
async def fetch_with_retry(client: httpx.AsyncClient, url: str):
    """Fetch with automatic retry on transient errors."""
    response = await client.get(url)
    response.raise_for_status()
    return response.json()
```

### Custom Exceptions

```python
# app/connectors/exceptions.py

class ConnectorError(Exception):
    """Base exception for connector errors."""
    pass

class RateLimitError(ConnectorError):
    """Rate limit exceeded."""
    pass

class AuthenticationError(ConnectorError):
    """Authentication failed."""
    pass

class DataTransformError(ConnectorError):
    """Failed to transform external data."""
    pass
```

## Testing Connectors

### Mock Responses

```python
# tests/connectors/test_hubspot.py

import pytest
from unittest.mock import AsyncMock, MagicMock
from app.connectors.hubspot import HubSpotConnector

@pytest.fixture
def mock_hubspot_client():
    """Mock HubSpot SDK client."""
    client = MagicMock()
    client.crm.tickets.basic_api.get_page = AsyncMock(return_value={
        "results": [
            {
                "id": "123",
                "properties": {
                    "subject": "Test ticket",
                    "content": "Test content",
                    "hs_ticket_priority": "HIGH"
                }
            }
        ],
        "paging": None
    })
    return client

@pytest.mark.asyncio
async def test_fetch_tickets(mock_hubspot_client):
    """Test fetching tickets from HubSpot."""
    connector = HubSpotConnector(api_key="test-key")
    connector.client = mock_hubspot_client

    response = await connector.fetch_tickets(limit=10)

    assert len(response["results"]) == 1
    assert response["results"][0]["title"] == "Test ticket"
    assert response["results"][0]["source"] == "hubspot"
```

## Deployment Checklist

Before deploying connectors:

- [ ] Environment variables set (API keys, secrets)
- [ ] Rate limiting configured appropriately
- [ ] Error handling and retries implemented
- [ ] Data transformation tested with real API responses
- [ ] OAuth flow tested end-to-end (if applicable)
- [ ] Sync service scheduled (cron job or background task)
- [ ] Monitoring and alerting configured

## Success Criteria

Connector is production-ready when:
- [ ] Fetches data successfully from external API
- [ ] Handles rate limits gracefully
- [ ] Retries transient failures
- [ ] Transforms data to JisrVoC format correctly
- [ ] Stores data in database without errors
- [ ] Handles OAuth token refresh (if applicable)
- [ ] Logs errors with sufficient context
- [ ] Has test coverage > 80%

## Related Skills

- `jisrvoc-backend-context` - Backend architecture overview
- `railway-deployment` - Deploy connectors to production
- `database-migrations` - Create tables for synced data

## References

- **HubSpot API**: https://developers.hubspot.com/docs/api/overview
- **Zendesk API**: https://developer.zendesk.com/api-reference/
- **Canny API**: https://developers.canny.io/api-reference
- **Tenacity Docs**: https://tenacity.readthedocs.io/
