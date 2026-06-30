"""Celery worker for HubSpot write-back operations (Phase 4)."""

import logging
from typing import List
from celery import shared_task
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
import asyncio

from app.core.config import settings
from app.services.hubspot_writeback import HubSpotWritebackService
from app.repositories.writeback_log import WritebackLogRepository
from app.models.bet import BetStatus

logger = logging.getLogger(__name__)


# Create async engine for worker
engine = create_async_engine(settings.normalized_database_url, pool_pre_ping=True)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,  # Start with 1 minute
)
def writeback_to_hubspot(
    self,
    bet_id: str,
    ticket_ids: List[str],
    status: str,  # String because Celery doesn't serialize enums well
    resolution_notes: str = None,
    pm_id: str = None,
):
    """
    Async task to write bet status back to HubSpot tickets.

    Retries up to 3 times with exponential backoff (60s, 120s, 240s).

    Args:
        bet_id: Product bet ID
        ticket_ids: List of HubSpot ticket IDs to update
        status: Bet status (string)
        resolution_notes: Optional resolution notes
        pm_id: PM who made the change (for logging)
    """
    try:
        # Convert string status back to enum
        bet_status = BetStatus(status)

        # Run async code in event loop
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        loop.run_until_complete(
            _writeback_async(
                bet_id=bet_id,
                ticket_ids=ticket_ids,
                status=bet_status,
                resolution_notes=resolution_notes,
                pm_id=pm_id,
            )
        )

        logger.info(f"✅ Successfully completed write-back for bet {bet_id}")

        # Trigger Slack notification for shipped bets
        if bet_status == BetStatus.SHIPPED:
            from app.workers.slack_notifications import send_slack_notification
            send_slack_notification.delay(bet_id, "shipped")

    except Exception as exc:
        logger.error(f"❌ Write-back failed for bet {bet_id}: {exc}", exc_info=True)

        # Calculate exponential backoff: 60s, 120s, 240s
        countdown = 60 * (2 ** self.request.retries)

        # Retry the task
        raise self.retry(exc=exc, countdown=countdown)


async def _writeback_async(
    bet_id: str,
    ticket_ids: List[str],
    status: BetStatus,
    resolution_notes: str = None,
    pm_id: str = None,
):
    """Async helper function to perform HubSpot write-back.

    Args:
        bet_id: Product bet ID
        ticket_ids: List of HubSpot ticket IDs
        status: Bet status
        resolution_notes: Optional notes
        pm_id: PM ID for audit trail
    """
    hubspot_service = HubSpotWritebackService()

    # Call HubSpot API to update tickets
    results = await hubspot_service.update_tickets_for_bet(
        bet_id=bet_id,
        ticket_ids=ticket_ids,
        status=status,
        resolution_notes=resolution_notes,
    )

    # Update writeback_log with results
    async with AsyncSessionLocal() as session:
        log_repo = WritebackLogRepository(session)

        for ticket_id, success in results.items():
            result_str = "success" if success else "failed:HubSpot API error"

            await log_repo.create_log_entry(
                bet_id=bet_id,
                hubspot_ticket_id=ticket_id,
                action="property_update",
                status_value=status,
                pm_id=pm_id or "system",
                result=result_str,
            )

        await log_repo.commit()

    # Log summary
    success_count = sum(1 for v in results.values() if v)
    failure_count = len(results) - success_count
    logger.info(
        f"Write-back completed for bet {bet_id}: "
        f"{success_count} succeeded, {failure_count} failed"
    )
