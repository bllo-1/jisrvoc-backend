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

1. **Phase 1 — Foundation.** Replace `mock.py` calls with repositories over
   `db/schema.sql`. Build connectors (HubSpot/Zendesk/Canny|Jira) → normalize →
   identity-resolve. Implement `workers/enrichment.py` (decompose → enrich →
   embed) against an **in-region** LLM + multilingual embeddings.
2. **Phase 2 — Intelligence.** Implement `workers/clustering.py`: weekly
   clustering with **stable theme identity**, vote weighting, trend; bet
   generation; Slack digest + high-urgency alerts.
3. **Phase 3 — Dashboard.** Harden aggregation endpoints; tune Feed filters.
4. **Phase 4 — Loop closure.** Implement the real HubSpot write-back in
   `PATCH /bets/{id}` and append to `writeback_log` (immutable, attributable).
5. **Phase 5 — V2.** Slack ingestion, Chargebee enrichment; revisit
   Kafka/OpenSearch only if scale warrants.

## Compliance reminders (carry over from the blueprint)

- Host and run **all** inference in a Saudi region; keep PII in-Kingdom.
- Store connector credentials only as secrets-manager references (`credentials_ref`).
- Log every HubSpot write-back to `writeback_log` (which bet, which PM, when).
- Preserve raw source text verbatim; AI tags are additive and correctable.
```
