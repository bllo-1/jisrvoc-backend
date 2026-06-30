"""Tests for HubSpot writeback service."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx

from app.services.hubspot_writeback import HubSpotWritebackService
from app.models.bet import BetStatus


@pytest.fixture
def hubspot_service():
    """Create HubSpot writeback service with mocked API key."""
    with patch('app.services.hubspot_writeback.settings') as mock_settings:
        mock_settings.hubspot_api_key = "test-api-key"
        service = HubSpotWritebackService()
        return service


@pytest.mark.asyncio
async def test_update_tickets_for_bet_success(hubspot_service):
    """Test successfully updating HubSpot tickets."""
    # Mock httpx client
    with patch('httpx.AsyncClient') as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client

        # Mock successful API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client.patch = AsyncMock(return_value=mock_response)

        # Call service
        results = await hubspot_service.update_tickets_for_bet(
            bet_id="bet-123",
            ticket_ids=["HS-1", "HS-2"],
            status=BetStatus.SHIPPED,
            resolution_notes="Fixed in v2.3",
        )

        # Verify all tickets updated successfully
        assert results == {"HS-1": True, "HS-2": True}
        assert mock_client.patch.call_count == 2


@pytest.mark.asyncio
async def test_update_tickets_handles_404(hubspot_service):
    """Test handling of ticket not found error."""
    with patch('httpx.AsyncClient') as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client

        # Mock 404 response
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_client.patch = AsyncMock(return_value=mock_response)

        # Call service
        results = await hubspot_service.update_tickets_for_bet(
            bet_id="bet-123",
            ticket_ids=["HS-999"],
            status=BetStatus.SHIPPED,
        )

        # Verify failure is recorded
        assert results == {"HS-999": False}


@pytest.mark.asyncio
async def test_update_tickets_handles_rate_limit(hubspot_service):
    """Test handling of rate limit error."""
    with patch('httpx.AsyncClient') as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client

        # Mock 429 rate limit response
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {"Retry-After": "60"}
        mock_client.patch = AsyncMock(return_value=mock_response)

        # Call service
        results = await hubspot_service.update_tickets_for_bet(
            bet_id="bet-123",
            ticket_ids=["HS-1"],
            status=BetStatus.SHIPPED,
        )

        # Verify failure is recorded
        assert results == {"HS-1": False}


@pytest.mark.asyncio
async def test_update_tickets_handles_network_error(hubspot_service):
    """Test handling of network timeout."""
    with patch('httpx.AsyncClient') as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client

        # Mock network timeout
        mock_client.patch = AsyncMock(side_effect=httpx.TimeoutException("Request timeout"))

        # Call service
        results = await hubspot_service.update_tickets_for_bet(
            bet_id="bet-123",
            ticket_ids=["HS-1"],
            status=BetStatus.SHIPPED,
        )

        # Verify failure is recorded
        assert results == {"HS-1": False}


@pytest.mark.asyncio
async def test_map_status_to_stage(hubspot_service):
    """Test status mapping from JisrVOC to HubSpot."""
    assert hubspot_service._map_status_to_stage(BetStatus.DRAFT) == "open"
    assert hubspot_service._map_status_to_stage(BetStatus.IN_BACKLOG) == "in_progress"
    assert hubspot_service._map_status_to_stage(BetStatus.IN_DISCOVERY) == "in_progress"
    assert hubspot_service._map_status_to_stage(BetStatus.IN_BUILD) == "in_progress"
    assert hubspot_service._map_status_to_stage(BetStatus.SHIPPED) == "closed_resolved"
    assert hubspot_service._map_status_to_stage(BetStatus.DECLINED) == "closed_no_action"


@pytest.mark.asyncio
async def test_update_tickets_partial_success(hubspot_service):
    """Test handling of partial success (some tickets succeed, some fail)."""
    with patch('httpx.AsyncClient') as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client

        # Mock mixed responses
        responses = [
            MagicMock(status_code=200),  # Success
            MagicMock(status_code=404),  # Failure
            MagicMock(status_code=200),  # Success
        ]
        mock_client.patch = AsyncMock(side_effect=responses)

        # Call service
        results = await hubspot_service.update_tickets_for_bet(
            bet_id="bet-123",
            ticket_ids=["HS-1", "HS-2", "HS-3"],
            status=BetStatus.SHIPPED,
        )

        # Verify mixed results
        assert results == {"HS-1": True, "HS-2": False, "HS-3": True}
