# Phase 3 Quick Start Guide

## 🎯 What Phase 3 Delivers

✅ Production-ready dashboard with real-time metrics
✅ Complex filtering across 9 dimensions
✅ Full-text search with cursor pagination
✅ Performance optimized (<500ms queries)
✅ Graceful degradation and error handling
✅ PRD-aligned schema architecture

## 🚀 Deploy in 3 Minutes (Docker Compose)

```bash
# 1. Clean slate deployment
docker compose down -v
docker compose up --build -d

# 2. Run migrations
docker compose exec api alembic upgrade head

# 3. Activate Phase 3 routes
mv app/api/router_phase3.py app/api/router.py
docker compose restart api

# 4. Verify deployment
curl http://localhost:8000/api/v1/overview/metrics
curl http://localhost:8000/api/v1/feedback?limit=5

# 5. Re-ingest data (if needed)
curl -X POST http://localhost:8000/api/v1/connectors/hubspot/sync
curl -X POST http://localhost:8000/api/v1/enrichment/process
```

## ✅ Success Checklist

- [ ] Migrations completed without errors
- [ ] Router switched to Phase 3 routes
- [ ] Overview metrics endpoint returns data
- [ ] Feedback filtering works with multiple filters
- [ ] Full-text search returns relevant results
- [ ] Cursor pagination works (check `next_cursor`)

## 🔍 Testing Phase 3 Features

### Overview Dashboard
```bash
# Get metrics
curl http://localhost:8000/api/v1/overview/metrics

# Volume trend (last 12 weeks)
curl http://localhost:8000/api/v1/overview/volume-trend?weeks=12

# Distribution by source
curl http://localhost:8000/api/v1/overview/by-source

# Distribution by product area
curl http://localhost:8000/api/v1/overview/by-product-area

# Top themes
curl http://localhost:8000/api/v1/overview/top-themes?limit=5
```

### Feed Filtering
```bash
# Filter by area
curl "http://localhost:8000/api/v1/feedback?area=payroll&limit=10"

# Filter by urgency
curl "http://localhost:8000/api/v1/feedback?urgency=high&limit=10"

# Multiple filters
curl "http://localhost:8000/api/v1/feedback?area=payroll&urgency=high&sentiment=negative"

# Full-text search
curl "http://localhost:8000/api/v1/feedback?q=salary&limit=10"

# Date range
curl "http://localhost:8000/api/v1/feedback?date_from=2026-01-01&date_to=2026-06-30"

# Cursor pagination
curl "http://localhost:8000/api/v1/feedback?limit=10"
# Use next_cursor from response for next page:
curl "http://localhost:8000/api/v1/feedback?limit=10&cursor=2026-06-15T10:30:00"
```

### Tag Corrections
```bash
# Get feedback item
curl http://localhost:8000/api/v1/feedback/{item_id}

# Correct tags (human-in-the-loop)
curl -X PATCH http://localhost:8000/api/v1/feedback/{item_id}/tags \
  -H "Content-Type: application/json" \
  -d '{"category": "bug_report", "urgency": "high"}'
```

## 📊 Database Schema Check

```bash
# Connect to database
docker compose exec db psql -U postgres -d jisrvoc

# Check tables
\dt

# Expected tables:
# - raw_ticket (immutable sources)
# - feedback_item (enriched units)
# - enrichment (AI audit trail)
# - embedding (vectors)
# - vote (upvotes)
# - customer (company-level)
# - theme, product_bet, etc.

# Check indexes
\di

# Expected composite indexes:
# - idx_fi_occurred_area
# - idx_fi_area_urgency
# - idx_fi_occurred_urgency
# - idx_fi_segment_area
```

## 🐛 Troubleshooting

### Migrations fail with "pgvector not found"
**Solution:** Use Docker Compose (includes pgvector) or install manually:
```bash
brew install pgvector
brew services restart postgresql@14
```

### Routes return 404
**Check:** Router file switched correctly
```bash
ls -la app/api/router.py
# Should show recent timestamp

# Verify imports
grep "phase3" app/api/router.py
```

### Empty results from endpoints
**Check:** Database has data
```bash
docker compose exec db psql -U postgres -d jisrvoc -c "SELECT COUNT(*) FROM feedback_item;"
```

If empty, re-ingest:
```bash
curl -X POST http://localhost:8000/api/v1/connectors/hubspot/sync
curl -X POST http://localhost:8000/api/v1/enrichment/process
```

### Slow queries
**Check:** Indexes exist
```bash
docker compose exec db psql -U postgres -d jisrvoc -c "\di feedback_item"
```

Should see 8+ indexes including composite ones.

## 🔄 Rollback

```bash
# Revert router
git checkout app/api/router.py
docker compose restart api

# Restore database (if backed up)
docker compose exec db psql -U postgres -d jisrvoc < backup.sql

# Or downgrade migrations
docker compose exec api alembic downgrade e34bd1c05797
```

## 📚 More Information

- **Full deployment guide:** `DEPLOYMENT.md`
- **Design document:** `docs/plans/2026-06-30-phase3-dashboard-design.md`
- **API documentation:** http://localhost:8000/docs

## 🎉 Success!

If all tests pass, Phase 3 is live! You now have:
- ⚡ Fast aggregations with composite indexes
- 🔍 Powerful filtering across 9 dimensions
- 📊 Real-time dashboard metrics
- 🛡️ Graceful error handling
- 📈 Performance monitoring ready

Next: Phase 4 (Loop Closure) or add Redis caching for even better performance.
