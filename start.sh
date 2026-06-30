#!/bin/bash

# Initialize database schema if tables don't exist
echo "Checking database schema..."
python scripts/init_db_schema.py || echo "⚠️  Schema initialization skipped (may already exist)"

# Run database migrations
echo "Running database migrations..."
alembic upgrade head || echo "⚠️  Migrations failed or already applied"

echo "Starting API server..."
exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
