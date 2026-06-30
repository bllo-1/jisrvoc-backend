#!/bin/bash
# Celery worker start script for Railway
echo "Starting Celery worker..."
exec celery -A app.core.celery_app worker \
  --loglevel=info \
  --concurrency=4 \
  --queues=writeback,notifications,chargebee_enrichment,clustering,alerts
