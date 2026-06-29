"""Tests for Zendesk connector."""

import asyncio
import pytest
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch
import httpx

from app.connectors.zendesk import (
    ZendeskConnector,
    ZendeskRateLimiter,
    ZendeskAuthError,
    ZendeskRateLimitError,
    ZendeskConnectorError,
)


class TestZendeskRateLimiter:
    """Test rate limiter token bucket implementation."""

    @pytest.mark.asyncio
    async def test_rate_limiter_allows_burst(self):
        """Rate limiter should allow burst of requests up to rate limit."""
        limiter = ZendeskRateLimiter(rate=10, per_seconds=1)

        # Should allow 10 requests immediately
        start = datetime.now()
        for _ in range(10):
            await limiter.acquire()
        elapsed = (datetime.now() - start).total_seconds()

        # All 10 should complete in < 0.1 seconds (burst)
        assert elapsed < 0.1

    @pytest.mark.asyncio
    async def test_rate_limiter_enforces_delay(self):
        """Rate limiter should enforce delay after burst is exhausted."""
        limiter = ZendeskRateLimiter(rate=10, per_seconds=1)

        # Exhaust burst allowance
        for _ in range(10):
            await limiter.acquire()

        # 11th request should be delayed
        start = datetime.now()
        await limiter.acquire()
        elapsed = (datetime.now() - start).total_seconds()

        # Should wait ~0.1 seconds (1/10 of a second)
        assert 0.05 < elapsed < 0.2

    @pytest.mark.asyncio
    async def test_rate_limiter_configured_for_180_per_minute(self):
        """Default rate limiter should be 180 req/min (3 req/sec)."""
        limiter = ZendeskRateLimiter(rate=180, per_seconds=60)

        assert limiter.rate == 180
        assert limiter.per_seconds == 60


class TestZendeskConnectorInit:
    """Test connector initialization and configuration."""

    def test_init_without_credentials_raises_error(self):
        """Connector should raise error when credentials are missing."""
        with patch("app.connectors.zendesk.settings") as mock_settings:
            mock_settings.zendesk_subdomain = ""
            mock_settings.zendesk_email = ""
            mock_settings.zendesk_api_token = ""

            with pytest.raises(ZendeskAuthError, match="credentials not configured"):
                ZendeskConnector()

    def test_init_with_explicit_credentials(self):
        """Connector should accept explicit credentials."""
        connector = ZendeskConnector(
            subdomain="test-company",
            email="test@example.com",
            api_token="test-token",
        )

        assert connector.subdomain == "test-company"
        assert connector.email == "test@example.com"
        assert connector.api_token == "test-token"
        assert connector.base_url == "https://test-company.zendesk.com/api/v2"

    def test_init_loads_field_mappings(self):
        """Connector should load field mappings from JSON."""
        connector = ZendeskConnector(
            subdomain="test",
            email="test@example.com",
            api_token="token",
        )

        assert "ticket_mapping" in connector.mappings
        assert "user_mapping" in connector.mappings
        assert "organization_mapping" in connector.mappings
        assert "satisfaction_mapping" in connector.mappings

    def test_rate_limiter_configured_correctly(self):
        """Rate limiter should be configured for 180 req/min."""
        connector = ZendeskConnector(
            subdomain="test",
            email="test@example.com",
            api_token="token",
        )

        assert connector.rate_limiter.rate == 180
        assert connector.rate_limiter.per_seconds == 60


class TestZendeskTicketFetching:
    """Test ticket fetching and transformation."""

    @pytest.mark.asyncio
    async def test_fetch_tickets_basic(self):
        """Should fetch and transform tickets successfully."""
        mock_ticket = {
            "id": 12345,
            "subject": "Website down",
            "description": "The website is not loading",
            "priority": "urgent",
            "type": "incident",
            "status": "open",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-02T00:00:00Z",
            "via": {"channel": "web"},
            "tags": ["website", "critical"],
            "requester_id": 67890,
        }

        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "tickets": [mock_ticket],
            "end_time": 1704153600,
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            connector = ZendeskConnector(
                subdomain="test",
                email="test@example.com",
                api_token="token",
            )
            result = await connector.fetch_tickets(start_time=1704067200)

        assert "tickets" in result
        assert len(result["tickets"]) == 1

        ticket = result["tickets"][0]
        assert ticket["external_id"] == "12345"  # Connector converts to string
        assert ticket["source"] == "zendesk"
        assert ticket["title"] == "Website down"
        assert ticket["content"] == "The website is not loading"
        assert ticket["priority"] == "urgent"
        assert ticket["status"] == "open"
        assert ticket["source_channel"] == "web"

    @pytest.mark.asyncio
    async def test_fetch_tickets_with_next_page(self):
        """Should include next_page URL when available."""
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "tickets": [],
            "next_page": "https://test.zendesk.com/api/v2/incremental/tickets.json?start_time=1234567890",
            "end_time": 1704153600,
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            connector = ZendeskConnector(
                subdomain="test",
                email="test@example.com",
                api_token="token",
            )
            result = await connector.fetch_tickets()

        assert "next_page" in result
        assert result["next_page"].startswith("https://")

    @pytest.mark.asyncio
    async def test_fetch_tickets_rate_limit_error(self):
        """Should raise ZendeskRateLimitError on 429 response."""
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 429
        mock_response.headers = {"Retry-After": "60"}

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            connector = ZendeskConnector(
                subdomain="test",
                email="test@example.com",
                api_token="token",
            )

            with pytest.raises(ZendeskRateLimitError, match="Rate limit exceeded"):
                await connector.fetch_tickets()

    @pytest.mark.asyncio
    async def test_fetch_tickets_auth_error(self):
        """Should raise ZendeskAuthError on 401/403 response."""
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            connector = ZendeskConnector(
                subdomain="test",
                email="test@example.com",
                api_token="token",
            )

            with pytest.raises(ZendeskAuthError, match="Authentication failed"):
                await connector.fetch_tickets()

    @pytest.mark.asyncio
    async def test_fetch_tickets_defaults_to_30_days(self):
        """Should default to last 30 days when no start_time provided."""
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"tickets": []}

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            connector = ZendeskConnector(
                subdomain="test",
                email="test@example.com",
                api_token="token",
            )
            await connector.fetch_tickets()

            # Verify the call was made with a start_time
            call_args = mock_client.get.call_args
            assert "params" in call_args.kwargs
            assert "start_time" in call_args.kwargs["params"]


class TestZendeskUserFetching:
    """Test user fetching and transformation."""

    @pytest.mark.asyncio
    async def test_fetch_users_basic(self):
        """Should fetch and transform users successfully."""
        mock_user = {
            "id": 67890,
            "email": "user@example.com",
            "name": "John Doe",
            "organization_id": 11111,
            "role": "end-user",
        }

        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"users": [mock_user]}

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            connector = ZendeskConnector(
                subdomain="test",
                email="test@example.com",
                api_token="token",
            )
            result = await connector.fetch_users()

        assert len(result["users"]) == 1

        user = result["users"][0]
        assert user["external_id"] == "67890"
        assert user["source"] == "zendesk"
        assert user["email"] == "user@example.com"
        assert user["name"] == "John Doe"
        assert user["company_external_id"] == 11111


class TestZendeskOrganizationFetching:
    """Test organization fetching and transformation."""

    @pytest.mark.asyncio
    async def test_fetch_organizations_basic(self):
        """Should fetch and transform organizations successfully."""
        mock_org = {
            "id": 11111,
            "name": "Acme Corp",
            "domain_names": ["acme.com", "acme.net"],
        }

        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"organizations": [mock_org]}

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            connector = ZendeskConnector(
                subdomain="test",
                email="test@example.com",
                api_token="token",
            )
            result = await connector.fetch_organizations()

        assert len(result["organizations"]) == 1

        org = result["organizations"][0]
        assert org["external_id"] == "11111"
        assert org["source"] == "zendesk"
        assert org["company_name"] == "Acme Corp"
        assert org["domain"] == "acme.com"  # Takes first domain

    @pytest.mark.asyncio
    async def test_fetch_organizations_handles_empty_domains(self):
        """Should handle organizations with no domain names."""
        mock_org = {
            "id": 22222,
            "name": "No Domain Corp",
            "domain_names": [],
        }

        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"organizations": [mock_org]}

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            connector = ZendeskConnector(
                subdomain="test",
                email="test@example.com",
                api_token="token",
            )
            result = await connector.fetch_organizations()

        org = result["organizations"][0]
        assert "domain" not in org or org.get("domain") is None


class TestZendeskContextManager:
    """Test async context manager functionality."""

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Should work as async context manager."""
        async with ZendeskConnector(
            subdomain="test",
            email="test@example.com",
            api_token="token",
        ) as connector:
            assert connector is not None
            assert connector.subdomain == "test"

    @pytest.mark.asyncio
    async def test_context_manager_calls_close(self):
        """Should call close() on context exit."""
        connector = ZendeskConnector(
            subdomain="test",
            email="test@example.com",
            api_token="token",
        )
        connector.close = AsyncMock()

        async with connector:
            pass

        connector.close.assert_called_once()


class TestFieldTransformation:
    """Test field mapping and transformation logic."""

    def test_ticket_transformation_preserves_metadata(self):
        """Transformed tickets should include original properties as metadata."""
        connector = ZendeskConnector(
            subdomain="test",
            email="test@example.com",
            api_token="token",
        )

        mock_ticket = {
            "id": 123,
            "subject": "Test",
            "custom_field": "custom_value",
            "via": {"channel": "email"},
        }

        result = connector._transform_ticket(mock_ticket)

        assert "metadata" in result
        assert result["metadata"]["custom_field"] == "custom_value"

    def test_ticket_transformation_handles_nested_fields(self):
        """Should correctly extract nested field values (via.channel)."""
        connector = ZendeskConnector(
            subdomain="test",
            email="test@example.com",
            api_token="token",
        )

        mock_ticket = {
            "id": 456,
            "subject": "Test",
            "via": {"channel": "chat", "source": {"from": {}}},
        }

        result = connector._transform_ticket(mock_ticket)

        assert result["source_channel"] == "chat"

    def test_ticket_transformation_handles_satisfaction_rating(self):
        """Should extract satisfaction score when available."""
        connector = ZendeskConnector(
            subdomain="test",
            email="test@example.com",
            api_token="token",
        )

        mock_ticket = {
            "id": 789,
            "subject": "Test",
            "satisfaction_rating": {"score": "good", "comment": "Great service!"},
        }

        result = connector._transform_ticket(mock_ticket)

        assert result["satisfaction_score"] == "good"

    def test_organization_transformation_takes_first_domain(self):
        """Organization transformation should take first domain from array."""
        connector = ZendeskConnector(
            subdomain="test",
            email="test@example.com",
            api_token="token",
        )

        mock_org = {
            "id": 111,
            "name": "Multi Domain Corp",
            "domain_names": ["primary.com", "secondary.com", "tertiary.com"],
        }

        result = connector._transform_organization(mock_org)

        assert result["domain"] == "primary.com"
