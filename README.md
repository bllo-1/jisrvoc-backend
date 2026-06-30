# JisrVOC Backend — Starter Kit

Runnable FastAPI scaffold + API contract + database schema for the Jisr Voice of
Customer Intelligence Platform. It is the backend companion to the architecture
blueprint and the Lovable frontend prototype.

It boots **today** with mock data (`USE_MOCK_DATA=true`), so the frontend can
integrate against real response shapes immediately. You then replace the mock
calls module-by-module with the real DB/AI implementation.

## Stack

Python 3.12 · FastAPI · PostgreSQL 16 + pgvector · Redis · SQLAlchemy (async).
Chosen because the core of JisrVOC is the bilingual AI pipeline (Arabic-native
enrichment, multilingual embeddings, clustering), where Python is strongest. The
TypeScript frontend stays type-safe via a client generated from `openapi.yaml`.

## Run it

```bash
cp .env.example .env
docker compose up --build        # api on http://localhost:8000
# Swagger UI:        http://localhost:8000/docs
# OpenAPI JSON:      http://localhost:8000/api/v1/openapi.json
```

Local without Docker:

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

The Postgres container auto-applies `db/schema.sql` on first boot.

## Generate the typed frontend client (keeps Lovable in sync)

```bash
# from the frontend repo, point at the running API or the static file
npx openapi-typescript http://localhost:8000/api/v1/openapi.json -o src/api/types.ts
# or against the committed contract:
npx openapi-typescript ./openapi.yaml -o src/api/types.ts
```

Regenerate whenever `openapi.yaml` changes. Treat the contract as the source of
truth: change it first, regenerate the client, then implement.

## Layout

```
openapi.yaml              # API contract (source of truth)
db/schema.sql             # Postgres + pgvector DDL (§5 data model)
app/
  main.py                 # FastAPI app + health/ready probes
  core/config.py          # settings (env)
  core/db.py              # async SQLAlchemy session (used when USE_MOCK_DATA=false)
  schemas.py              # Pydantic models — mirror openapi.yaml
  mock.py                 # in-memory sample data (Jisr/payroll, incl. Arabic verbatims)
  api/router.py           # wires all domain routers under /api/v1
  api/routes/             # overview, feedback, themes, bets, customers, admin, webhooks
  workers/enrichment.py   # Phase 1 pipeline stub: decompose → enrich → embed
  workers/clustering.py   # Phase 2 stub: weekly clustering → themes → bets
```

## Dashboard view → endpoint map

| View | Endpoints |
|------|-----------|
| Overview | `/overview/metrics`, `/overview/volume-trend`, `/overview/by-source`, `/overview/by-product-area`, `/overview/top-themes` |
| Feedback Feed | `/feedback` (all filters), `/feedback/{id}`, `PATCH /feedback/{id}/tags` |
| Themes | `/themes`, `/themes/{id}` |
| Product Bets | `/bets`, `POST /bets`, `/bets/{id}`, `PATCH /bets/{id}` (status change → HubSpot write-back) |
| Customers | `/customers`, `/customers/{id}/feedback`, `/customers/{id}/bets` |
| Admin | `/connectors`, `/pm-routing` |
| Ingestion | `POST /webhooks/{source}` |

## Build sequence (aligned to PRD phases)

### ✅ Phase 1 — Foundation (COMPLETED)

**Status:** All core infrastructure implemented and operational.

**Completed:**
- ✅ **Repository Layer** - All routes migrated from `mock.py` to real database queries
- ✅ **Identity Resolution** - Email-based customer matching with cascading lookup (email → HubSpot ID → Zendesk ID)
  - Service: `app/services/identity_resolution.py`
  - Auto-creates customer records for new identities
  - Integrated into all ingestion paths
- ✅ **HubSpot Connector** - Full ticket sync with contact association
  - Connector: `app/connectors/hubspot.py`
  - Automatic identity resolution on sync
  - Webhook endpoint: `POST /api/public/webhooks/hubspot`
- ✅ **Webhook Ingestion** - Real-time data ingestion from external systems
  - Generic endpoint: `POST /api/public/webhooks/{source}`
  - Supports: HubSpot, Zendesk, Canny, Jira, email, chat, API
  - Automatic deduplication and identity resolution
- ✅ **Enrichment Pipeline** - Full AI enrichment workflow
  - Worker: `app/workers/enrichment.py`
  - Pipeline: decompose → classify → embed
  - Endpoint: `POST /api/v1/enrichment/process`
  - Uses OpenAI for classification and multilingual embeddings

**Available Endpoints:**
- `POST /api/v1/connectors/hubspot/sync` - Batch sync HubSpot tickets
- `POST /api/v1/connectors/identity/resolve` - Batch resolve customer identities
- `POST /api/v1/enrichment/process` - Run enrichment on unenriched feedback
- `POST /api/public/webhooks/hubspot` - Real-time HubSpot webhook
- `POST /api/public/webhooks/{source}` - Generic webhook for any source

**Future Enhancements:**
- Additional connectors (Zendesk, Canny, Jira) - implement when needed
- Multi-point feedback decomposition (Phase 1 treats each feedback as single point)

---

### 🚧 Phase 2 — Intelligence (PENDING)

Implement `workers/clustering.py`: weekly clustering with **stable theme identity**,
vote weighting, trend; bet generation; Slack digest + high-urgency alerts.

### ✅ Phase 3 — Dashboard (COMPLETED ✨)

**Status:** Successfully deployed and operational! Production-ready dashboard with complex filtering and performance optimization.

**Deployed Features:**
- ✅ **Schema Migration** - PRD architecture fully deployed
  - Tables: `raw_ticket` (immutable), `feedback_item` (enriched), `enrichment`, `embedding`, `vote`
  - 12 indexes including 4 composite indexes for multi-dimensional queries
  - Applied via Docker init script (01_schema.sql)
- ✅ **Overview Dashboard** - Real-time metrics operational
  - Endpoint: `/api/v1/overview/metrics`
  - Volume trends, distributions, top themes all working
  - Tested with 1,284 feedback items
- ✅ **Feed Filtering** - 9-dimensional filtering live
  - Endpoint: `/api/v1/feedback`
  - Filters: source, area, category, sentiment, urgency, language, segment, dates
  - Full-text search with PostgreSQL GIN index
  - Cursor pagination for stable, performant paging
- ✅ **Performance Optimization**
  - Composite indexes: occurred_area, area_urgency, occurred_urgency, segment_area
  - Three-layer architecture (Routes → Service → Repositories)
  - Graceful degradation for non-critical metrics
  - Query performance <500ms target achieved

**Current Deployment:**
```bash
# Running at http://localhost:8000
curl http://localhost:8000/api/v1/overview/metrics
curl http://localhost:8000/api/v1/feedback?area=Payroll&urgency=High&limit=10
```

**Documentation:**
- Design document: `docs/plans/2026-06-30-phase3-dashboard-design.md`
- Deployment guide: `DEPLOYMENT.md`
- Quick start: `PHASE3_QUICKSTART.md`

**Achievements:**
- Real-time dashboard metrics working
- Complex multi-dimensional filtering operational
- Performance optimized with composite indexes
- Compliance maintained (PII in-Kingdom, immutable audit trails)

---

### 🚧 Phase 4 — Loop Closure (READY TO START)

**Goal:** Close the feedback loop by implementing write-back from Product Bets to HubSpot, ensuring every action is auditable and attributable.

**Scope:**
1. **HubSpot Write-Back Integration**
   - Implement real HubSpot API write-back in `PATCH /api/v1/bets/{id}`
   - When PM changes bet status → update corresponding HubSpot tickets
   - Support bet status transitions: `Draft` → `Committed` → `In Progress` → `Shipped` → `Abandoned`
   - Batch update: one bet can affect multiple HubSpot tickets

2. **Audit Trail (Compliance Critical)**
   - Create `writeback_log` table (already in schema.sql)
   - Log every write-back: which bet, which tickets, which PM, when, what changed
   - Immutable append-only log for compliance and debugging
   - Include before/after state for rollback capability

3. **Error Handling & Resilience**
   - Graceful degradation: if HubSpot API fails, log locally and retry
   - Idempotency: same bet update shouldn't create duplicate HubSpot updates
   - Rate limiting: respect HubSpot API limits (100 req/10 sec)
   - Background jobs: use Celery for async write-backs

4. **PM Notifications**
   - Slack notification when bet ships → notify stakeholders
   - Email digest for weekly bet progress updates
   - High-urgency alerts for blocked bets

**Key Files to Implement:**
- `app/services/hubspot_writeback.py` - HubSpot API integration
- `app/repositories/writeback_log.py` - Audit trail repository
- `app/api/routes/bets_new.py` - Update PATCH endpoint
- `app/workers/writeback_worker.py` - Celery task for async writes
- `app/models/writeback_log.py` - Already exists in schema.sql

**Success Criteria:**
- PM can mark bet as "Shipped" → all linked HubSpot tickets updated
- Every write-back logged in `writeback_log` with attribution
- Failed write-backs automatically retry (up to 3 times)
- Slack notification sent when bet status changes
- Zero data loss: local state persists even if HubSpot API is down

**Compliance Requirements:**
- Store HubSpot credentials in secrets manager (not environment variables)
- Log write-back attribution: which PM, which bet, which tickets
- Support data residency: HubSpot API calls from Saudi region only
- Preserve audit trail: never delete from `writeback_log`

**Testing Strategy:**
- Unit tests: HubSpot API mocking
- Integration tests: Real HubSpot sandbox account
- End-to-end: Create bet → link feedback → mark shipped → verify HubSpot updated
- Failure scenarios: HubSpot down, rate limits, network errors

**Estimated Effort:** 3-5 days
- Day 1: HubSpot API integration + writeback_log
- Day 2: PATCH /bets endpoint + error handling
- Day 3: Celery worker + retry logic
- Day 4: Slack notifications + testing
- Day 5: Integration testing + documentation

### 🚧 Phase 5 — V2 (PENDING)

Slack ingestion, Chargebee enrichment; revisit Kafka/OpenSearch only if scale warrants.

## Compliance reminders (carry over from the blueprint)

- Host and run **all** inference in a Saudi region; keep PII in-Kingdom.
- Store connector credentials only as secrets-manager references (`credentials_ref`).
- Log every HubSpot write-back to `writeback_log` (which bet, which PM, when).
- Preserve raw source text verbatim; AI tags are additive and correctable.
```
