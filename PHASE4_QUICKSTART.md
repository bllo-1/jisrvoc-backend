# Phase 4 Quick Start Guide

## 🎯 Phase 4 Goal

Close the feedback loop: When a PM marks a Product Bet as "Shipped", automatically update all linked HubSpot tickets with resolution details. Every action is logged for compliance.

**Current Status:** ✅ Phase 3 Complete → Ready to start Phase 4

---

## 📋 Implementation Checklist

### Day 1: Foundation (4-6 hours)

- [ ] **Create `app/models/writeback_log.py`**
  - SQLAlchemy model for `writeback_log` table
  - Fields: bet_id, action, performed_by, old_state, new_state, hubspot_results
  - Immutable append-only model (no UPDATE/DELETE)

- [ ] **Create `app/repositories/writeback_log.py`**
  - `create_log_entry()` - Append audit log
  - `get_logs_for_bet()` - Query logs by bet_id
  - `update_hubspot_results()` - Update log after HubSpot call

- [ ] **Create `app/services/hubspot_writeback.py`**
  - `update_tickets_for_bet()` - Call HubSpot API to update tickets
  - `_map_status_to_stage()` - Map JisrVOC status → HubSpot stage
  - Error handling: rate limits, auth failures, network errors

- [ ] **Write unit tests**
  - Mock HubSpot API responses
  - Test status mapping (Draft → open, Shipped → closed_resolved)
  - Test error scenarios (429, 401, timeout)

### Day 2: API Endpoint (4-6 hours)

- [ ] **Update `app/api/routes/bets_new.py`**
  - Modify `PATCH /bets/{bet_id}` to accept status updates
  - Validate status transitions (Draft → Committed → In Progress → Shipped)
  - Log to `writeback_log` before async task
  - Enqueue Celery task `writeback_to_hubspot.delay()`

- [ ] **Create Pydantic models**
  - `BetStatusUpdate` - Request schema for PATCH endpoint
  - `WritebackLogResponse` - Response schema for audit logs

- [ ] **Test endpoint**
  - Unit test with mocked Celery
  - Integration test: PATCH → verify database update → verify log created
  - Test invalid transitions (Shipped → Draft should fail)

### Day 3: Async Worker (4-6 hours)

- [ ] **Create `app/workers/writeback_worker.py`**
  - `@shared_task writeback_to_hubspot()` - Celery task
  - Call HubSpotWritebackService
  - Update writeback_log with results
  - Retry up to 3 times on failure (exponential backoff)

- [ ] **Configure Celery**
  - Rate limiting: 100 requests/minute for HubSpot API
  - Task serializer: JSON
  - Timezone: Asia/Riyadh

- [ ] **Test worker**
  - Integration test with HubSpot sandbox account
  - Test retry logic: simulate API failure
  - Test idempotency: same bet update twice → HubSpot called once

### Day 4: Notifications (3-4 hours)

- [ ] **Create `app/workers/slack_notifications.py`**
  - `send_slack_notification()` - Post to Slack webhook
  - Format messages for different events (shipped, committed, blocked)
  - Include bet title, owner, linked tickets count

- [ ] **Integrate with writeback worker**
  - On successful write-back → send Slack notification
  - Only for "Shipped" status (not Draft/Committed)

- [ ] **Test notifications**
  - Mock Slack webhook
  - Verify message formatting
  - Test failure handling (Slack API down)

### Day 5: Integration & Documentation (4-6 hours)

- [ ] **End-to-end testing**
  - Create test bet with linked HubSpot tickets
  - PATCH to "Shipped" status
  - Verify: bet updated, log created, Celery task ran, HubSpot updated, Slack sent
  - Test failure recovery: HubSpot down → retry → eventual success

- [ ] **Security review**
  - HubSpot API key from secrets manager (not env vars)
  - All write-backs logged with attribution
  - Audit trail immutable (no UPDATE/DELETE)

- [ ] **Documentation**
  - Update API docs: PATCH /bets endpoint
  - Deployment guide: Celery worker setup
  - Troubleshooting: common errors and fixes

---

## 🚀 Getting Started

### 1. Review Phase 4 Design Doc

```bash
cat docs/plans/2026-06-30-phase4-loop-closure-plan.md
```

**Key sections to read:**
- Architecture diagram (PM → API → Celery → HubSpot)
- Database schema (writeback_log table)
- Error handling strategies
- Testing approach

### 2. Check Current Schema

```bash
# Verify writeback_log table exists
docker compose exec db psql -U jisrvoc -d jisrvoc -c "\d writeback_log"
```

Expected output:
```
Table "public.writeback_log"
     Column      |           Type           | Nullable
-----------------+--------------------------+----------
 id              | uuid                     | not null
 bet_id          | uuid                     | not null
 action          | character varying(50)    | not null
 performed_by    | character varying(255)   |
 old_state       | jsonb                    |
 new_state       | jsonb                    |
 ...
```

### 3. Set Up Environment

```bash
# Add HubSpot credentials to .env
echo "HUBSPOT_API_KEY=your-api-key-here" >> .env
echo "SLACK_WEBHOOK_URL=https://hooks.slack.com/services/..." >> .env

# Restart API to load new env vars
docker compose restart api
```

### 4. Start Celery Worker

```bash
# Celery worker is already in docker-compose.yml
docker compose up -d celery-worker

# Verify worker is running
docker compose logs celery-worker

# Should see:
# [2026-06-30 12:00:00,000: INFO/MainProcess] Connected to redis://redis:6379/0
# [2026-06-30 12:00:00,000: INFO/MainProcess] mingle: all alone
```

### 5. Create First File

```bash
# Start with the model
touch app/models/writeback_log.py
```

Open `app/models/writeback_log.py` and implement the SQLAlchemy model (see design doc for full code).

---

## 🧪 Testing Strategy

### Unit Tests (Fast, isolated)

```bash
# Run unit tests for HubSpot service
pytest tests/services/test_hubspot_writeback.py -v

# Run unit tests for writeback worker
pytest tests/workers/test_writeback_worker.py -v
```

### Integration Tests (Requires DB + Redis)

```bash
# Run integration tests
pytest tests/integration/test_bet_writeback_flow.py -v --integration

# This will:
# 1. Create test bet in database
# 2. PATCH /bets/{id} to change status
# 3. Wait for Celery task
# 4. Verify HubSpot ticket updated (uses sandbox)
# 5. Verify audit log created
```

### Manual Testing

```bash
# 1. Create test bet
curl -X POST http://localhost:8000/api/v1/bets \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Test Bet",
    "description": "Testing write-back",
    "status": "Draft",
    "linkedTickets": [{"source": "HubSpot", "externalId": "HS-TEST-1"}]
  }'

# 2. Update bet status
curl -X PATCH http://localhost:8000/api/v1/bets/{bet_id} \
  -H "Content-Type: application/json" \
  -d '{
    "new_status": "Shipped",
    "notes": "Fixed in test release"
  }'

# 3. Check writeback log
curl http://localhost:8000/api/v1/bets/{bet_id}/writeback-logs

# 4. Verify HubSpot ticket
# (Check HubSpot sandbox manually or via API)
```

---

## 📊 Implementation Progress Tracking

Use this checklist as you implement:

```markdown
## Phase 4 Progress

### Foundation ✅/🚧/⏳
- [ ] writeback_log model
- [ ] writeback_log repository
- [ ] hubspot_writeback service
- [ ] Unit tests

### API Endpoint ✅/🚧/⏳
- [ ] PATCH /bets endpoint updated
- [ ] Status transition validation
- [ ] Pydantic models
- [ ] Integration tests

### Async Worker ✅/🚧/⏳
- [ ] writeback_worker Celery task
- [ ] Retry logic with backoff
- [ ] Celery configuration
- [ ] Integration tests with sandbox

### Notifications ✅/🚧/⏳
- [ ] Slack notification worker
- [ ] Message formatting
- [ ] Integration with writeback

### Testing & Docs ✅/🚧/⏳
- [ ] End-to-end tests
- [ ] Security review
- [ ] API documentation
- [ ] Deployment guide

Legend: ✅ Done | 🚧 In Progress | ⏳ Not Started
```

---

## 🐛 Common Issues

### Issue 1: HubSpot API 401 Unauthorized

**Symptom:** `hubspot_error: "401 Unauthorized"`

**Fix:**
```bash
# Check API key is set
docker compose exec api env | grep HUBSPOT

# If missing, add to .env and restart
echo "HUBSPOT_API_KEY=pat-na1-..." >> .env
docker compose restart api celery-worker
```

### Issue 2: Celery Task Not Running

**Symptom:** Bet updated but HubSpot not updated

**Fix:**
```bash
# Check Celery worker logs
docker compose logs celery-worker --tail=100

# Verify Redis connection
docker compose exec celery-worker python -c "
from app.core.celery_app import celery_app
print(celery_app.connection().as_uri())
"

# Restart worker
docker compose restart celery-worker
```

### Issue 3: Rate Limit Errors

**Symptom:** `hubspot_error: "429 Too Many Requests"`

**Fix:**
```python
# Update Celery rate limit in app/core/celery_app.py
task_annotations={
    "app.workers.writeback_worker.writeback_to_hubspot": {
        "rate_limit": "50/m"  # Reduce from 100/m to 50/m
    }
}
```

### Issue 4: Writeback Log Not Created

**Symptom:** Bet updated but no audit log

**Fix:**
```bash
# Check database connection
docker compose exec db psql -U jisrvoc -d jisrvoc -c "SELECT COUNT(*) FROM writeback_log;"

# Check for errors in API logs
docker compose logs api --tail=100 | grep ERROR
```

---

## 📚 Key Files Reference

| File | Purpose | Lines |
|------|---------|-------|
| `docs/plans/2026-06-30-phase4-loop-closure-plan.md` | Comprehensive design doc | 500+ |
| `app/models/writeback_log.py` | SQLAlchemy model | ~50 |
| `app/repositories/writeback_log.py` | Data access layer | ~100 |
| `app/services/hubspot_writeback.py` | HubSpot API integration | ~150 |
| `app/api/routes/bets_new.py` | PATCH endpoint | ~200 |
| `app/workers/writeback_worker.py` | Celery task | ~100 |
| `app/workers/slack_notifications.py` | Slack webhooks | ~80 |
| `tests/integration/test_bet_writeback_flow.py` | End-to-end tests | ~200 |

---

## 🎯 Success Criteria

Phase 4 is complete when:

1. ✅ PM can mark bet "Shipped" via API
2. ✅ All linked HubSpot tickets automatically updated
3. ✅ Every action logged in `writeback_log` with attribution
4. ✅ Failed write-backs retry up to 3 times
5. ✅ Slack notification sent on successful ship
6. ✅ >99% write-back success rate
7. ✅ Average latency <5 seconds (bet update → HubSpot)
8. ✅ All integration tests passing

**Test Command:**
```bash
pytest tests/ -v --integration --cov=app --cov-report=term-missing
```

**Expected Coverage:** >90% for Phase 4 code

---

## 🚀 Ready to Start?

1. Read the full design doc: `docs/plans/2026-06-30-phase4-loop-closure-plan.md`
2. Start with Day 1: Create `writeback_log` model and repository
3. Follow the 5-day implementation plan above
4. Test incrementally (unit → integration → end-to-end)
5. Deploy with confidence!

**Estimated Time:** 3-5 days (20-30 hours)

**Next Phase:** Phase 5 — V2 (Slack ingestion, Chargebee enrichment, scale optimizations)
