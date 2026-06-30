"""HubSpot write-back service for updating tickets with bet status."""

import logging
from typing import List, Dict
import httpx

from app.core.config import settings
from app.models.bet import BetStatus

logger = logging.getLogger(__name__)


class HubSpotWritebackService:
    """Service for writing bet status changes back to HubSpot tickets."""

    def __init__(self):
        """Initialize HubSpot writeback service."""
        self.api_key = settings.hubspot_api_key
        self.base_url = "https://api.hubapi.com"

    async def update_tickets_for_bet(
        self,
        bet_id: str,
        ticket_ids: List[str],
        status: BetStatus,
        resolution_notes: str = None,
    ) -> Dict[str, bool]:
        """Update multiple HubSpot tickets with bet resolution.

        Args:
            bet_id: Product bet ID
            ticket_ids: List of HubSpot ticket IDs to update
            status: New bet status
            resolution_notes: Optional resolution notes

        Returns:
            Dictionary mapping ticket_id to success boolean
        """
        results = {}

        async with httpx.AsyncClient() as client:
            for ticket_id in ticket_ids:
                try:
                    # Map status to HubSpot stage
                    hubspot_stage = self._map_status_to_stage(status)

                    # Update ticket properties
                    response = await client.patch(
                        f"{self.base_url}/crm/v3/objects/tickets/{ticket_id}",
                        headers={"Authorization": f"Bearer {self.api_key}"},
                        json={
                            "properties": {
                                "hs_pipeline_stage": hubspot_stage,
                                "product_bet_id": bet_id,
                                "resolution_notes": resolution_notes or "",
                            }
                        },
                        timeout=10.0,
                    )

                    # Check if successful
                    success = response.status_code == 200
                    results[ticket_id] = success

                    if success:
                        logger.info(f"Successfully updated HubSpot ticket {ticket_id} for bet {bet_id}")
                    else:
                        logger.warning(
                            f"Failed to update HubSpot ticket {ticket_id}: "
                            f"status={response.status_code}"
                        )

                except httpx.TimeoutException as e:
                    logger.error(f"Timeout updating HubSpot ticket {ticket_id}: {e}")
                    results[ticket_id] = False

                except Exception as e:
                    logger.error(f"Error updating HubSpot ticket {ticket_id}: {e}")
                    results[ticket_id] = False

        return results

    def _map_status_to_stage(self, status: BetStatus) -> str:
        """Map JisrVOC bet status to HubSpot pipeline stage.

        Args:
            status: Bet status

        Returns:
            HubSpot pipeline stage string
        """
        mapping = {
            BetStatus.DRAFT: "open",
            BetStatus.IN_BACKLOG: "in_progress",
            BetStatus.IN_DISCOVERY: "in_progress",
            BetStatus.IN_BUILD: "in_progress",
            BetStatus.SHIPPED: "closed_resolved",
            BetStatus.DECLINED: "closed_no_action",
        }
        return mapping.get(status, "open")
