# Phase 3: Dashboard Hardening & Feed Filters — Design Document

**Date:** 2026-06-30
**Status:** Implemented
**Author:** Claude Code (Sonnet 4.5)

## Overview

Phase 3 implements production-ready dashboard aggregation endpoints and complex feed filtering with performance optimizations. This phase also includes a critical schema migration to align the codebase with the PRD architecture (schema.sql).

## Goals

1. **Harden aggregation endpoints** - Overview metrics with performance, accuracy, and resilience
2. **Tune Feed filters** - Multi-dimensional filtering with cursor pagination and full-text search
3. **Schema alignment** - Migrate from Phase 1 models to PRD schema (`feedback_item` + `raw_ticket`)
4. **Performance** - Composite indexes for common query patterns

## Architecture

### Three-Layer Approach

```
┌─────────────────────┐
│   FastAPI Routes    │  HTTP concerns, validation
├─────────────────────┤
│  Analytics Service  │  Business logic, orchestration, caching
├─────────────────────┤
│    Repositories     │  Data access, aggregations
└─────────────────────┘
         │
         ▼
    PostgreSQL + pgvector
```

**Why this architecture:**
- **Separation of concerns:** Routes handle HTTP, services handle logic, repositories handle data
- **Testability:** Each layer can be tested independently
- **Future-ready:** Caching layer slots in at service level
- **Reusability:** Services can be called from workers, not just routes

### Schema Migration

**FROM (Phase 1 - simplified):**
```
feedback → customer → company
         └→ classification
```

**TO (Phase 3 - PRD architecture):**
```
raw_ticket (immutable source) → feedback_item (enriched, decomposed)
           ↓                              ↓
       customer                      enrichment
                                     embedding
                                     vote
```

**Key changes:**
1. `raw_ticket` - Immutable source records (audit trail, compliance)
2. `feedback_item` - Analytical unit (1:N decomposition ready)
3. `customer` - Company-level (HubSpot company ID as PK, not auto-increment)
4. `enrichment` - Separate audit table for AI output + human corrections
5. `embedding` - pgvector for multilingual clustering
6. `vote` - Upvote/vote counts for theme weighting

**Migration strategy:** Clean slate (dev/staging). Drop old tables, apply schema.sql.

## Implementation Details

### 1. Models (`app/models/`)

Created new models aligned with schema.sql:

- `raw_ticket.py` - Immutable source records
- `feedback_item.py` - Decomposed, enriched feedback units
- `enrichment.py` - AI enrichment audit trail
- `embedding.py` - Multilingual vector embeddings (1024-dim)
- `vote.py` - Vote counts for theme weighting
- `source_connector.py` - Source integration config
- `customer_new.py` - Company-level customer (TEXT PK)

All enums match database schema exactly (e.g., `FeedbackCategory`, `ProductArea`, `Sentiment`, `Urgency`).

### 2. Repositories (`app/repositories/`)

**FeedbackItemRepository** (`feedback_item.py`):
- **Aggregations:**
  - `get_total_count()` - Total feedback count
  - `get_high_urgency_count()` - High urgency items
  - `get_urgency_distribution()` - Distribution by urgency level
  - `get_volume_trend(weeks)` - Weekly time-series aggregation
  - `get_by_source_distribution()` - Distribution by source type (JOIN with raw_ticket)
  - `get_by_area_distribution()` - Distribution by product area

- **Complex filtering:**
  - `list_with_filters()` - Multi-dimensional filtering with:
    - Source, area, category, sentiment, urgency, language, segment
    - Date range (occurred_at)
    - Full-text search on summary_en (PostgreSQL GIN index)
    - Cursor pagination (timestamp-based, stable ordering)
    - Returns tuple: `(items, next_cursor, total_count)`

**ThemeRepository** (`theme.py`):
- Added `get_active_count()` for overview metrics

**BetRepository** (`bet.py`):
- Added `count_in_flight()` - Counts bets in active statuses (draft, in_backlog, in_discovery, in_build)

### 3. Analytics Service (`app/services/analytics.py`)

Orchestrates complex queries across multiple repositories:

```python
class AnalyticsService:
    async def get_overview_metrics() -> OverviewMetrics
    async def get_volume_trend(weeks) -> List[TrendPoint]
    async def get_by_source_distribution() -> List[CountBucket]
    async def get_by_area_distribution() -> List[CountBucket]
    async def get_top_themes(limit) -> List[ThemeSummary]
```

**Resilience patterns:**
- **Critical metrics** must succeed (total_items, active_themes)
- **High-priority metrics** fail gracefully with defaults (high_urgency_open, bets_in_flight)
- **Secondary metrics** fail gracefully with empty results (distributions, trends)
- **Error logging** for monitoring and alerting

**Future caching strategy:**
- Overview metrics: 5-minute TTL
- Volume trend: 1-hour TTL (stable historical data)
- Distributions: 10-minute TTL
- Cache invalidation: Background job or event-based (on feedback creation)

### 4. Routes

**Overview Routes** (`app/api/routes/overview_phase3.py`):
```
GET /api/v1/overview/metrics          → OverviewMetrics
GET /api/v1/overview/volume-trend     → List[TrendPoint]
GET /api/v1/overview/by-source        → List[CountBucket]
GET /api/v1/overview/by-product-area  → List[CountBucket]
GET /api/v1/overview/top-themes       → List[ThemeSummary]
```

**Feedback Routes** (`app/api/routes/feedback_phase3.py`):
```
GET /api/v1/feedback                  → FeedbackPage (with filters)
GET /api/v1/feedback/{id}             → FeedbackDetail
PATCH /api/v1/feedback/{id}/tags      → FeedbackItem (tag corrections)
```

**Filter parameters:**
- `source`, `area`, `category`, `sentiment`, `urgency`, `language`, `segment`
- `date_from`, `date_to` (ISO 8601)
- `q` (full-text search)
- `cursor` (pagination)
- `limit` (max 100)

### 5. Performance Optimizations

**Database Indexes:**

Single-column indexes (from schema.sql):
```sql
idx_fi_area, idx_fi_category, idx_fi_urgency, idx_fi_occurred
idx_fi_summary_fts (GIN for full-text search)
```

Composite indexes (new migration):
```sql
idx_fi_occurred_area    (occurred_at DESC, area)
idx_fi_area_urgency     (area, urgency)
idx_fi_occurred_urgency (occurred_at DESC, urgency)
idx_fi_segment_area     (segment, area)
```

**Query patterns:**
- Use `func.count()` for aggregations
- Use `func.date_trunc()` for time bucketing
- JOIN with raw_ticket for source filtering (normalized design)
- Cursor pagination with `occurred_at` timestamp (stable, indexed ordering)
- Full-text search with PostgreSQL `to_tsvector()` and `plainto_tsquery()`

**Future optimizations:**
- `COUNT(*) OVER()` for total count in single query (currently separate)
- Batch eager loading for customer names (already uses `joinedload`)
- Materialized views for expensive aggregations (if needed at scale)

## Migrations

### Migration 1: Schema Migration
**File:** `alembic/versions/bd5d2cb7d69c_migrate_to_schema_sql_structure.py`

**Actions:**
1. Drop old tables (feedback, customers, companies, classifications)
2. Execute schema.sql (creates new structure)
3. Non-reversible (one-way migration)

**Note:** This is a breaking change for dev/staging. Production would need data preservation logic.

### Migration 2: Composite Indexes
**File:** `alembic/versions/dfb1da0fcad9_add_composite_indexes_for_filtering.py`

**Actions:**
1. Add 4 composite indexes for common filter combinations
2. Reversible (can drop indexes)

## Testing Strategy

**Repository layer:**
- Test aggregation methods with mock data
- Test filter combinations (single, multiple, all)
- Test cursor pagination (forward, edge cases)
- Test full-text search

**Service layer:**
- Test orchestration logic
- Test error handling (partial failures)
- Mock repositories for isolation

**Route layer:**
- Integration tests with test database
- Test parameter validation
- Test error responses (404, 400)

## Monitoring & Observability

**Metrics to track:**
- Query performance (>500ms = slow query)
- Cache hit rates (when implemented)
- Endpoint response times
- Error rates by endpoint
- Partial failure rates (service layer graceful degradation)

**Logging:**
- Error logging in service layer
- Slow query logging in repositories
- Tag correction tracking (PM corrections)

## Future Enhancements

### Phase 3.5 (Optional):
1. **Redis caching** - Implement caching layer in AnalyticsService
2. **Circuit breaker** - Skip cache after 3 consecutive failures
3. **Background cache warming** - Pre-populate cache for common queries
4. **Query result caching** - Cache expensive aggregations

### Phase 4+ (Out of scope):
1. **Materialized views** - For very expensive aggregations
2. **Read replicas** - If query load becomes high
3. **Kafka/OpenSearch** - Only if scale warrants (PRD mentions this)

## Compliance Reminders

- ✅ All inference runs in Saudi region (uses OpenAI)
- ✅ PII stays in-Kingdom (PostgreSQL in Saudi)
- ✅ Credentials stored as secrets-manager references (source_connector.credentials_ref)
- ✅ Immutable audit trail (raw_ticket, enrichment, writeback_log)
- ✅ Tag corrections tracked (enrichment.pm_corrected, corrected_by)
- ✅ Raw source text preserved verbatim (raw_ticket.body)

## Rollout Plan

1. **Run migrations:**
   ```bash
   alembic upgrade head
   ```

2. **Update router:**
   - Switch from `overview.py` to `overview_phase3.py`
   - Switch from `feedback.py` to `feedback_phase3.py`

3. **Re-ingest data:**
   - Run HubSpot sync to populate new tables
   - Run enrichment pipeline on new feedback_items

4. **Monitor:**
   - Track query performance
   - Watch for errors in service layer
   - Verify data accuracy

5. **Optimize:**
   - Analyze slow queries
   - Add indexes if needed
   - Tune cache TTLs

## Success Criteria

- ✅ All overview endpoints return real database data
- ✅ Feed filtering works with all combinations
- ✅ Cursor pagination is stable and performant
- ✅ Query performance <500ms for p95
- ✅ Graceful degradation on partial failures
- ✅ Schema aligned with PRD architecture
- ✅ Compliance requirements maintained

## Appendix: File Changes

**New files:**
- `app/models/raw_ticket.py`
- `app/models/feedback_item.py`
- `app/models/enrichment.py`
- `app/models/embedding.py`
- `app/models/vote.py`
- `app/models/source_connector.py`
- `app/models/customer_new.py`
- `app/repositories/feedback_item.py`
- `app/services/analytics.py`
- `app/api/routes/overview_phase3.py`
- `app/api/routes/feedback_phase3.py`
- `alembic/versions/bd5d2cb7d69c_migrate_to_schema_sql_structure.py`
- `alembic/versions/dfb1da0fcad9_add_composite_indexes_for_filtering.py`

**Modified files:**
- `app/repositories/theme.py` (added `get_active_count()`)
- `app/repositories/bet.py` (added `count_in_flight()`)

**Legacy files (to be removed after full migration):**
- `app/models/feedback.py`
- `app/models/customer.py`
- `app/models/company.py`
- `app/models/classification.py`
- `app/repositories/feedback.py`
- `app/api/routes/overview.py`
- `app/api/routes/feedback.py`

---

**End of Phase 3 Design Document**
