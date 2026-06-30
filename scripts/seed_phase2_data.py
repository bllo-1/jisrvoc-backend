"""Seed test data for Phase 2 clustering and bet generation.

Creates diverse feedback items with embeddings to test clustering pipeline.
"""
import asyncio
import logging
from datetime import datetime, timedelta
import random
from typing import List

from app.db.session import AsyncSessionLocal
from app.models.feedback import Feedback
from app.models.customer import Customer
from app.models.company import Company
from app.ai.llm_provider import create_llm_provider

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Test feedback organized by topic clusters
FEEDBACK_CLUSTERS = {
    "performance_issues": [
        {"title": "Dashboard loading very slow", "content": "The dashboard takes over 30 seconds to load. This is affecting our daily operations significantly."},
        {"title": "API response times degraded", "content": "We've noticed API calls taking 5-10x longer than normal. Timeouts are becoming common."},
        {"title": "Page load times unacceptable", "content": "Every page takes forever to load. Our team is frustrated and considering alternatives."},
        {"title": "Slow query performance", "content": "Database queries are timing out. Reports that used to run in seconds now take minutes."},
        {"title": "System lag during peak hours", "content": "The system becomes unusable during business hours. We need better performance."},
        {"title": "Export feature extremely slow", "content": "Exporting data takes 10+ minutes. This is blocking our monthly reporting."},
        {"title": "Real-time sync delays", "content": "Data sync has significant lag. We see updates delayed by 5-10 minutes."},
        {"title": "Search functionality slow", "content": "Search takes 20-30 seconds to return results. This makes the product hard to use."},
    ],
    "ui_confusion": [
        {"title": "Navigation unclear", "content": "Can't find basic features. The menu structure doesn't make sense."},
        {"title": "Settings buried too deep", "content": "It takes 5 clicks to reach settings. Why isn't this more accessible?"},
        {"title": "Inconsistent button placement", "content": "Action buttons are in different places on different screens. Very confusing."},
        {"title": "Too many tabs and menus", "content": "The interface has too many navigation layers. Hard to find anything."},
        {"title": "Icons not intuitive", "content": "The icons don't clearly represent their functions. Need better labeling."},
        {"title": "Workflow not obvious", "content": "How do I complete a basic task? The workflow is not clear at all."},
    ],
    "mobile_app_issues": [
        {"title": "Mobile app crashes frequently", "content": "The mobile app crashes 3-4 times per day. Makes it unusable on the go."},
        {"title": "Mobile sync not working", "content": "Changes made on mobile don't sync to desktop. Data loss is a concern."},
        {"title": "Mobile UI elements too small", "content": "Buttons and text are too small on mobile. Very hard to use."},
        {"title": "Mobile app drains battery", "content": "The app drains phone battery in 2-3 hours. Not sustainable for field work."},
        {"title": "Push notifications broken", "content": "Not receiving push notifications for urgent updates. This defeats the purpose of mobile."},
    ],
    "integration_requests": [
        {"title": "Need Slack integration", "content": "We use Slack for all communication. Need native integration with notifications."},
        {"title": "Request for Salesforce sync", "content": "Our sales team needs automatic Salesforce sync. Manual export/import is not working."},
        {"title": "Google Calendar integration missing", "content": "Would love to see calendar events synced automatically with Google Calendar."},
        {"title": "Zapier support needed", "content": "Please add Zapier support so we can connect to our other tools."},
        {"title": "API for custom integrations", "content": "We need a comprehensive API to build custom integrations with our internal systems."},
    ],
    "data_export_limitations": [
        {"title": "Export format limited to CSV", "content": "Need Excel and JSON export options. CSV loses formatting."},
        {"title": "Cannot export historical data", "content": "Export only works for last 30 days. We need full history for compliance."},
        {"title": "Export missing key fields", "content": "Several important fields are missing from exports. Makes data analysis difficult."},
        {"title": "Bulk export not available", "content": "Can only export one record at a time. Need bulk export for all data."},
        {"title": "Export formatting broken", "content": "Exported data has formatting issues. Dates are corrupted."},
    ],
    "security_concerns": [
        {"title": "Need two-factor authentication", "content": "Please add 2FA support. Our security policy requires it."},
        {"title": "Session timeouts too long", "content": "Users stay logged in for days. Need configurable session timeout."},
        {"title": "Audit logs insufficient", "content": "Audit logs don't capture enough detail. Need comprehensive activity tracking."},
        {"title": "Password policy too weak", "content": "Need stronger password requirements. Current policy doesn't meet compliance standards."},
    ],
}


async def create_test_company() -> Company:
    """Create a test company."""
    async with AsyncSessionLocal() as session:
        company = Company(
            hubspot_id="test_company_phase2",
            name="Acme Corporation",
            domain="acme.com",
        )
        session.add(company)
        await session.commit()
        await session.refresh(company)
        logger.info(f"Created test company: {company.name}")
        return company


async def create_test_customers(company: Company, count: int = 5) -> List[Customer]:
    """Create test customers."""
    async with AsyncSessionLocal() as session:
        customers = []
        for i in range(count):
            customer = Customer(
                email=f"user{i+1}@acme.com",
                name=f"Test User {i+1}",
                company_id=company.id,
            )
            session.add(customer)
            customers.append(customer)

        await session.commit()
        for c in customers:
            await session.refresh(c)

        logger.info(f"Created {len(customers)} test customers")
        return customers


async def create_feedback_with_embeddings(
    llm_provider,
    customers: List[Customer],
    topic: str,
    items: List[dict],
) -> int:
    """Create feedback items with real embeddings."""
    async with AsyncSessionLocal() as session:
        created = 0

        for item in items:
            # Random customer
            customer = random.choice(customers)

            # Random created date (last 14 days)
            days_ago = random.randint(0, 14)
            created_at = datetime.utcnow() - timedelta(days=days_ago)

            # Create feedback
            feedback = Feedback(
                title=item["title"],
                content=item["content"],
                customer_id=customer.id,
                customer_email=customer.email,
                customer_name=customer.name,
                created_at=created_at,
            )

            # Assign classification and sentiment based on topic
            if "performance" in topic or "slow" in topic:
                feedback.classification = "bug"
                feedback.sentiment = "negative"
                feedback.sentiment_score = random.uniform(-0.7, -0.3)
            elif "ui" in topic or "confusing" in topic:
                feedback.classification = "feature_request"
                feedback.sentiment = "negative"
                feedback.sentiment_score = random.uniform(-0.5, -0.2)
            elif "mobile" in topic:
                feedback.classification = "bug"
                feedback.sentiment = "negative"
                feedback.sentiment_score = random.uniform(-0.8, -0.4)
            elif "integration" in topic or "export" in topic:
                feedback.classification = "feature_request"
                feedback.sentiment = "neutral"
                feedback.sentiment_score = random.uniform(-0.2, 0.2)
            elif "security" in topic:
                feedback.classification = "feature_request"
                feedback.sentiment = "neutral"
                feedback.sentiment_score = random.uniform(-0.1, 0.1)

            # Generate embedding
            try:
                embedding = await llm_provider.embed(f"{item['title']} {item['content']}")
                feedback.embedding = embedding
            except Exception as e:
                logger.warning(f"Failed to generate embedding: {e}, skipping item")
                continue

            session.add(feedback)
            created += 1

        await session.commit()
        logger.info(f"Created {created} feedback items for topic: {topic}")
        return created


async def seed_phase2_data():
    """Seed all Phase 2 test data."""
    logger.info("Starting Phase 2 data seeding")

    # Initialize LLM provider for embeddings
    llm_provider = create_llm_provider()

    # Create company
    company = await create_test_company()

    # Create customers
    customers = await create_test_customers(company, count=8)

    # Create feedback for each topic cluster
    total_created = 0
    for topic, items in FEEDBACK_CLUSTERS.items():
        count = await create_feedback_with_embeddings(
            llm_provider,
            customers,
            topic,
            items,
        )
        total_created += count

    logger.info(f"Phase 2 seeding complete: {total_created} feedback items created across {len(FEEDBACK_CLUSTERS)} topics")
    logger.info("Ready for clustering! Run POST /api/v1/clustering/trigger to test")


if __name__ == "__main__":
    asyncio.run(seed_phase2_data())
