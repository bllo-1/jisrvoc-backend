#!/bin/bash
# Start Celery worker for clustering and bet generation tasks

set -e

echo "Starting Celery worker..."
echo "Ensure Redis is running (redis-server) and DATABASE_URL is set in .env"

# Load virtual environment if exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Load environment variables
if [ -f ".env" ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Start Celery worker
celery -A app.core.celery_app worker \
    --loglevel=info \
    --concurrency=2 \
    --pool=solo
