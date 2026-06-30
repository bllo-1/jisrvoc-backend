# Phase 5 Quick Start Guide

**Goal:** Deploy Chargebee enrichment to production in <30 minutes.

---

## Prerequisites

- [ ] Phase 4 deployed (HubSpot write-back working)
- [ ] Chargebee API key obtained
- [ ] Redis running
- [ ] PostgreSQL database accessible

---

## Step 1: Environment Setup (5 mins)

### Add Chargebee Credentials

Edit `.env`:

```bash
# Chargebee (Phase 5)
CHARGEBEE_API_KEY=test_your_api_key_here
CHARGEBEE_SITE=jisr

# Redis (if not already set)
REDIS_URL=redis://localhost:6379/0
```

---

## Step 2: Database Migration (2 mins)

```bash
# Activate virtual environment
source venv/bin/activate

# Run migration
alembic upgrade head

# Verify new columns
psql $DATABASE_URL -c "\d+ feedback_item" | grep -E "customer_mrr|customer_ltv|churn_risk"
```

**Expected output:**
```
customer_mrr         | numeric(10,2)
customer_ltv         | numeric(10,2)
churn_risk_score     | integer
subscription_plan    | character varying(100)
enriched_at          | timestamp with time zone
```

---

## Step 3: Start Celery Worker (2 mins)

```bash
# Start Celery with chargebee_enrichment queue
celery -A app.core.celery_app worker \
  --loglevel=info \
  --concurrency=4 \
  --queues=writeback,notifications,chargebee_enrichment,clustering,alerts &

# Verify worker started
celery -A app.core.celery_app inspect active_queues
```

**Expected output:**
```json
{
  "celery@hostname": [
    {"name": "writeback"},
    {"name": "notifications"},
    {"name": "chargebee_enrichment"},
    ...
  ]
}
```

---

## Step 4: Test Enrichment (10 mins)

### 4.1 Test Single Customer

Create a Python script `test_enrichment.py`:

```python
import asyncio
from app.connectors.chargebee_connector import ChargebeeConnector
from app.services.chargebee_enrichment import ChargebeeEnrichmentService

async def test():
    # Test connector
    connector = ChargebeeConnector()
    customer = await connector.get_customer_by_email("test@jisr.com")
    print(f"Customer: {customer}")

    # Test enrichment service
    service = ChargebeeEnrichmentService()
    enrichment = await service.enrich_customer("test@jisr.com")
    print(f"Enrichment: {enrichment}")

asyncio.run(test())
```

Run:
```bash
python test_enrichment.py
```

**Expected output:**
```json
{
  "customer_id": "cust_abc123",
  "customer_mrr": 5000.0,
  "customer_ltv": 120000.0,
  "customer_segment": "mid_market",
  "churn_risk_score": 10,
  "subscription_plan": "growth-plan",
  "enriched_at": "2026-06-30T15:30:00Z"
}
```

### 4.2 Test Celery Task

```python
from app.workers.chargebee_enrichment_worker import enrich_feedback_item

# Trigger enrichment for a feedback item
result = enrich_feedback_item.delay("feedback-uuid-here")
print(f"Task ID: {result.id}")

# Check task status
print(f"Status: {result.status}")
print(f"Result: {result.get(timeout=30)}")
```

---

## Step 5: Initial Backfill (10 mins)

### Option A: Manual Trigger (Recommended)

```bash
# Enrich first 100 items (for testing)
python -c "
from app.workers.chargebee_enrichment_worker import enrich_unenriched_feedback
result = enrich_unenriched_feedback.delay(limit=100)
print(f'Task ID: {result.id}')
print(f'Result: {result.get(timeout=600)}')
"
```

### Option B: Via API Endpoint

Create an admin endpoint (optional):

```python
# app/api/routes/admin.py
@router.post("/admin/enrich-feedback")
async def trigger_enrichment(limit: int = 1000):
    from app.workers.chargebee_enrichment_worker import enrich_unenriched_feedback
    task = enrich_unenriched_feedback.delay(limit=limit)
    return {"task_id": str(task.id), "status": "queued"}
```

Then:
```bash
curl -X POST http://localhost:8000/api/v1/admin/enrich-feedback?limit=100
```

---

## Step 6: Verify Results (5 mins)

### Check Enriched Feedback

```sql
SELECT
  id,
  customer_mrr,
  customer_ltv,
  segment,
  churn_risk_score,
  subscription_plan,
  enriched_at
FROM feedback_item
WHERE enriched_at IS NOT NULL
LIMIT 10;
```

**Expected:**
```
id                  | customer_mrr | customer_ltv | segment     | churn_risk | plan
--------------------+--------------+--------------+-------------+------------+-------------
uuid-1              | 5000.00      | 120000.00    | mid_market  | 10         | growth-plan
uuid-2              | 500.00       | 6000.00      | smb         | 30         | starter
...
```

### Check Redis Cache

```bash
redis-cli
> KEYS customer_enrichment:*
> TTL customer_enrichment:abc123...
> GET customer_enrichment:abc123...
```

**Expected:**
- Keys exist for enriched customers
- TTL ~86400 seconds (24 hours)
- JSON data with customer/subscriptions/invoices

---

## Step 7: Monitor (Ongoing)

### Check Celery Task Logs

```bash
tail -f celery_worker.log | grep -E "enrich_feedback|chargebee"
```

**Expected:**
```
[2026-06-30 15:30:00] INFO: Starting Chargebee enrichment for feedback abc-123
[2026-06-30 15:30:02] INFO: Found Chargebee customer for email test@jisr.com: cust_abc123
[2026-06-30 15:30:05] INFO: Successfully enriched feedback abc-123: MRR=$5000, LTV=$120000, churn_risk=10
```

### Check Enrichment Stats

```sql
-- Enrichment coverage
SELECT
  COUNT(*) as total_feedback,
  COUNT(enriched_at) as enriched_count,
  ROUND(100.0 * COUNT(enriched_at) / COUNT(*), 2) as enrichment_rate
FROM feedback_item
WHERE customer_id IS NOT NULL;

-- Segment distribution
SELECT
  segment,
  COUNT(*) as count,
  AVG(customer_mrr) as avg_mrr,
  AVG(customer_ltv) as avg_ltv
FROM feedback_item
WHERE enriched_at IS NOT NULL
GROUP BY segment;

-- High churn risk customers
SELECT
  customer_id,
  COUNT(*) as feedback_count,
  AVG(churn_risk_score) as avg_churn_risk,
  MAX(customer_mrr) as mrr
FROM feedback_item
WHERE churn_risk_score > 50
GROUP BY customer_id
ORDER BY avg_churn_risk DESC
LIMIT 10;
```

---

## Troubleshooting

### Issue: "Chargebee API key not configured"

**Solution:**
- Verify `CHARGEBEE_API_KEY` in `.env`
- Restart API server: `pkill -f uvicorn && uvicorn app.main:app --reload`

### Issue: "Redis connection refused"

**Solution:**
```bash
# Check Redis status
redis-cli ping

# Start Redis if needed
redis-server &
```

### Issue: "No Chargebee customer found"

**Possible causes:**
1. Customer email doesn't exist in Chargebee
2. API key has wrong permissions
3. Site name incorrect in `CHARGEBEE_SITE`

**Debug:**
```python
from app.connectors.chargebee_connector import ChargebeeConnector
connector = ChargebeeConnector()
result = await connector.get_customer_by_email("known-email@jisr.com")
print(result)
```

### Issue: "Rate limit exceeded"

**Solution:**
- Celery worker already has rate limiting (300 req/min)
- If still hitting limits, reduce batch size:
  ```python
  enrich_unenriched_feedback.delay(limit=50)  # Smaller batches
  ```

### Issue: "Migration fails"

**Solution:**
```bash
# Check current migration
alembic current

# If stuck, downgrade and re-upgrade
alembic downgrade -1
alembic upgrade head
```

---

## Production Checklist

### Before Go-Live

- [ ] Chargebee API key has production credentials (not test)
- [ ] Database backups enabled
- [ ] Redis persistence enabled (AOF or RDB)
- [ ] Celery worker runs as systemd service (auto-restart)
- [ ] Monitoring dashboards created (Grafana/Datadog)
- [ ] Alert rules configured (enrichment failures, rate limits)
- [ ] Cache TTL tested (verify 24h expiration)

### Post-Deployment

- [ ] Run initial backfill (all existing feedback)
- [ ] Monitor enrichment success rate (target: >90%)
- [ ] Verify cache hit rate (target: >70%)
- [ ] Check Chargebee API usage (stay under 300 req/min)
- [ ] Test frontend displays enrichment data correctly

---

## Next Steps

1. **Add Filters to Feedback API:**
   - Filter by MRR range
   - Filter by churn risk score
   - Filter by customer segment

2. **Create Dashboard Widgets:**
   - High-value customer feedback (>$10K LTV)
   - High churn risk alerts (>70 score)
   - Segment breakdown charts

3. **Integrate with Bet Generation:**
   - Prioritize bets by customer LTV
   - Weight themes by affected customer revenue

---

**🎉 Phase 5 Deployed! Customer enrichment is now live.**

**Support:** If you encounter issues, check `docs/PHASE5_COMPLETION_SUMMARY.md` for detailed troubleshooting.
