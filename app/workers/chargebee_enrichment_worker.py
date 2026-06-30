"""Celery worker for Chargebee customer enrichment."""

import logging
from typing import List
from celery import shared_task, group

from app.core.celery_app import celery_app
from app.db.session import get_db
from app.repositories.feedback_item import FeedbackItemRepository
from app.services.chargebee_enrichment import ChargebeeEnrichmentService
from app.connectors.chargebee_connector import ChargebeeConnector

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    rate_limit="300/m",  # Chargebee API limit: 300 requests/minute
)
def enrich_feedback_item(self, feedback_id: str) -> dict:
    """Enrich a single feedback item with Chargebee data.

    Args:
        feedback_id: Feedback item UUID

    Returns:
        Dict with status and enrichment data
    """
    try:
        logger.info(f"Starting Chargebee enrichment for feedback {feedback_id}")

        # Get database session (sync for Celery)
        from app.db.session import SessionLocal
        db = SessionLocal()

        try:
            # Get feedback item
            from app.models.feedback_item import FeedbackItem
            from sqlalchemy import select

            result = db.execute(
                select(FeedbackItem)
                .where(FeedbackItem.id == feedback_id)
            )
            feedback = result.scalars().first()

            if not feedback:
                logger.warning(f"Feedback {feedback_id} not found")
                return {"status": "not_found", "feedback_id": feedback_id}

            # Skip if already enriched recently (within 24 hours)
            if feedback.enriched_at:
                from datetime import datetime, timedelta
                if datetime.utcnow() - feedback.enriched_at < timedelta(hours=24):
                    logger.info(f"Feedback {feedback_id} already enriched recently, skipping")
                    return {
                        "status": "skipped",
                        "feedback_id": feedback_id,
                        "reason": "already_enriched_recently"
                    }

            # Get customer email
            if not feedback.customer_id:
                logger.info(f"Feedback {feedback_id} has no customer, skipping enrichment")
                return {
                    "status": "skipped",
                    "feedback_id": feedback_id,
                    "reason": "no_customer"
                }

            # Get customer email from customer record
            from app.models.customer import Customer
            customer_result = db.execute(
                select(Customer).where(Customer.id == feedback.customer_id)
            )
            customer = customer_result.scalars().first()

            if not customer or not customer.email:
                logger.info(f"Customer {feedback.customer_id} has no email, skipping enrichment")
                return {
                    "status": "skipped",
                    "feedback_id": feedback_id,
                    "reason": "no_email"
                }

            # Enrich customer data from Chargebee
            # Note: This is sync code for Celery, so we need to use asyncio.run()
            import asyncio
            enrichment_service = ChargebeeEnrichmentService()
            enrichment_data = asyncio.run(enrichment_service.enrich_customer(customer.email))

            if not enrichment_data:
                logger.info(f"No Chargebee data found for customer {customer.email}")
                return {
                    "status": "not_found_in_chargebee",
                    "feedback_id": feedback_id,
                    "customer_email": customer.email
                }

            # Update feedback item with enrichment data
            feedback.customer_mrr = enrichment_data["customer_mrr"]
            feedback.customer_ltv = enrichment_data["customer_ltv"]
            feedback.segment = enrichment_data["customer_segment"]  # Update segment from Chargebee
            feedback.churn_risk_score = enrichment_data["churn_risk_score"]
            feedback.subscription_plan = enrichment_data["subscription_plan"]
            feedback.enriched_at = enrichment_data["enriched_at"]

            db.commit()

            logger.info(
                f"Successfully enriched feedback {feedback_id}: "
                f"MRR=${enrichment_data['customer_mrr']}, "
                f"LTV=${enrichment_data['customer_ltv']}, "
                f"churn_risk={enrichment_data['churn_risk_score']}"
            )

            return {
                "status": "success",
                "feedback_id": feedback_id,
                "enrichment": enrichment_data
            }

        finally:
            db.close()

    except Exception as e:
        logger.error(f"Error enriching feedback {feedback_id}: {e}", exc_info=True)
        # Retry with exponential backoff
        raise self.retry(exc=e)


@shared_task
def batch_enrich_feedback(feedback_ids: List[str]) -> dict:
    """Enrich multiple feedback items in parallel.

    Uses Celery group to process items concurrently while respecting rate limits.

    Args:
        feedback_ids: List of feedback item UUIDs

    Returns:
        Dict with batch processing stats
    """
    logger.info(f"Starting batch enrichment for {len(feedback_ids)} feedback items")

    # Create a group of enrichment tasks
    job = group(enrich_feedback_item.s(fid) for fid in feedback_ids)
    result = job.apply_async()

    # Wait for all tasks to complete (with timeout)
    results = result.get(timeout=600)  # 10 minute timeout

    # Aggregate results
    stats = {
        "total": len(feedback_ids),
        "success": sum(1 for r in results if r.get("status") == "success"),
        "not_found": sum(1 for r in results if r.get("status") == "not_found"),
        "skipped": sum(1 for r in results if r.get("status") == "skipped"),
        "not_found_in_chargebee": sum(1 for r in results if r.get("status") == "not_found_in_chargebee"),
        "failed": sum(1 for r in results if r.get("status") == "error"),
    }

    logger.info(f"Batch enrichment complete: {stats}")

    return stats


@shared_task
def enrich_unenriched_feedback(limit: int = 1000) -> dict:
    """Enrich all feedback items that haven't been enriched yet.

    This is useful for:
    1. Initial backfill after Phase 5 deployment
    2. Periodic re-enrichment (run nightly)

    Args:
        limit: Maximum number of items to enrich in one batch

    Returns:
        Dict with enrichment stats
    """
    logger.info(f"Finding unenriched feedback items (limit={limit})")

    # Get database session
    from app.db.session import SessionLocal
    db = SessionLocal()

    try:
        from app.models.feedback_item import FeedbackItem
        from sqlalchemy import select

        # Find feedback items without enrichment data
        result = db.execute(
            select(FeedbackItem.id)
            .where(FeedbackItem.enriched_at.is_(None))
            .where(FeedbackItem.customer_id.is_not(None))  # Only items with customers
            .limit(limit)
        )
        feedback_ids = [str(row[0]) for row in result.fetchall()]

        logger.info(f"Found {len(feedback_ids)} unenriched feedback items")

        if not feedback_ids:
            return {"status": "no_items", "total": 0}

        # Trigger batch enrichment
        stats = batch_enrich_feedback(feedback_ids)

        return stats

    finally:
        db.close()
