"""Celery worker for urgent feedback alerts."""
import logging
from typing import Dict, List
from datetime import datetime, timedelta

from app.core.celery_app import celery_app
from app.db.session import AsyncSessionLocal
from app.services.slack_service import SlackService
from app.models.feedback import Feedback
from sqlalchemy import select, and_

logger = logging.getLogger(__name__)


# Define urgent classifications
URGENT_CLASSIFICATIONS = {"critical_bug", "security_issue", "data_loss"}


@celery_app.task(name="app.workers.alert_worker.check_urgent_feedback")
def check_urgent_feedback() -> Dict:
    """Check for urgent/critical feedback and send Slack alerts.

    Scheduled to run every 5 minutes via Celery Beat.
    Only alerts on feedback created in the last 10 minutes to avoid duplicates.

    Returns:
        Dict with alert count and status
    """
    logger.info("Checking for urgent feedback")

    import asyncio
    return asyncio.run(_check_urgent_feedback_async())


async def _check_urgent_feedback_async() -> Dict:
    """Async implementation of urgent feedback checking."""
    result = {
        "status": "completed",
        "alerts_sent": 0,
        "feedback_checked": 0,
    }

    async with AsyncSessionLocal() as session:
        try:
            slack_service = SlackService()

            if not slack_service.is_enabled():
                logger.info("Slack not enabled, skipping urgent feedback check")
                result["status"] = "skipped_slack_disabled"
                return result

            # Get feedback from last 10 minutes (to avoid re-alerting)
            cutoff = datetime.utcnow() - timedelta(minutes=10)

            # Query for urgent feedback
            stmt = select(Feedback).where(
                and_(
                    Feedback.classification.in_(URGENT_CLASSIFICATIONS),
                    Feedback.created_at >= cutoff,
                    Feedback.slack_alerted.is_(False),  # Not yet alerted
                )
            ).order_by(Feedback.created_at.desc())

            result_set = await session.execute(stmt)
            urgent_feedback = list(result_set.scalars().all())

            result["feedback_checked"] = len(urgent_feedback)

            if not urgent_feedback:
                logger.info("No urgent feedback found")
                return result

            logger.info(f"Found {len(urgent_feedback)} urgent feedback items to alert")

            # Send alerts
            alerts_sent = 0
            for feedback in urgent_feedback:
                success = await slack_service.send_urgent_feedback_alert(feedback)

                if success:
                    # Mark as alerted
                    feedback.slack_alerted = True
                    alerts_sent += 1

            # Commit alert flags
            await session.commit()

            result["alerts_sent"] = alerts_sent
            logger.info(f"Sent {alerts_sent} urgent feedback alerts")

            return result

        except Exception as e:
            logger.error(f"Urgent feedback check failed: {e}", exc_info=True)
            await session.rollback()
            raise


@celery_app.task(name="app.workers.alert_worker.send_manual_alert")
def send_manual_alert(feedback_id: str) -> Dict:
    """Manually trigger alert for specific feedback (called via API).

    Args:
        feedback_id: Feedback ID to alert about

    Returns:
        Dict with alert status
    """
    logger.info(f"Sending manual alert for feedback {feedback_id}")

    import asyncio
    return asyncio.run(_send_manual_alert_async(feedback_id))


async def _send_manual_alert_async(feedback_id: str) -> Dict:
    """Async implementation of manual alert."""
    result = {
        "status": "failed",
        "feedback_id": feedback_id,
        "alert_sent": False,
    }

    async with AsyncSessionLocal() as session:
        try:
            slack_service = SlackService()

            if not slack_service.is_enabled():
                result["status"] = "skipped_slack_disabled"
                return result

            # Get feedback
            stmt = select(Feedback).where(Feedback.id == feedback_id)
            result_set = await session.execute(stmt)
            feedback = result_set.scalars().first()

            if not feedback:
                result["status"] = "feedback_not_found"
                logger.warning(f"Feedback {feedback_id} not found")
                return result

            # Send alert
            success = await slack_service.send_urgent_feedback_alert(feedback)

            if success:
                feedback.slack_alerted = True
                await session.commit()
                result["status"] = "completed"
                result["alert_sent"] = True
                logger.info(f"Manual alert sent for feedback {feedback_id}")
            else:
                result["status"] = "slack_send_failed"
                logger.warning(f"Failed to send alert for feedback {feedback_id}")

            return result

        except Exception as e:
            logger.error(f"Manual alert failed: {e}", exc_info=True)
            await session.rollback()
            raise


@celery_app.task(name="app.workers.alert_worker.check_negative_sentiment")
def check_negative_sentiment(threshold: float = -0.5) -> Dict:
    """Check for feedback with very negative sentiment and alert.

    Args:
        threshold: Sentiment threshold (default: -0.5 = very negative)

    Returns:
        Dict with alert count and status
    """
    logger.info(f"Checking for negative sentiment (threshold={threshold})")

    import asyncio
    return asyncio.run(_check_negative_sentiment_async(threshold))


async def _check_negative_sentiment_async(threshold: float) -> Dict:
    """Async implementation of negative sentiment checking."""
    result = {
        "status": "completed",
        "alerts_sent": 0,
        "feedback_checked": 0,
    }

    async with AsyncSessionLocal() as session:
        try:
            slack_service = SlackService()

            if not slack_service.is_enabled():
                result["status"] = "skipped_slack_disabled"
                return result

            # Get feedback from last hour with very negative sentiment
            cutoff = datetime.utcnow() - timedelta(hours=1)

            stmt = select(Feedback).where(
                and_(
                    Feedback.sentiment_score <= threshold,
                    Feedback.created_at >= cutoff,
                    Feedback.slack_alerted.is_(False),
                )
            ).order_by(Feedback.sentiment_score.asc()).limit(5)  # Top 5 most negative

            result_set = await session.execute(stmt)
            negative_feedback = list(result_set.scalars().all())

            result["feedback_checked"] = len(negative_feedback)

            if not negative_feedback:
                logger.info("No very negative feedback found")
                return result

            logger.info(f"Found {len(negative_feedback)} very negative feedback items")

            # Send alerts
            alerts_sent = 0
            for feedback in negative_feedback:
                success = await slack_service.send_urgent_feedback_alert(feedback)

                if success:
                    feedback.slack_alerted = True
                    alerts_sent += 1

            await session.commit()

            result["alerts_sent"] = alerts_sent
            logger.info(f"Sent {alerts_sent} negative sentiment alerts")

            return result

        except Exception as e:
            logger.error(f"Negative sentiment check failed: {e}", exc_info=True)
            await session.rollback()
            raise
