"""Celery application configuration for JisrVOC background workers.

Workers:
- Clustering worker: Weekly theme clustering and bet generation
- Alert worker: Real-time Slack alerts for urgent feedback
- Writeback worker: HubSpot write-back for bet status updates (Phase 4)
- Slack notifications: Notification dispatcher (Phase 4)
- Chargebee enrichment: Customer data enrichment (Phase 5)
"""
from celery import Celery
from app.core.config import settings

# Create Celery app
celery_app = Celery(
    "jisrvoc",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "app.workers.clustering_worker",
        "app.workers.alert_worker",
        "app.workers.writeback_worker",  # Phase 4: HubSpot write-back
        "app.workers.slack_notifications",  # Phase 4: Slack notifications
        "app.workers.chargebee_enrichment_worker",  # Phase 5: Chargebee enrichment
    ],
)

# Load configuration from celery_config module
celery_app.config_from_object("app.core.celery_config")

if __name__ == "__main__":
    celery_app.start()
