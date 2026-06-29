# JisrVOC Backend — Implementation Plan

Execution plan for building the JisrVOC backend, written to be picked up directly
in Claude Code. The repo already contains a runnable FastAPI scaffold
(`app/`), the API contract (`openapi.yaml`), and the database schema
(`db/schema.sql`). This plan sequences turning that scaffold into the real system.

**Golden rule — treat `openapi.yaml` as the source of truth.** Change the contract
first, regenerate the frontend client, then implement. Keep `app/schemas.py` in
sync with it.

---

## Phase 0 — Decisions to lock before coding (do not skip)

- [ ] Cloud + region: **GCP Dammam** (in-region Vertex AI) vs **AWS Riyadh**.
- [ ] In-region LLM + multilingual embedding model; run a small Arabic-quality spike.
- [ ] HubSpot field mapping: exact properties / pipeline / stages for feedback tickets.
- [ ] Canny vs Jira: which is live at build time + migration timeline.
- [ ] Zendesk↔HubSpot match key (domain or email→account).
- [ ] Write-back mechanism: Note vs custom property (validate with CS/Sales).

> These are facts only Jisr can supply. Capture answers in this file as you get them.

---

## MVP first — deploy the scaffold on Railway (synthetic data only)

Goal: a live API the Lovable frontend talks to, with zero production infra.

**Residency note:** Railway is not in-Kingdom. MVP/demo with mock data ONLY. Do not
ingest real customer PII on Railway — move to the chosen Saudi region before real data.

- [ ] Make 3 Railway-compat tweaks:
  - [ ] Bind uvicorn to Railway's injected `$PORT` (Dockerfile currently hardcodes 8000).
  - [ ] Normalize `DATABASE_URL` (`postgresql://` → `postgresql+asyncpg://`) at startup in `app/core/config.py`.
  - [ ] Keep pgvector optional for now (clustering is Phase 2).
- [ ] Push repo to GitHub → Railway → Deploy from repo (auto-detects Dockerfile).
- [ ] Set `USE_MOCK_DATA=true` → instantly live, no DB required.
- [ ] Point the Lovable frontend at the Railway URL; regenerate its typed client from
      `/api/v1/openapi.json`.
- [ ] (When Phase 1 starts) add Railway Postgres + Redis, flip `USE_MOCK_DATA=false`.

---

## Phase 1 — Foundation

Goal: feedback flows in, is enriched, and lands in the DB. This is the bulk of the work.

**Infra & data layer**
- [ ] Terraform: Postgres+pgvector, Redis, queue (SQS/Pub-Sub), secrets manager — in-region.
- [ ] Apply `db/schema.sql` as the first migration (introduce Alembic).
- [ ] Build the repository layer; replace each `app/mock.py` call with a DB query, route by route.

**Connectors** (one source end-to-end first, recommended: HubSpot)
- [ ] HubSpot connector: webhook + scheduled poll; idempotent on `(source, external_id)`.
- [ ] Zendesk connector.
- [ ] Canny/Jira connector behind a thin source-adapter interface; preserve vote counts.
- [ ] Normalization → common `raw_ticket`; identity resolution → match to HubSpot `customer`.

**AI enrichment pipeline** (`app/workers/enrichment.py`)
- [ ] `decompose()` — split multi-point tickets into cards; retain parent ref (PRD 6.3).
- [ ] `enrich()` — category, area, sentiment, urgency, language, English summary (PRD 6.1/6.2).
- [ ] `embed()` — multilingual vector (dim must match `db/schema.sql` `vector(N)`).
- [ ] Persist model/version + confidence to `enrichment`; quarantine low-confidence outputs.
- [ ] Stand up the **AR/EN eval harness now** — it gates the bilingual capability.

**Auth**
- [ ] Real SSO/OIDC token validation; RBAC by role (pm / director / cs_sales / admin).

**Acceptance:** a real HubSpot ticket ingests → decomposes → enriches → appears in
`GET /feedback` from the DB (not mock).

---

## Phase 2 — Intelligence layer

Goal: items become themes and bets. (`app/workers/clustering.py`)

- [ ] Weekly clustering (embeddings → HDBSCAN/agglomerative).
- [ ] **Stable theme identity** via centroid match against prior themes.
- [ ] Compute trend, vote weight, segment breakdown, representative verbatims.
- [ ] Draft product-bet generation from top themes.
- [ ] Slack weekly digest (Sunday, Riyadh time) + real-time high-urgency alerts (routed by area).
- [ ] Durable scheduler/workflow (Temporal or scheduled job) with resume-on-failure.

**Acceptance:** a weekly run produces named themes that persist week-to-week and at
least one draft bet traceable to its evidence.

---

## Phase 3 — Dashboard integration

- [ ] Harden + performance-tune all aggregation endpoints behind the Lovable UI.
- [ ] Lock the contract; frontend client generated from `openapi.yaml`.
- [ ] RTL-safe verbatim delivery; Feed filter/index tuning.

---

## Phase 4 — Loop closure

- [ ] Real HubSpot write-back on bet status change (`PATCH /bets/{id}`), targeting every
      evidence ticket (parent, even for split items).
- [ ] Append every write-back to `writeback_log` (immutable, attributable).
- [ ] Validate with CS/Sales that updates appear correctly in HubSpot.

---

## Phase 5 — V2

- [ ] Slack ingestion (post-migration), Chargebee enrichment, additional sources.
- [ ] Revisit Kafka/OpenSearch only if scale demands it.

---

## Cross-cutting (every phase)

- **Compliance:** all storage + inference in-Kingdom for real data; credentials as
  secrets-manager refs only; encryption at rest/in transit; full audit logging; retention policy.
- **Observability:** structured logs (no PII), queue-depth/enrichment-success metrics,
  OpenTelemetry tracing, dead-letter queue + retries with backoff, Sentry, sync-health alarms.
- **CI/CD:** GitHub Actions → image → Terraform-provisioned dev/staging/prod; gated migrations.

---

## Suggested milestone order

1. Phase 0 decisions
2. Railway MVP live (mock mode) + frontend integration
3. Infra + schema + HubSpot connector end-to-end
4. Enrichment pipeline + AR/EN eval harness
5. Remaining connectors
6. Clustering + bets
7. Digest/alerts
8. Dashboard hardening
9. Loop closure

**Critical-path risks to front-load:** the in-region LLM decision and Arabic
clustering quality. Prove both early.

---

## Repo map (what already exists)

| File | Purpose |
|------|---------|
| `openapi.yaml` | API contract — source of truth |
| `db/schema.sql` | Postgres + pgvector DDL (§5 data model) |
| `app/main.py` | FastAPI app + health/ready probes |
| `app/schemas.py` | Pydantic models (mirror the contract) |
| `app/mock.py` | In-memory sample data — replace with repositories |
| `app/api/routes/` | Endpoints per dashboard view |
| `app/workers/enrichment.py` | Phase 1 pipeline stub |
| `app/workers/clustering.py` | Phase 2 clustering stub |
| `README.md` | Run + client-generation instructions |
