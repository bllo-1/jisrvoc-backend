# Phase 5: V2 Enhancements - Implementation Prompt

**Created:** 2026-06-30
**Prerequisites:** Phase 4 (Loop Closure) Complete ✅
**Objective:** Scale JisrVOC system with Chargebee enrichment, performance optimizations, and monitoring

---

## 🎯 Overview

Phase 5 builds on the complete feedback loop (Phases 1-4) by adding:

1. **Advanced Enrichment**: Customer LTV, churn risk, segment classification (Chargebee)
2. **Performance Optimizations**: Batch processing, caching, query optimization
3. **Production Readiness**: Monitoring, error handling, rate limiting
4. **Future Data Sources**: Slack ingestion (planned for Phase 6)

---

## 📋 Phase 5 Components

### 1. Chargebee Enrichment

**Goal:** Enrich feedback items with customer subscription data (LTV, MRR, plan tier)

#### 1.1 Chargebee Connector
- **File:** `app/connectors/chargebee_connector.py`
- **Features:**
  - API authentication with Chargebee
  - Customer lookup by email/ID
  - Subscription data fetch (plan, MRR, status)
  - Invoice history retrieval
  - Churn prediction signals (failed payments, cancellation requests)

#### 1.2 Enrichment Service
- **File:** `app/services/chargebee_enrichment.py`
- **Features:**
  - Calculate customer LTV (lifetime value)
  - Determine customer segment (SMB, Mid-Market, Enterprise) from MRR
  - Compute churn risk score (0-100)
  - Extract plan-specific features (payroll users, employee count)
  - Cache enrichment data (TTL: 24 hours)

#### 1.3 Database Schema Updates
- **Migration:** `alembic revision -m "add_chargebee_enrichment"`
- **New Fields on `feedback_item`:**
  ```sql
  ALTER TABLE feedback_item ADD COLUMN customer_mrr NUMERIC(10,2);
  ALTER TABLE feedback_item ADD COLUMN customer_ltv NUMERIC(10,2);
  ALTER TABLE feedback_item ADD COLUMN churn_risk_score INTEGER;
  ALTER TABLE feedback_item ADD COLUMN subscription_plan TEXT;
  ALTER TABLE feedback_item ADD COLUMN enriched_at TIMESTAMP;
  ```

#### 1.4 Celery Worker
- **File:** `app/workers/chargebee_enrichment_worker.py`
- **Tasks:**
  - `enrich_feedback_item(feedback_id)` - Enrich single item
  - `batch_enrich_feedback(feedback_ids)` - Batch enrich (100 at a time)
  - Rate limiting: 300 requests/minute (Chargebee limit)
  - Caching: Redis cache for customer data (TTL: 24h)

#### Success Criteria:
- [ ] Chargebee API integration working
- [ ] Customer LTV calculation accurate
- [ ] Segment classification matches finance team's rules
- [ ] Enrichment data cached (Redis hit rate >80%)
- [ ] Batch enrichment processing 500+ items/minute

---

### 2. Performance Optimizations

**Goal:** Optimize database queries, add caching, improve clustering performance

#### 2.1 Database Indexing
- **Migration:** `alembic revision -m "add_performance_indexes"`
- **Indexes to Add:**
  ```sql
  CREATE INDEX idx_feedback_created_at ON feedback_item(created_at DESC);
  CREATE INDEX idx_feedback_urgency_area ON feedback_item(urgency, product_area);
  CREATE INDEX idx_feedback_customer_segment ON feedback_item(customer_segment);
  CREATE INDEX idx_theme_vote_weight ON theme(vote_weight DESC);
  CREATE INDEX idx_bet_status ON product_bet(status);
  CREATE INDEX idx_writeback_log_bet_id ON writeback_log(bet_id);
  ```

#### 2.2 Query Optimization
- **Files to Optimize:**
  - `app/repositories/feedback_item.py` - Add `.options(selectinload(...))` for eager loading
  - `app/repositories/theme.py` - Use `func.count()` instead of loading all items
  - `app/services/analytics.py` - Add materialized views for dashboard metrics

#### 2.3 Redis Caching Layer
- **File:** `app/core/cache.py`
- **Features:**
  ```python
  @cached(ttl=3600, key_prefix="dashboard_metrics")
  async def get_dashboard_metrics():
      # Expensive aggregation query
      pass

  @cached(ttl=86400, key_prefix="customer_enrichment")
  async def get_customer_data(customer_id: str):
      # Chargebee API call
      pass
  ```

#### 2.4 Batch Processing
- **File:** `app/services/batch_processor.py`
- **Features:**
  - Batch classification (100 items at a time)
  - Batch clustering (500 items at a time)
  - Parallel Celery tasks with `group()` and `chord()`
  - Progress tracking with Redis

#### Success Criteria:
- [ ] Dashboard loads <500ms (p95)
- [ ] Feedback list endpoint <200ms (p95)
- [ ] Redis cache hit rate >70%
- [ ] Database query count reduced by 50%
- [ ] Batch processing 1000+ items in <5 minutes

---

### 3. Monitoring & Observability

**Goal:** Add comprehensive logging, metrics, and alerting

#### 3.1 Structured Logging
- **File:** `app/core/logging.py`
- **Features:**
  - JSON-formatted logs with trace IDs
  - Contextual logging (user_id, bet_id, feedback_id)
  - Log levels per module
  - Integration with Sentry for errors

#### 3.2 Metrics Collection
- **File:** `app/core/metrics.py`
- **Metrics to Track:**
  ```python
  # API Metrics
  - api_request_duration_seconds (histogram)
  - api_request_count (counter)
  - api_error_rate (gauge)

  # Worker Metrics
  - celery_task_duration_seconds (histogram)
  - celery_task_success_count (counter)
  - celery_task_failure_count (counter)
  - celery_queue_depth (gauge)

  # Business Metrics
  - feedback_items_ingested_count (counter)
  - themes_created_count (counter)
  - bets_shipped_count (counter)
  - hubspot_writeback_success_rate (gauge)
  ```

#### 3.3 Health Checks
- **File:** `app/api/routes/health.py`
- **Endpoints:**
  - `GET /health` - Overall system health
  - `GET /health/db` - Database connectivity
  - `GET /health/redis` - Redis connectivity
  - `GET /health/celery` - Worker status
  - `GET /health/external` - HubSpot, Slack, Chargebee APIs

#### 3.4 Alerting Rules
- **File:** `docs/alerting_rules.yml`
- **Alerts:**
  - API error rate >5% for 5 minutes
  - Celery queue depth >1000 for 10 minutes
  - Database query time p95 >1s for 5 minutes
  - HubSpot writeback failure rate >10% for 15 minutes
  - Disk usage >80%

#### Success Criteria:
- [ ] All API endpoints have duration metrics
- [ ] All Celery tasks have success/failure counters
- [ ] Health check endpoint returns status in <100ms
- [ ] Sentry captures all errors with full context
- [ ] Alerting rules tested and working

---

### 4. Production Deployment

**Goal:** Deploy Phase 5 to production with zero downtime

#### 4.1 Database Migration
```bash
# Run migrations
alembic upgrade head

# Verify schema
psql jisrvoc -c "\d+ feedback_item"
psql jisrvoc -c "\di"  # Check indexes
```

#### 4.2 Environment Variables
```bash
# .env additions for Phase 5
SLACK_BOT_TOKEN=xoxb-...
SLACK_SIGNING_SECRET=...
CHARGEBEE_API_KEY=...
CHARGEBEE_SITE=jisr
REDIS_CACHE_TTL=3600
SENTRY_DSN=https://...
```

#### 4.3 Celery Worker Deployment
```bash
# Update Celery queues
celery -A app.core.celery_app worker \
  --loglevel=info \
  --concurrency=4 \
  --queues=writeback,notifications,chargebee_enrichment,clustering,alerts
```

#### 4.4 Rollout Plan
1. Deploy database migrations (off-peak hours)
2. Deploy API server (rolling restart, 25% at a time)
3. Deploy Celery workers (drain + restart)
4. Enable Chargebee enrichment (batch process existing feedback)
5. Monitor for 48 hours before full rollout

#### Success Criteria:
- [ ] Zero downtime during deployment
- [ ] All migrations applied successfully
- [ ] Celery workers processing all 5 queues
- [ ] Chargebee enrichment batch complete (100% success rate)

---

## 📊 Phase 5 Success Metrics (After 1 Week)

### Data Enrichment
- [ ] **Chargebee enrichment rate:** >95% of feedback items
- [ ] **LTV calculation accuracy:** 100% (matches finance team data)
- [ ] **Segment classification accuracy:** >98%

### Performance
- [ ] **API p95 latency:** <500ms (dashboard), <200ms (feedback list)
- [ ] **Cache hit rate:** >70%
- [ ] **Database query count reduction:** >50%
- [ ] **Batch processing throughput:** >1,000 items/5min

### Reliability
- [ ] **API error rate:** <1%
- [ ] **Celery task success rate:** >99%
- [ ] **HubSpot writeback success rate:** >99%
- [ ] **Health check uptime:** >99.9%

---

## 🗂️ File Structure for Phase 5

```
app/
├── connectors/
│   └── chargebee_connector.py      # NEW - Chargebee API client
├── services/
│   ├── chargebee_enrichment.py     # NEW - Customer enrichment
│   └── batch_processor.py          # NEW - Batch operations
├── workers/
│   └── chargebee_enrichment_worker.py  # NEW - Celery task for Chargebee
├── core/
│   ├── cache.py                    # NEW - Redis caching decorators
│   ├── logging.py                  # NEW - Structured logging
│   └── metrics.py                  # NEW - Prometheus metrics
├── api/routes/
│   └── health.py                   # NEW - Health check endpoints
└── alembic/versions/
    ├── xxxx_add_chargebee_enrichment.py  # NEW - Migration
    └── yyyy_add_performance_indexes.py   # NEW - Migration

tests/
├── connectors/
│   └── test_chargebee_connector.py # NEW
├── services/
│   └── test_chargebee_enrichment.py # NEW
└── workers/
    └── test_chargebee_enrichment_worker.py  # NEW

docs/
├── PHASE5_IMPLEMENTATION_STATUS.md  # NEW - Progress tracker
├── PHASE5_COMPLETION_SUMMARY.md     # NEW - Final summary
└── alerting_rules.yml               # NEW - Prometheus alerts
```

---

## 🔑 Key Design Decisions

### Decision 1: Customer Enrichment Timing
**Options:**
- **A)** Real-time enrichment (on feedback creation)
- **B)** Batch enrichment (nightly job)
- **C)** On-demand enrichment (when viewing feedback detail)

**Recommended:** Option B - Batch enrichment
**Rationale:** Reduces API calls to Chargebee, enables caching, predictable load

### Decision 2: Caching Strategy
**Options:**
- **A)** Cache individual records (feedback items, customers)
- **B)** Cache aggregated queries (dashboard metrics, theme stats)
- **C)** Both

**Recommended:** Option C - Both
**Rationale:** Max cache hit rate, balances memory vs. performance

### Decision 3: Monitoring Stack
**Options:**
- **A)** Prometheus + Grafana (self-hosted)
- **B)** Datadog (SaaS)
- **C)** CloudWatch (AWS-native)

**Recommended:** Option A - Prometheus + Grafana
**Rationale:** Open-source, flexible, no vendor lock-in, cost-effective

---

## 🧪 Testing Strategy

### Unit Tests (80% coverage target)
- Chargebee enrichment calculations
- Cache invalidation logic
- Batch processing error handling
- LTV and churn risk calculations

### Integration Tests
- Chargebee API calls with sandbox account
- Redis cache hit/miss scenarios
- Database query performance benchmarks
- Batch enrichment with 1000+ items

### Load Tests
- 1,000 concurrent API requests
- 10,000 feedback items in batch processing
- 1,000 Celery tasks queued simultaneously

---

## 📚 Reference Documentation

### Chargebee API
- https://apidocs.chargebee.com/docs/api/customers
- https://apidocs.chargebee.com/docs/api/subscriptions
- https://apidocs.chargebee.com/docs/api/invoices

### Performance Best Practices
- PostgreSQL indexing: https://www.postgresql.org/docs/current/indexes.html
- SQLAlchemy eager loading: https://docs.sqlalchemy.org/en/20/orm/loading_relationships.html
- Redis caching patterns: https://redis.io/docs/manual/patterns/

---

## 🚀 Ready to Start Phase 5?

**Pre-flight Checklist:**
- [ ] Phase 4 (Loop Closure) deployed and tested ✅
- [ ] Chargebee API key obtained
- [ ] Redis instance available (for caching)
- [ ] Prometheus + Grafana set up (optional for MVP)

**Suggested Implementation Order:**
1. **Chargebee Enrichment** (core feature, enriches existing + new feedback)
2. **Performance Optimizations** (improves UX for all users)
3. **Monitoring & Observability** (production readiness)
4. **Testing & Deployment** (zero-downtime rollout)

**Let's build Phase 5!** 🎯

---

**Next Steps:**
1. Review this prompt and confirm scope
2. Obtain Chargebee API credentials
3. Start with Chargebee Enrichment (follow TDD approach)
4. Use `/superpowers:brainstorm` for design decisions
5. Use `/superpowers:write-plan` for detailed task breakdown
6. Execute with `/superpowers:execute-plan` in batches

---

## 🔮 Phase 6 Preview: Slack Ingestion

**Note:** Slack ingestion has been deferred to Phase 6 to focus on Chargebee enrichment and performance optimizations first.

### Planned Features (Phase 6)
- Slack OAuth 2.0 authentication
- Channel subscription management
- Message → FeedbackItem conversion
- Thread context extraction
- Sentiment analysis from messages and reactions
- Celery worker for batch message processing

See `PHASE6_SLACK_INGESTION.md` (to be created) for detailed implementation plan.
