"""API endpoints for connector sync operations."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.db.session import get_db
from app.connectors.hubspot import HubSpotConnector
from app.services.identity_resolution import IdentityResolutionService


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/connectors", tags=["connectors"])


# Request/Response models
class HubSpotSyncRequest(BaseModel):
    """Request for Hub Spot ticket sync."""
    limit: int = 100


class HubSpotSyncResponse(BaseModel):
    """Response for HubSpot sync operations."""
    message: str
    synced_count: int
    source: str


class IdentityResolutionRequest(BaseModel):
    """Request for identity resolution."""
    limit: int = 100


class IdentityResolutionResponse(BaseModel):
    """Response for identity resolution operations."""
    message: str
    resolved_count: int


# Endpoints
@router.post("/hubspot/sync", response_model=HubSpotSyncResponse)
async def sync_hubspot_tickets(
    request: HubSpotSyncRequest = HubSpotSyncRequest(),
    db: AsyncSession = Depends(get_db),
):
    """
    Sync HubSpot support tickets to feedback table.

    Args:
        request: Sync parameters (limit)
        db: Database session

    Returns:
        Sync result with count of synced tickets
    """
    try:
        # Initialize HubSpot connector
        hubspot = HubSpotConnector(session=db)

        # Sync tickets
        synced_feedback = await hubspot.sync_tickets(limit=request.limit)

        return HubSpotSyncResponse(
            message="Successfully synced HubSpot tickets",
            synced_count=len(synced_feedback),
            source="hubspot",
        )
    except Exception as e:
        logger.error(f"Error syncing HubSpot tickets: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to sync HubSpot tickets: {str(e)}")


@router.post("/identity/resolve", response_model=IdentityResolutionResponse)
async def resolve_unlinked_feedback(
    request: IdentityResolutionRequest = IdentityResolutionRequest(),
    db: AsyncSession = Depends(get_db),
):
    """
    Resolve customer identities for feedback without customer links.

    Args:
        request: Resolution parameters (limit)
        db: Database session

    Returns:
        Resolution result with count of resolved feedback
    """
    try:
        # Initialize identity resolution service
        identity_service = IdentityResolutionService(session=db)

        # Resolve unlinked feedback
        resolved_count = await identity_service.resolve_all_unlinked_feedback(
            limit=request.limit
        )

        return IdentityResolutionResponse(
            message="Successfully resolved customer identities",
            resolved_count=resolved_count,
        )
    except Exception as e:
        logger.error(f"Error resolving identities: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to resolve identities: {str(e)}")
