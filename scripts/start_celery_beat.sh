#!/bin/bash
# Start Celery beat scheduler for periodic tasks

set -e

echo "Starting Celery beat scheduler..."
echo "Ensure Redis is running (redis-server) and DATABASE_URL is set in .env"

# Load virtual environment if exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Load environment variables
if [ -f ".env" ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Start Celery beat
celery -A app.core.celery_app beat \
    --loglevel=info
