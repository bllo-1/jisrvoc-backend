# Phase 3 Deployment Guide

## Current Status

Phase 3 code is complete and ready. However, the database migration requires manual steps due to:
1. Local PostgreSQL missing `pgvector` extension
2. Existing schema conflicts with clean slate migration

## Option 1: Clean Slate (Recommended for Dev/Staging)

**Use Docker Compose** (includes pgvector):

```bash
# Stop existing containers
docker compose down -v

# Start fresh with new schema
docker compose up --build

# Run migrations
docker compose exec api alembic upgrade head

# Verify schema
docker compose exec db psql -U postgres -d jisrvoc -c "\dt"
```

This will:
- Drop all existing tables
- Create new schema from `db/schema.sql`
- Apply composite indexes

## Option 2: Manual Migration (Current Local Setup)

If you want to keep using local PostgreSQL:

### Step 1: Install pgvector

```bash
# macOS (Homebrew)
brew install pgvector

# Or compile from source
git clone https://github.com/pgvector/pgvector.git
cd pgvector
make
make install  # may need sudo

# Restart PostgreSQL
brew services restart postgresql@14
```

### Step 2: Drop and Recreate Database

```bash
# Backup if needed
pg_dump jisrvoc > backup.sql

# Drop and recreate
dropdb jisrvoc
createdb jisrvoc

# Apply schema manually
psql jisrvoc < db/schema.sql

# Mark migrations as applied
alembic stamp head
```

### Step 3: Re-ingest Data

```bash
# Run HubSpot sync
curl -X POST http://localhost:8000/api/v1/connectors/hubspot/sync

# Run enrichment pipeline
curl -X POST http://localhost:8000/api/v1/enrichment/process
```

## Option 3: Skip Migration (Use Phase 3 Code with Old Schema)

**NOT RECOMMENDED** but possible:

The Phase 3 routes expect the new schema structure. To use them with the old schema, you would need to:
1. Keep using `overview.py` and `feedback.py` (old routes)
2. Gradually migrate data in background
3. Switch routes when ready

This defeats the purpose of Phase 3.

## Verifying Deployment

After migration:

```bash
# Check tables exist
psql jisrvoc -c "\dt"

# Should see:
# - raw_ticket
# - feedback_item
# - enrichment
# - embedding
# - vote
# - source_connector
# - customer
# - theme
# - product_bet
# ... and others

# Check indexes
psql jisrvoc -c "\di"

# Should see composite indexes:
# - idx_fi_occurred_area
# - idx_fi_area_urgency
# - idx_fi_occurred_urgency
# - idx_fi_segment_area

# Test API
curl http://localhost:8000/api/v1/overview/metrics
curl http://localhost:8000/api/v1/feedback?limit=10
```

## Next: Update Router

Once schema is in place, update the router in `app/api/router.py`:

```python
# Change from:
from .routes import overview, feedback

# To:
from .routes import overview_phase3 as overview
from .routes import feedback_phase3 as feedback
```

## Rollback Plan

If Phase 3 has issues:

```bash
# Revert router changes
git checkout app/api/router.py

# Restore from backup
psql jisrvoc < backup.sql

# Downgrade migrations (if partially applied)
alembic downgrade e34bd1c05797
```

## Monitoring After Deployment

Watch for:
- Query performance (should be <500ms p95)
- Error rates in analytics service
- Graceful degradation logs (partial failures)

```bash
# Watch logs
docker compose logs -f api

# Or local
tail -f logs/app.log
```

## Production Deployment

For production, use **data preservation migration** instead of clean slate:
1. Create new tables alongside old ones
2. Migrate data programmatically
3. Run enrichment on migrated data
4. Validate data accuracy
5. Switch routes
6. Drop old tables after validation period

See `docs/plans/2026-06-30-phase3-dashboard-design.md` for details.
