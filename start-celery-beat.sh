#!/bin/bash
# Celery beat start script for Railway
echo "Starting Celery beat scheduler..."
exec celery -A app.core.celery_app beat --loglevel=info
