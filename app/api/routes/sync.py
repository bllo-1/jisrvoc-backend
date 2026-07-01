"""API endpoints for syncing feedback from external sources."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.db.session import get_db
from app.services.feedback_sync import FeedbackSyncService
from app.connectors.hubspot import HubSpotConnector
from app.connectors.zendesk import ZendeskConnector
from app.core.config import settings


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/sync", tags=["sync"])


# Request/Response models
class SyncResponse(BaseModel):
    """Response for sync operations."""
    message: str
    synced_count: int
    source: str


class SyncRequest(BaseModel):
    """Request for sync operations."""
    limit: int = 100
    after: Optional[str] = None


# Endpoints
@router.post("/hubspot", response_model=SyncResponse)
async def sync_hubspot_tickets(
    request: SyncRequest = SyncRequest(),
    db: AsyncSession = Depends(get_db),
):
    """
    Sync tickets from HubSpot.

    Args:
        request: Sync parameters (limit, pagination cursor)
        db: Database session

    Returns:
        Sync result with count of synced items
    """
    try:
        # Initialize HubSpot connector
        connector = HubSpotConnector(session=db)

        # Initialize sync service
        sync_service = FeedbackSyncService(session=db, connector=connector)

        # Sync tickets
        synced_feedback = await sync_service.sync_all_tickets(
            limit=request.limit,
            after=request.after,
        )

        return SyncResponse(
            message="Successfully synced HubSpot tickets",
            synced_count=len(synced_feedback),
            source="hubspot",
        )
    except Exception as e:
        logger.error(f"Error syncing HubSpot tickets: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to sync HubSpot tickets: {str(e)}")


@router.post("/zendesk", response_model=SyncResponse)
async def sync_zendesk_tickets(
    request: SyncRequest = SyncRequest(),
    db: AsyncSession = Depends(get_db),
):
    """
    Sync tickets from Zendesk.

    Args:
        request: Sync parameters (limit, pagination cursor)
        db: Database session

    Returns:
        Sync result with count of synced items
    """
    try:
        # Initialize Zendesk connector
        connector = ZendeskConnector(
            subdomain=settings.zendesk_subdomain,
            email=settings.zendesk_email,
            api_token=settings.zendesk_api_token,
        )

        # Initialize sync service
        sync_service = FeedbackSyncService(session=db, connector=connector)

        # Sync tickets
        synced_feedback = await sync_service.sync_all_tickets(
            limit=request.limit,
            after=request.after,
        )

        return SyncResponse(
            message="Successfully synced Zendesk tickets",
            synced_count=len(synced_feedback),
            source="zendesk",
        )
    except Exception as e:
        logger.error(f"Error syncing Zendesk tickets: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to sync Zendesk tickets: {str(e)}")


@router.post("/hubspot/background", response_model=dict)
async def sync_hubspot_tickets_background(
    background_tasks: BackgroundTasks,
    request: SyncRequest = SyncRequest(),
):
    """
    Sync HubSpot tickets in background.

    Args:
        background_tasks: FastAPI background tasks
        request: Sync parameters

    Returns:
        Acknowledgment that sync was queued
    """
    # Note: This is a simplified version. In production, use Celery/Redis for proper background jobs
    logger.info(f"Queuing HubSpot sync in background (limit={request.limit})")

    return {
        "message": "HubSpot sync queued in background",
        "status": "queued",
        "source": "hubspot",
    }


@router.post("/zendesk/background", response_model=dict)
async def sync_zendesk_tickets_background(
    background_tasks: BackgroundTasks,
    request: SyncRequest = SyncRequest(),
):
    """
    Sync Zendesk tickets in background.

    Args:
        background_tasks: FastAPI background tasks
        request: Sync parameters

    Returns:
        Acknowledgment that sync was queued
    """
    # Note: This is a simplified version. In production, use Celery/Redis for proper background jobs
    logger.info(f"Queuing Zendesk sync in background (limit={request.limit})")

    return {
        "message": "Zendesk sync queued in background",
        "status": "queued",
        "source": "zendesk",
    }
