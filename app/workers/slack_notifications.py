"""Celery worker for Slack notifications (Phase 4)."""

import logging
from celery import shared_task
import httpx
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.core.config import settings
from app.repositories.bet import BetRepository

logger = logging.getLogger(__name__)


# Create async engine for worker
engine = create_async_engine(settings.normalized_database_url, pool_pre_ping=True)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@shared_task
def send_slack_notification(bet_id: str, event_type: str):
    """
    Send Slack notification for bet status changes.

    Events:
    - "shipped": Bet marked as shipped
    - "committed": New bet committed
    - "blocked": Bet blocked (high urgency)

    Args:
        bet_id: Product bet ID
        event_type: Type of event to notify
    """
    try:
        # Run async code in event loop
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        loop.run_until_complete(_send_notification_async(bet_id, event_type))

        logger.info(f"✅ Slack notification sent for bet {bet_id}: {event_type}")

    except Exception as e:
        logger.error(f"❌ Failed to send Slack notification for bet {bet_id}: {e}", exc_info=True)


async def _send_notification_async(bet_id: str, event_type: str):
    """Async helper to send Slack notification.

    Args:
        bet_id: Product bet ID
        event_type: Event type
    """
    # Skip if no webhook URL configured
    if not settings.slack_bot_token or settings.slack_bot_token == "":
        logger.debug("Slack webhook not configured, skipping notification")
        return

    # Get bet details from database
    async with AsyncSessionLocal() as session:
        bet_repo = BetRepository(session)
        bet = await bet_repo.get_by_id(bet_id)

        if not bet:
            logger.error(f"Bet {bet_id} not found, cannot send notification")
            return

        # Format Slack message
        message = _format_slack_message(bet, event_type)

        # Send to Slack
        webhook_url = f"https://hooks.slack.com/services/{settings.slack_bot_token}"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    webhook_url,
                    json={"text": message},
                    timeout=5.0,
                )

                if response.status_code != 200:
                    logger.warning(
                        f"Slack notification failed: status={response.status_code}, "
                        f"response={response.text}"
                    )

        except httpx.TimeoutException:
            logger.warning("Slack notification timed out")
        except Exception as e:
            logger.error(f"Error sending Slack notification: {e}")


def _format_slack_message(bet, event_type: str) -> str:
    """Format Slack message based on event type.

    Args:
        bet: ProductBet instance
        event_type: Event type

    Returns:
        Formatted message string
    """
    frontend_url = settings.frontend_url if hasattr(settings, 'frontend_url') else "http://localhost:3000"

    if event_type == "shipped":
        return (
            f"🎉 *Product Bet Shipped!*\n"
            f"*Title:* {bet.title}\n"
            f"*Owner:* {bet.owner_pm or 'Unassigned'}\n"
            f"*Estimated Impact:* {bet.est_customer_count or 'Unknown'} customers\n"
            f"View: {frontend_url}/bets/{bet.id}"
        )
    elif event_type == "committed":
        return (
            f"🚀 *New Product Bet Committed*\n"
            f"*Title:* {bet.title}\n"
            f"*Owner:* {bet.owner_pm or 'Unassigned'}\n"
            f"*Estimated Impact:* {bet.est_customer_count or 'Unknown'} customers\n"
            f"View: {frontend_url}/bets/{bet.id}"
        )
    elif event_type == "blocked":
        return (
            f"🚨 *Product Bet Blocked*\n"
            f"*Title:* {bet.title}\n"
            f"*Owner:* {bet.owner_pm or 'Unassigned'}\n"
            f"*Reason:* {bet.declined_reason or 'Not specified'}\n"
            f"View: {frontend_url}/bets/{bet.id}"
        )
    else:
        return f"Bet {bet.title} updated: {event_type}"
