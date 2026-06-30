# Phase 4: Loop Closure — Design Document

**Author:** JisrVOC Backend Team
**Date:** 2026-06-30
**Status:** Planning → Ready to Implement
**Phase:** 4 of 5

---

## Executive Summary

Phase 4 closes the feedback loop by implementing bi-directional sync between JisrVOC and HubSpot. When a PM marks a Product Bet as "Shipped", all linked HubSpot tickets are automatically updated with resolution details. Every write-back is logged in an immutable audit trail for compliance and debugging.

**Goals:**
- ✅ PM marks bet "Shipped" → HubSpot tickets auto-updated
- ✅ All write-backs logged with attribution (who, when, what)
- ✅ Graceful degradation: HubSpot down → local state persists, retry later
- ✅ Slack notifications for bet status changes
- ✅ Compliance: immutable audit trail, secrets management

**Non-Goals:**
- Real-time sync (async via Celery is acceptable)
- Write-back to other sources (Zendesk, Canny) — Phase 5
- Full bi-directional sync (only bet → HubSpot)

---

## Architecture

### System Context

```
┌─────────────┐         ┌──────────────┐         ┌─────────────┐
│  PM (Web)   │ PATCH   │  JisrVOC API │  Async  │   Celery    │
│  Dashboard  │────────▶│  /bets/{id}  │────────▶│   Worker    │
└─────────────┘         └──────────────┘         └─────────────┘
                              │                          │
                              │ Log                      │ Write
                              ▼                          ▼
                        ┌──────────────┐         ┌─────────────┐
                        │ writeback_   │         │  HubSpot    │
                        │    log       │         │     API     │
                        └──────────────┘         └─────────────┘
                                                        │
                                                        │ Notify
                                                        ▼
                                                 ┌─────────────┐
                                                 │    Slack    │
                                                 └─────────────┘
```

### Data Flow

1. **PM Action**: PM updates bet status via `PATCH /api/v1/bets/{bet_id}`
2. **Validation**: API validates transition (Draft → Committed → In Progress → Shipped)
3. **Database Update**: Update `product_bet` table with new status
4. **Audit Log**: Append to `writeback_log` (who, when, what)
5. **Async Task**: Enqueue Celery task `writeback_to_hubspot.delay(bet_id)`
6. **HubSpot API**: Worker calls HubSpot API to update linked tickets
7. **Retry Logic**: On failure, retry up to 3 times with exponential backoff
8. **Notification**: Send Slack notification on success

---

## Database Schema

### Writeback Log (Already in schema.sql)

```sql
CREATE TABLE writeback_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    bet_id UUID NOT NULL REFERENCES product_bet(id),
    action VARCHAR(50) NOT NULL,  -- 'status_change', 'ticket_link', etc.
    performed_by VARCHAR(255),     -- PM email or system user
    performed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- What changed
    old_state JSONB,               -- {"status": "Draft", "tickets": [...]}
    new_state JSONB,               -- {"status": "Shipped", "tickets": [...]}

    -- HubSpot write-back results
    hubspot_ticket_ids TEXT[],     -- Array of HubSpot ticket IDs updated
    hubspot_success BOOLEAN,       -- Did HubSpot API succeed?
    hubspot_error TEXT,            -- Error message if failed
    retry_count INT DEFAULT 0,     -- Number of retries

    -- Audit trail
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_writeback_bet ON writeback_log(bet_id);
CREATE INDEX idx_writeback_performed_at ON writeback_log(performed_at DESC);
```

**Design Decisions:**
- **Immutable**: Never UPDATE or DELETE rows (append-only)
- **JSONB for state**: Captures full before/after context
- **Attribution**: `performed_by` tracks which PM made the change
- **Retry tracking**: `retry_count` prevents infinite loops

---

## Implementation Plan

### Phase 4.1: HubSpot Write-Back Service (Day 1)

**File:** `app/services/hubspot_writeback.py`

```python
from typing import List, Dict
import httpx
from app.core.config import settings

class HubSpotWritebackService:
    """Service for writing bet status changes back to HubSpot tickets."""

    def __init__(self):
        self.api_key = settings.HUBSPOT_API_KEY  # From secrets manager
        self.base_url = "https://api.hubapi.com"

    async def update_tickets_for_bet(
        self,
        bet_id: str,
        ticket_ids: List[str],
        status: str,
        resolution_notes: str = None
    ) -> Dict[str, bool]:
        """
        Update multiple HubSpot tickets with bet resolution.

        Returns: {ticket_id: success_bool}
        """
        results = {}

        async with httpx.AsyncClient() as client:
            for ticket_id in ticket_ids:
                try:
                    # Update ticket properties
                    response = await client.patch(
                        f"{self.base_url}/crm/v3/objects/tickets/{ticket_id}",
                        headers={"Authorization": f"Bearer {self.api_key}"},
                        json={
                            "properties": {
                                "hs_pipeline_stage": self._map_status_to_stage(status),
                                "product_bet_id": bet_id,
                                "resolution_notes": resolution_notes or ""
                            }
                        },
                        timeout=10.0
                    )
                    results[ticket_id] = response.status_code == 200

                except Exception as e:
                    logger.error(f"Failed to update HubSpot ticket {ticket_id}: {e}")
                    results[ticket_id] = False

        return results

    def _map_status_to_stage(self, status: str) -> str:
        """Map JisrVOC bet status to HubSpot pipeline stage."""
        mapping = {
            "Draft": "open",
            "Committed": "in_progress",
            "In Progress": "in_progress",
            "Shipped": "closed_resolved",
            "Abandoned": "closed_no_action"
        }
        return mapping.get(status, "open")
```

**Testing:**
- Unit tests with mocked HubSpot API
- Integration tests with HubSpot sandbox
- Error handling: network timeout, 429 rate limits, 401 auth errors

---

### Phase 4.2: Writeback Log Repository (Day 1)

**File:** `app/repositories/writeback_log.py`

```python
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.writeback_log import WritebackLog

class WritebackLogRepository:
    """Repository for immutable audit trail of write-backs."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_log_entry(
        self,
        bet_id: str,
        action: str,
        performed_by: str,
        old_state: dict,
        new_state: dict,
        hubspot_ticket_ids: List[str] = None,
        hubspot_success: bool = False,
        hubspot_error: str = None
    ) -> WritebackLog:
        """Create immutable audit log entry."""
        log = WritebackLog(
            bet_id=bet_id,
            action=action,
            performed_by=performed_by,
            old_state=old_state,
            new_state=new_state,
            hubspot_ticket_ids=hubspot_ticket_ids or [],
            hubspot_success=hubspot_success,
            hubspot_error=hubspot_error
        )
        self.db.add(log)
        await self.db.commit()
        return log

    async def get_logs_for_bet(self, bet_id: str) -> List[WritebackLog]:
        """Get all audit logs for a bet (chronological)."""
        result = await self.db.execute(
            select(WritebackLog)
            .where(WritebackLog.bet_id == bet_id)
            .order_by(WritebackLog.performed_at.asc())
        )
        return result.scalars().all()
```

---

### Phase 4.3: Update PATCH /bets Endpoint (Day 2)

**File:** `app/api/routes/bets_new.py`

```python
@router.patch("/{bet_id}", response_model=ProductBetDetail)
async def update_bet_status(
    bet_id: str,
    status_update: BetStatusUpdate,  # Pydantic model
    current_user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Update bet status and trigger HubSpot write-back.

    Workflow:
    1. Validate status transition
    2. Update bet in database
    3. Log to writeback_log
    4. Enqueue Celery task for HubSpot update
    5. Return updated bet
    """
    bet_repo = BetRepository(db)
    writeback_log_repo = WritebackLogRepository(db)

    # 1. Get current bet state
    bet = await bet_repo.get_by_id(bet_id)
    if not bet:
        raise HTTPException(404, "Bet not found")

    old_state = {
        "status": bet.status,
        "tickets": [t.external_id for t in bet.linked_tickets]
    }

    # 2. Validate transition
    if not is_valid_transition(bet.status, status_update.new_status):
        raise HTTPException(400, f"Invalid transition: {bet.status} → {status_update.new_status}")

    # 3. Update bet
    bet.status = status_update.new_status
    await db.commit()

    new_state = {
        "status": bet.status,
        "tickets": [t.external_id for t in bet.linked_tickets]
    }

    # 4. Create audit log
    await writeback_log_repo.create_log_entry(
        bet_id=bet_id,
        action="status_change",
        performed_by=current_user,
        old_state=old_state,
        new_state=new_state,
        hubspot_success=False  # Will be updated by worker
    )

    # 5. Enqueue async task
    ticket_ids = [t.external_id for t in bet.linked_tickets if t.source_type == "HubSpot"]
    if ticket_ids:
        writeback_to_hubspot.delay(
            bet_id=bet_id,
            ticket_ids=ticket_ids,
            status=status_update.new_status,
            resolution_notes=status_update.notes
        )

    return bet
```

**Status Transition Validation:**
```
Draft ──▶ Committed ──▶ In Progress ──▶ Shipped
  │                                        │
  └───────────▶ Abandoned ◀───────────────┘
```

---

### Phase 4.4: Celery Worker (Day 3)

**File:** `app/workers/writeback_worker.py`

```python
from celery import shared_task
from celery.utils.log import get_task_logger
from app.services.hubspot_writeback import HubSpotWritebackService

logger = get_task_logger(__name__)

@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60  # 1 minute
)
def writeback_to_hubspot(
    self,
    bet_id: str,
    ticket_ids: List[str],
    status: str,
    resolution_notes: str = None
):
    """
    Async task to write bet status back to HubSpot.
    Retries up to 3 times on failure.
    """
    try:
        service = HubSpotWritebackService()
        results = await service.update_tickets_for_bet(
            bet_id=bet_id,
            ticket_ids=ticket_ids,
            status=status,
            resolution_notes=resolution_notes
        )

        # Update writeback_log with results
        async with get_db_session() as db:
            log_repo = WritebackLogRepository(db)
            await log_repo.update_hubspot_results(
                bet_id=bet_id,
                hubspot_success=all(results.values()),
                hubspot_error=None if all(results.values()) else "Some tickets failed"
            )

        logger.info(f"✅ Successfully updated {len(ticket_ids)} HubSpot tickets for bet {bet_id}")

        # Send Slack notification
        if status == "Shipped":
            send_slack_notification.delay(bet_id, "shipped")

    except Exception as exc:
        logger.error(f"❌ Failed to update HubSpot for bet {bet_id}: {exc}")

        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)
```

**Celery Configuration:**
```python
# app/core/celery_app.py
from celery import Celery

celery_app = Celery(
    "jisrvoc",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Riyadh",
    enable_utc=True,

    # Rate limiting for HubSpot API
    task_annotations={
        "app.workers.writeback_worker.writeback_to_hubspot": {
            "rate_limit": "100/m"  # 100 requests per minute
        }
    }
)
```

---

### Phase 4.5: Slack Notifications (Day 4)

**File:** `app/workers/slack_notifications.py`

```python
from celery import shared_task
import httpx
from app.core.config import settings

@shared_task
def send_slack_notification(bet_id: str, event_type: str):
    """
    Send Slack notification for bet status changes.

    Events:
    - "shipped": Bet marked as shipped
    - "committed": New bet committed
    - "blocked": Bet blocked (high urgency)
    """
    async with get_db_session() as db:
        bet_repo = BetRepository(db)
        bet = await bet_repo.get_by_id(bet_id)

        if not bet:
            logger.error(f"Bet {bet_id} not found")
            return

        message = _format_slack_message(bet, event_type)

        async with httpx.AsyncClient() as client:
            await client.post(
                settings.SLACK_WEBHOOK_URL,
                json={"text": message},
                timeout=5.0
            )

def _format_slack_message(bet: ProductBet, event_type: str) -> str:
    """Format Slack message based on event type."""
    if event_type == "shipped":
        return (
            f"🎉 *Product Bet Shipped!*\n"
            f"*Title:* {bet.title}\n"
            f"*Owner:* {bet.owner}\n"
            f"*Feedback Items:* {len(bet.linked_feedback)}\n"
            f"*HubSpot Tickets:* {len([t for t in bet.linked_tickets if t.source_type == 'HubSpot'])}\n"
            f"View: {settings.FRONTEND_URL}/bets/{bet.id}"
        )
    elif event_type == "committed":
        return (
            f"🚀 *New Product Bet Committed*\n"
            f"*Title:* {bet.title}\n"
            f"*Owner:* {bet.owner}\n"
            f"*Priority:* {bet.priority}\n"
            f"View: {settings.FRONTEND_URL}/bets/{bet.id}"
        )
    else:
        return f"Bet {bet.title} updated: {event_type}"
```

---

## Error Handling

### Failure Scenarios

| Scenario | Handling |
|----------|----------|
| HubSpot API down | Log locally, retry 3x with exponential backoff, alert on 3rd failure |
| Rate limit (429) | Back off exponentially, respect Retry-After header |
| Auth failure (401) | Alert immediately, check credentials in secrets manager |
| Network timeout | Retry immediately (may be transient) |
| Invalid ticket ID | Log error, continue with remaining tickets |
| Partial success | Log which tickets succeeded/failed, retry only failed ones |

### Idempotency

**Problem:** What if the same bet status change is processed twice?

**Solution:**
1. Check `writeback_log` for existing successful entry
2. If found with `hubspot_success=true` → skip write-back
3. If found with `hubspot_success=false` → retry

```python
async def is_already_written_back(bet_id: str, new_status: str) -> bool:
    """Check if this status change was already written back successfully."""
    result = await db.execute(
        select(WritebackLog)
        .where(
            WritebackLog.bet_id == bet_id,
            WritebackLog.new_state["status"].astext == new_status,
            WritebackLog.hubspot_success == True
        )
        .order_by(WritebackLog.performed_at.desc())
        .limit(1)
    )
    return result.scalar() is not None
```

---

## Testing Strategy

### Unit Tests

```python
# tests/services/test_hubspot_writeback.py
@pytest.mark.asyncio
async def test_update_tickets_for_bet_success(mock_httpx):
    """Test successful HubSpot ticket update."""
    mock_httpx.patch.return_value = MockResponse(200)

    service = HubSpotWritebackService()
    results = await service.update_tickets_for_bet(
        bet_id="bet-123",
        ticket_ids=["HS-1", "HS-2"],
        status="Shipped",
        resolution_notes="Fixed in v2.3"
    )

    assert results == {"HS-1": True, "HS-2": True}
    assert mock_httpx.patch.call_count == 2

@pytest.mark.asyncio
async def test_update_tickets_handles_rate_limit(mock_httpx):
    """Test rate limit handling."""
    mock_httpx.patch.return_value = MockResponse(429, headers={"Retry-After": "60"})

    service = HubSpotWritebackService()
    with pytest.raises(RateLimitError):
        await service.update_tickets_for_bet(
            bet_id="bet-123",
            ticket_ids=["HS-1"],
            status="Shipped"
        )
```

### Integration Tests

```python
# tests/integration/test_bet_writeback_flow.py
@pytest.mark.integration
async def test_full_writeback_flow(test_db, hubspot_sandbox):
    """Test complete flow: PATCH bet → Celery task → HubSpot API."""
    # 1. Create bet with linked tickets
    bet = await create_test_bet(test_db, linked_tickets=["HS-TEST-1"])

    # 2. Update bet status
    response = await client.patch(
        f"/api/v1/bets/{bet.id}",
        json={"new_status": "Shipped", "notes": "Test release"}
    )
    assert response.status_code == 200

    # 3. Wait for Celery task
    await asyncio.sleep(2)

    # 4. Verify HubSpot ticket updated
    ticket = await hubspot_sandbox.get_ticket("HS-TEST-1")
    assert ticket.properties["hs_pipeline_stage"] == "closed_resolved"

    # 5. Verify audit log
    logs = await writeback_log_repo.get_logs_for_bet(bet.id)
    assert len(logs) == 1
    assert logs[0].hubspot_success == True
```

---

## Deployment

### Environment Variables

```bash
# .env
HUBSPOT_API_KEY=pat-na1-...  # From secrets manager
HUBSPOT_RATE_LIMIT=100       # Requests per 10 seconds
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0
```

### Celery Worker Deployment

```yaml
# docker-compose.yml (already exists)
celery-worker:
  build: .
  command: celery -A app.core.celery_app worker --loglevel=info --concurrency=2
  env_file: .env
  depends_on:
    - db
    - redis
```

**Monitoring:**
- Celery Flower dashboard: `http://localhost:5555`
- Dead letter queue for failed tasks after 3 retries
- Sentry for error tracking

---

## Security & Compliance

### Credentials Management

**Do NOT store HubSpot API keys in environment variables in production.**

Use AWS Secrets Manager:
```python
import boto3

def get_hubspot_api_key() -> str:
    """Fetch HubSpot API key from AWS Secrets Manager."""
    client = boto3.client("secretsmanager", region_name="me-south-1")
    response = client.get_secret_value(SecretId="prod/jisrvoc/hubspot-api-key")
    return response["SecretString"]
```

### Audit Trail Requirements

1. **Immutability**: Never UPDATE or DELETE from `writeback_log`
2. **Attribution**: Always log `performed_by` (PM email)
3. **Completeness**: Log both successes and failures
4. **Retention**: Keep logs for 7 years (compliance requirement)

### Data Residency

- Run all HubSpot API calls from Saudi region (AWS me-south-1)
- Do NOT proxy through third-party services
- Log all API calls with timestamps for compliance audits

---

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Write-back success rate | >99% | `writeback_log.hubspot_success = true` / total |
| Average latency (bet update → HubSpot) | <5 seconds | Celery task duration |
| Retry rate | <5% | `writeback_log.retry_count > 0` / total |
| Failed after 3 retries | <0.1% | Dead letter queue size |
| Slack notification delivery | >99.5% | Webhook success rate |

---

## Future Enhancements (Phase 5+)

- Write-back to Zendesk, Canny, Jira
- Bi-directional sync (HubSpot → JisrVOC)
- Real-time sync via webhooks (instead of polling)
- Batch write-backs for multiple bets
- Customer-facing status page (show bet progress)

---

## Appendix: API Contract

### PATCH /api/v1/bets/{bet_id}

**Request:**
```json
{
  "new_status": "Shipped",
  "notes": "Fixed in v2.3.0 release",
  "performed_by": "pm@jisr.com"
}
```

**Response:**
```json
{
  "id": "bet-123",
  "title": "Fix payroll timeout for large companies",
  "status": "Shipped",
  "owner": "pm@jisr.com",
  "linkedFeedback": [...],
  "linkedTickets": [
    {"source": "HubSpot", "externalId": "HS-1", "updated": true},
    {"source": "HubSpot", "externalId": "HS-2", "updated": true}
  ],
  "updatedAt": "2026-06-30T14:30:00Z"
}
```

**Error Responses:**
- `400`: Invalid status transition
- `404`: Bet not found
- `500`: HubSpot API error (logged, will retry)

---

## References

- [HubSpot CRM API Documentation](https://developers.hubspot.com/docs/api/crm/tickets)
- [Celery Best Practices](https://docs.celeryproject.org/en/stable/userguide/tasks.html)
- Phase 3 Design: `docs/plans/2026-06-30-phase3-dashboard-design.md`
- Schema: `db/schema.sql` (writeback_log table)
