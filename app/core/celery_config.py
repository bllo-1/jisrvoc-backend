"""Celery configuration for task scheduling and routing."""
from celery.schedules import crontab

# Celery configuration
task_serializer = "json"
accept_content = ["json"]
result_serializer = "json"
timezone = "Asia/Riyadh"  # Saudi Arabia timezone
enable_utc = True

# Task routing
task_routes = {
    "app.workers.clustering_worker.*": {"queue": "clustering"},
    "app.workers.alert_worker.*": {"queue": "alerts"},
    "app.workers.writeback_worker.*": {"queue": "writeback"},
    "app.workers.slack_notifications.*": {"queue": "notifications"},
    "app.workers.chargebee_enrichment_worker.*": {"queue": "chargebee_enrichment"},
}

# Rate limiting
task_annotations = {
    # HubSpot API: 100 requests per minute
    "app.workers.writeback_worker.writeback_to_hubspot": {
        "rate_limit": "100/m",
    },
    # Chargebee API: 300 requests per minute
    "app.workers.chargebee_enrichment_worker.enrich_feedback_item": {
        "rate_limit": "300/m",
    },
}

# Periodic task schedule
beat_schedule = {
    # Weekly clustering - Every Monday at 2 AM UTC
    "weekly-clustering": {
        "task": "app.workers.clustering_worker.run_weekly_clustering",
        "schedule": crontab(hour=2, minute=0, day_of_week=1),  # Monday at 2 AM
    },
    # Alert checking - Every 5 minutes
    "check-urgent-alerts": {
        "task": "app.workers.alert_worker.check_urgent_feedback",
        "schedule": crontab(minute="*/5"),  # Every 5 minutes
    },
    # Chargebee enrichment - Nightly at 3 AM UTC
    "nightly-chargebee-enrichment": {
        "task": "app.workers.chargebee_enrichment_worker.enrich_unenriched_feedback",
        "schedule": crontab(hour=3, minute=0),  # Every day at 3 AM
        "kwargs": {"limit": 1000},  # Enrich up to 1000 items per night
    },
}

# Worker configuration
worker_prefetch_multiplier = 1  # Process one task at a time
task_acks_late = True  # Acknowledge task after completion
task_reject_on_worker_lost = True  # Reject task if worker crashes
task_time_limit = 3600  # 1 hour max per task
task_soft_time_limit = 3300  # 55 minutes soft limit
