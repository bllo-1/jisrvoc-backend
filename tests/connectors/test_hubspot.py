"""Tests for HubSpot connector."""

import asyncio
import pytest
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch
from types import SimpleNamespace

from app.connectors.hubspot import (
    HubSpotConnector,
    HubSpotRateLimiter,
    HubSpotAuthError,
    HubSpotRateLimitError,
    HubSpotConnectorError,
)


class TestHubSpotRateLimiter:
    """Test rate limiter token bucket implementation."""

    @pytest.mark.asyncio
    async def test_rate_limiter_allows_burst(self):
        """Rate limiter should allow burst of requests up to rate limit."""
        limiter = HubSpotRateLimiter(rate=5, per_seconds=1)

        # Should allow 5 requests immediately
        start = datetime.now()
        for _ in range(5):
            await limiter.acquire()
        elapsed = (datetime.now() - start).total_seconds()

        # All 5 should complete in < 0.1 seconds (burst)
        assert elapsed < 0.1

    @pytest.mark.asyncio
    async def test_rate_limiter_enforces_delay(self):
        """Rate limiter should enforce delay after burst is exhausted."""
        limiter = HubSpotRateLimiter(rate=5, per_seconds=1)

        # Exhaust burst allowance
        for _ in range(5):
            await limiter.acquire()

        # 6th request should be delayed
        start = datetime.now()
        await limiter.acquire()
        elapsed = (datetime.now() - start).total_seconds()

        # Should wait ~0.2 seconds (1/5 of a second)
        assert 0.15 < elapsed < 0.3

    @pytest.mark.asyncio
    async def test_rate_limiter_refills_tokens(self):
        """Rate limiter should refill tokens over time."""
        limiter = HubSpotRateLimiter(rate=10, per_seconds=1)

        # Use 5 tokens
        for _ in range(5):
            await limiter.acquire()

        # Wait 0.5 seconds (should refill 5 tokens)
        await asyncio.sleep(0.5)

        # Should allow another 5 requests immediately
        start = datetime.now()
        for _ in range(5):
            await limiter.acquire()
        elapsed = (datetime.now() - start).total_seconds()

        assert elapsed < 0.1


class TestHubSpotConnectorInit:
    """Test connector initialization and configuration."""

    def test_init_without_api_key_raises_error(self):
        """Connector should raise error when API key is missing."""
        with patch("app.connectors.hubspot.settings") as mock_settings:
            mock_settings.hubspot_api_key = ""

            with pytest.raises(HubSpotAuthError, match="not configured"):
                HubSpotConnector()

    def test_init_with_explicit_api_key(self):
        """Connector should accept explicit API key."""
        connector = HubSpotConnector(api_key="test-key")

        assert connector.api_key == "test-key"
        assert connector.rate_limiter is not None
        assert connector.mappings is not None

    def test_init_loads_field_mappings(self):
        """Connector should load field mappings from JSON."""
        connector = HubSpotConnector(api_key="test-key")

        assert "ticket_mapping" in connector.mappings
        assert "contact_mapping" in connector.mappings
        assert "company_mapping" in connector.mappings
        assert "custom_fields" in connector.mappings

    def test_rate_limiter_configured_correctly(self):
        """Rate limiter should be configured for 10 req/sec."""
        connector = HubSpotConnector(api_key="test-key")

        assert connector.rate_limiter.rate == 10
        assert connector.rate_limiter.per_seconds == 1


class TestHubSpotTicketFetching:
    """Test ticket fetching and transformation."""

    @pytest.mark.asyncio
    async def test_fetch_tickets_basic(self):
        """Should fetch and transform tickets successfully."""
        # Mock HubSpot API response
        mock_ticket = SimpleNamespace(
            id="12345",
            properties={
                "subject": "Test Issue",
                "content": "Description here",
                "hs_ticket_priority": "HIGH",
                "hs_ticket_category": "bug",
                "createdate": "2024-01-01T00:00:00Z",
                "hs_lastmodifieddate": "2024-01-02T00:00:00Z",
                "source_type": "EMAIL",
                "hs_pipeline_stage": "open",
            }
        )

        mock_response = SimpleNamespace(
            results=[mock_ticket],
            paging=None
        )

        # Mock the HubSpot client class
        with patch("app.connectors.hubspot.HubSpot") as mock_hubspot_class:
            mock_client = Mock()
            mock_client.crm.tickets.basic_api.get_page = Mock(return_value=mock_response)
            mock_hubspot_class.return_value = mock_client

            connector = HubSpotConnector(api_key="test-key")
            result = await connector.fetch_tickets(limit=10)

        assert "results" in result
        assert len(result["results"]) == 1

        ticket = result["results"][0]
        assert ticket["external_id"] == "12345"
        assert ticket["source"] == "hubspot"
        assert ticket["title"] == "Test Issue"
        assert ticket["content"] == "Description here"
        assert ticket["priority"] == "HIGH"

    @pytest.mark.asyncio
    async def test_fetch_tickets_with_pagination(self):
        """Should include pagination info when available."""
        # Create mock with dict() method
        mock_next = Mock()
        mock_next.dict.return_value = {"after": "cursor-123"}

        mock_response = SimpleNamespace(
            results=[],
            paging=SimpleNamespace(
                next=mock_next
            )
        )

        with patch("app.connectors.hubspot.HubSpot") as mock_hubspot_class:
            mock_client = Mock()
            mock_client.crm.tickets.basic_api.get_page = Mock(return_value=mock_response)
            mock_hubspot_class.return_value = mock_client

            connector = HubSpotConnector(api_key="test-key")
            result = await connector.fetch_tickets()

        assert "paging" in result
        assert result["paging"]["next"] is not None
        assert result["paging"]["next"]["after"] == "cursor-123"

    @pytest.mark.asyncio
    async def test_fetch_tickets_rate_limit_error(self):
        """Should raise HubSpotRateLimitError on 429 response."""
        from hubspot.crm.tickets import ApiException
        mock_error = ApiException(status=429, reason="Rate limit exceeded")

        with patch("app.connectors.hubspot.HubSpot") as mock_hubspot_class:
            mock_client = Mock()
            mock_client.crm.tickets.basic_api.get_page = Mock(side_effect=mock_error)
            mock_hubspot_class.return_value = mock_client

            connector = HubSpotConnector(api_key="test-key")
            with pytest.raises(HubSpotRateLimitError):
                await connector.fetch_tickets()

    @pytest.mark.asyncio
    async def test_fetch_tickets_auth_error(self):
        """Should raise HubSpotAuthError on 401/403 response."""
        connector = HubSpotConnector(api_key="test-key")

        from hubspot.crm.tickets import ApiException
        mock_error = ApiException(status=401, reason="Unauthorized")

        with patch.object(connector.client.crm.tickets.basic_api, "get_page", side_effect=mock_error):
            with pytest.raises(HubSpotAuthError):
                await connector.fetch_tickets()

    @pytest.mark.asyncio
    async def test_fetch_tickets_respects_rate_limiter(self):
        """Should call rate limiter before API requests."""
        mock_response = SimpleNamespace(results=[], paging=None)

        with patch("app.connectors.hubspot.HubSpot") as mock_hubspot_class:
            mock_client = Mock()
            mock_client.crm.tickets.basic_api.get_page = Mock(return_value=mock_response)
            mock_hubspot_class.return_value = mock_client

            connector = HubSpotConnector(api_key="test-key")
            # Mock rate limiter
            connector.rate_limiter.acquire = AsyncMock()

            await connector.fetch_tickets()

            # Verify rate limiter was called
            connector.rate_limiter.acquire.assert_called_once()


class TestHubSpotContactFetching:
    """Test contact fetching and transformation."""

    @pytest.mark.asyncio
    async def test_fetch_contacts_basic(self):
        """Should fetch and transform contacts successfully."""
        mock_contact = SimpleNamespace(
            id="67890",
            properties={
                "email": "test@example.com",
                "firstname": "John",
                "lastname": "Doe",
                "company": "Acme Corp",
                "hs_customer_tier": "enterprise",
                "createdate": "2024-01-01T00:00:00Z",
            }
        )

        mock_response = SimpleNamespace(results=[mock_contact], paging=None)

        with patch("app.connectors.hubspot.HubSpot") as mock_hubspot_class:
            mock_client = Mock()
            mock_client.crm.contacts.basic_api.get_page = Mock(return_value=mock_response)
            mock_hubspot_class.return_value = mock_client

            connector = HubSpotConnector(api_key="test-key")
            result = await connector.fetch_contacts()

        assert len(result["results"]) == 1

        contact = result["results"][0]
        assert contact["external_id"] == "67890"
        assert contact["source"] == "hubspot"
        assert contact["name"] == "John Doe"
        assert contact["email"] == "test@example.com"
        assert contact["company_name"] == "Acme Corp"

    @pytest.mark.asyncio
    async def test_fetch_contacts_handles_missing_name(self):
        """Should handle contacts with missing first/last name."""
        mock_contact = SimpleNamespace(
            id="11111",
            properties={
                "email": "noreply@example.com",
            }
        )

        mock_response = SimpleNamespace(results=[mock_contact], paging=None)

        with patch("app.connectors.hubspot.HubSpot") as mock_hubspot_class:
            mock_client = Mock()
            mock_client.crm.contacts.basic_api.get_page = Mock(return_value=mock_response)
            mock_hubspot_class.return_value = mock_client

            connector = HubSpotConnector(api_key="test-key")
            result = await connector.fetch_contacts()

        contact = result["results"][0]
        assert contact["name"] == "Unknown"


class TestHubSpotCompanyFetching:
    """Test company fetching and transformation."""

    @pytest.mark.asyncio
    async def test_fetch_companies_basic(self):
        """Should fetch and transform companies successfully."""
        mock_company = SimpleNamespace(
            id="99999",
            properties={
                "domain": "example.com",
                "name": "Example Inc",
                "industry": "Technology",
                "annualrevenue": "1000000",
                "hs_num_decision_makers": "5",
            }
        )

        mock_response = SimpleNamespace(results=[mock_company], paging=None)

        with patch("app.connectors.hubspot.HubSpot") as mock_hubspot_class:
            mock_client = Mock()
            mock_client.crm.companies.basic_api.get_page = Mock(return_value=mock_response)
            mock_hubspot_class.return_value = mock_client

            connector = HubSpotConnector(api_key="test-key")
            result = await connector.fetch_companies()

        assert len(result["results"]) == 1

        company = result["results"][0]
        assert company["external_id"] == "99999"
        assert company["source"] == "hubspot"
        assert company["domain"] == "example.com"
        assert company["company_name"] == "Example Inc"
        assert company["industry"] == "Technology"


class TestHubSpotContextManager:
    """Test async context manager functionality."""

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Should work as async context manager."""
        async with HubSpotConnector(api_key="test-key") as connector:
            assert connector is not None
            assert connector.api_key == "test-key"

    @pytest.mark.asyncio
    async def test_context_manager_calls_close(self):
        """Should call close() on context exit."""
        connector = HubSpotConnector(api_key="test-key")
        connector.close = AsyncMock()

        async with connector:
            pass

        connector.close.assert_called_once()


class TestFieldTransformation:
    """Test field mapping and transformation logic."""

    def test_ticket_transformation_preserves_metadata(self):
        """Transformed tickets should include original properties as metadata."""
        connector = HubSpotConnector(api_key="test-key")

        mock_ticket = SimpleNamespace(
            id="123",
            properties={
                "subject": "Test",
                "custom_field": "custom_value",
            }
        )

        result = connector._transform_ticket(mock_ticket)

        assert "metadata" in result
        assert result["metadata"]["custom_field"] == "custom_value"

    def test_contact_transformation_combines_names(self):
        """Contact transformation should combine first and last names."""
        connector = HubSpotConnector(api_key="test-key")

        mock_contact = SimpleNamespace(
            id="456",
            properties={
                "email": "test@example.com",
                "firstname": "Jane",
                "lastname": "Smith",
            }
        )

        result = connector._transform_contact(mock_contact)

        assert result["name"] == "Jane Smith"

    def test_transformation_handles_null_values(self):
        """Transformation should handle null/missing field values."""
        connector = HubSpotConnector(api_key="test-key")

        mock_ticket = SimpleNamespace(
            id="789",
            properties={
                "subject": "Test",
                "content": None,  # Null value
            }
        )

        result = connector._transform_ticket(mock_ticket)

        # Null values should not appear in transformed output (except metadata)
        assert "content" not in result or result["content"] is None
        assert "metadata" in result
