# JisrVOC Production Deployment Checklist

**Date:** _______________
**Deployer:** _______________
**Environment:** Production

---

## 📋 Pre-Deployment

### Infrastructure
- [ ] PostgreSQL 16+ with pgvector running
- [ ] Redis 7+ running
- [ ] Sufficient disk space (min 50GB for database)
- [ ] Sufficient memory (min 4GB per service)
- [ ] Network connectivity verified
- [ ] SSL certificates configured (if using HTTPS)

### API Keys & Credentials
- [ ] OpenAI API key obtained and tested
- [ ] HubSpot API key obtained and tested
- [ ] Chargebee API key obtained (optional, Phase 5)
- [ ] Slack webhook URL configured (optional, Phase 4)
- [ ] Sentry DSN configured (optional, monitoring)
- [ ] All keys stored in secrets manager (NOT in .env)

### Code & Configuration
- [ ] Latest code pulled from main branch
- [ ] `.env` file created from `.env.example`
- [ ] All required environment variables set
- [ ] `USE_MOCK_DATA=false` in production
- [ ] CORS configured for production domains only
- [ ] Database connection string verified

---

## 🗄️ Database Setup

### Initial Setup
- [ ] Database `jisrvoc` created
- [ ] User `jisrvoc` created with proper permissions
- [ ] `pgvector` extension enabled
- [ ] Database backup strategy configured
- [ ] Connection pooling configured

### Migrations
- [ ] All migrations reviewed
- [ ] Migration files checked into git
- [ ] Backup taken before migration
- [ ] Migrations applied: `alembic upgrade head`
- [ ] Migration verified: `alembic current`
- [ ] Schema verified: `\dt` shows all expected tables

**Expected Tables:**
- [ ] raw_ticket
- [ ] feedback_item
- [ ] enrichment
- [ ] embedding
- [ ] vote
- [ ] theme
- [ ] product_bet
- [ ] bet_evidence
- [ ] writeback_log
- [ ] customer
- [ ] source_connector

**Phase 5 Columns (feedback_item):**
- [ ] customer_mrr
- [ ] customer_ltv
- [ ] churn_risk_score
- [ ] subscription_plan
- [ ] enriched_at

---

## 🐳 Service Deployment

### API Server
- [ ] Docker image built successfully
- [ ] Container started and running
- [ ] Health endpoint responding: `GET /health`
- [ ] Readiness check passing: `GET /api/v1/readyz`
- [ ] Database connectivity confirmed
- [ ] Redis connectivity confirmed
- [ ] Logs showing no errors
- [ ] Port 8000 accessible (or custom PORT)

### Celery Worker
- [ ] Celery worker container started
- [ ] All 5 queues configured:
  - [ ] writeback
  - [ ] notifications
  - [ ] chargebee_enrichment
  - [ ] clustering
  - [ ] alerts
- [ ] Concurrency set to 4 (or appropriate for resources)
- [ ] Worker status checked: `celery inspect active`
- [ ] Queue status checked: `celery inspect active_queues`
- [ ] Logs showing no errors

### Celery Beat
- [ ] Celery beat container started
- [ ] Scheduled tasks configured:
  - [ ] Weekly clustering (Monday 2 AM)
  - [ ] Urgent alerts (Every 5 min)
  - [ ] Chargebee enrichment (Daily 3 AM)
- [ ] Beat status checked
- [ ] Logs showing scheduled tasks

---

## 🧪 Post-Deployment Testing

### Phase 1: Data Ingestion
- [ ] HubSpot sync endpoint tested
- [ ] Webhook endpoint tested
- [ ] Identity resolution working
- [ ] Enrichment pipeline tested
- [ ] Embeddings generated correctly

**Test Commands:**
```bash
# HubSpot sync
curl -X POST $API_URL/api/v1/connectors/hubspot/sync

# Check feedback created
curl $API_URL/api/v1/feedback?limit=10

# Trigger enrichment
curl -X POST $API_URL/api/v1/enrichment/process
```

### Phase 2: Intelligence
- [ ] Clustering endpoint tested (if manual trigger)
- [ ] Themes generated correctly
- [ ] Vote weighting working
- [ ] Alerts triggered for urgent feedback (check Slack)

### Phase 3: Dashboard
- [ ] Overview metrics endpoint tested
- [ ] Feedback list with filters tested
- [ ] Themes list tested
- [ ] Bets list tested
- [ ] Pagination working
- [ ] Response times <500ms p95

**Test Commands:**
```bash
# Overview metrics
curl $API_URL/api/v1/overview/metrics

# Filtered feedback
curl "$API_URL/api/v1/feedback?urgency=High&area=Payroll&limit=10"

# Themes
curl $API_URL/api/v1/themes
```

### Phase 4: Loop Closure
- [ ] Bet status update tested
- [ ] HubSpot write-back triggered
- [ ] Writeback_log entries created
- [ ] Slack notifications sent (if configured)
- [ ] Retry logic working (test with invalid ticket)

**Test Commands:**
```bash
# Update bet status (use real bet ID)
curl -X PATCH $API_URL/api/v1/bets/{bet_id} \
  -H "Content-Type: application/json" \
  -d '{"status": "shipped"}'

# Check writeback log
psql $DATABASE_URL -c "SELECT * FROM writeback_log ORDER BY performed_at DESC LIMIT 5;"
```

### Phase 5: Chargebee Enrichment (Optional)
- [ ] Chargebee connector tested
- [ ] Enrichment service calculations verified
- [ ] Celery enrichment task working
- [ ] Redis cache functioning
- [ ] Nightly schedule configured

**Test Commands:**
```bash
# Test single enrichment
python -c "
from app.workers.chargebee_enrichment_worker import enrich_feedback_item
result = enrich_feedback_item.delay('feedback-uuid')
print(result.get(timeout=30))
"

# Check enrichment data
psql $DATABASE_URL -c "SELECT id, customer_mrr, customer_ltv, churn_risk_score FROM feedback_item WHERE enriched_at IS NOT NULL LIMIT 5;"
```

---

## 📊 Monitoring Setup

### Logging
- [ ] Structured JSON logs enabled
- [ ] Log level set to INFO (or DEBUG for initial period)
- [ ] Log aggregation configured (if using service)
- [ ] Correlation IDs working in logs

### Error Tracking
- [ ] Sentry initialized (if configured)
- [ ] Test error sent to Sentry
- [ ] Error grouping working
- [ ] Alert rules configured

### Metrics & Dashboards
- [ ] Health checks accessible
- [ ] Readiness checks accessible
- [ ] Prometheus metrics exposed (if configured)
- [ ] Grafana dashboards created (if using)
- [ ] Key metrics tracked:
  - [ ] API response times
  - [ ] Error rates
  - [ ] Celery queue depth
  - [ ] Database query duration
  - [ ] Cache hit rates

### Alerting
- [ ] Critical alerts configured:
  - [ ] API down (health check fails)
  - [ ] Database connection lost
  - [ ] Redis connection lost
  - [ ] High error rate (>5% for 5 min)
  - [ ] Celery queue backed up (>1000 tasks)
- [ ] On-call rotation defined
- [ ] Alert channels tested (email, Slack, PagerDuty, etc.)

---

## 🔐 Security Verification

### Access Control
- [ ] API keys rotated (not using development keys)
- [ ] Database credentials strong (min 20 chars)
- [ ] Redis auth enabled (if exposed)
- [ ] Firewall rules configured
- [ ] VPC/network isolation (if applicable)

### Application Security
- [ ] CORS restricted to production domains only
- [ ] HTTPS enabled (no HTTP in production)
- [ ] Security headers configured
- [ ] Rate limiting enabled on public endpoints
- [ ] SQL injection protection (parameterized queries)

### Compliance (Saudi Arabia)
- [ ] All services hosted in Saudi region
- [ ] PII kept in-Kingdom (database + Redis)
- [ ] Audit trails preserved (immutable)
- [ ] Email hashes in cache (privacy)
- [ ] Data retention policy defined

---

## 🔄 Initial Backfill

### HubSpot Data
- [ ] Historical tickets synced (specify timeframe: ______)
- [ ] Number of tickets synced: ______
- [ ] Enrichment pipeline run on synced data
- [ ] Embeddings generated
- [ ] Verification: Data visible in dashboard

### Clustering
- [ ] Initial clustering run (if data >50 items)
- [ ] Themes generated: ______ themes
- [ ] Bets generated: ______ bets (if applicable)

### Chargebee Enrichment (Phase 5 - Optional)
- [ ] Test enrichment run (100 items)
- [ ] Validation: LTV/MRR matches Chargebee UI
- [ ] Segment classification verified
- [ ] Cache functioning (check Redis)
- [ ] Full backfill scheduled or completed

---

## 📋 Documentation

- [ ] README.md updated with production info
- [ ] PRODUCTION_DEPLOYMENT.md reviewed
- [ ] API documentation accessible at `/docs`
- [ ] Runbook created for common issues
- [ ] Team trained on:
  - [ ] Dashboard usage
  - [ ] Troubleshooting
  - [ ] Monitoring
  - [ ] Incident response

---

## ✅ Go/No-Go Decision

### Critical Issues (MUST be resolved before go-live)
- [ ] All health checks passing
- [ ] Database migrations successful
- [ ] No critical errors in logs
- [ ] Core user flows tested and working
- [ ] Rollback plan tested

### Non-Critical Issues (Can be addressed post-launch)
- Monitoring dashboards incomplete
- Some optional features not tested (e.g., Chargebee)
- Performance optimization pending
- Documentation gaps

---

## 🚀 Go-Live

### Final Steps
- [ ] Announce maintenance window (if applicable)
- [ ] Switch DNS/load balancer to production
- [ ] Monitor logs for 30 minutes
- [ ] Run verification script: `./scripts/verify_deployment.sh`
- [ ] All checks passing
- [ ] Announce go-live to team

### Post-Launch Monitoring (48 hours)
- [ ] Monitor error rates (target: <1%)
- [ ] Monitor response times (target: <500ms p95)
- [ ] Monitor Celery queue depth (target: <100)
- [ ] Monitor database performance
- [ ] Monitor cache hit rates
- [ ] Review Sentry errors
- [ ] User feedback collected

---

## 🆘 Rollback Trigger Criteria

Initiate rollback if:
- [ ] Error rate >10% for 10 minutes
- [ ] Critical functionality broken (cannot ingest feedback)
- [ ] Database data corruption detected
- [ ] Security vulnerability discovered
- [ ] Cannot resolve issue within 2 hours

### Rollback Executed
- [ ] Services stopped
- [ ] Previous version deployed
- [ ] Database restored from backup (if needed)
- [ ] Verification tests passed
- [ ] Post-mortem scheduled

---

## 📝 Sign-Off

**Deployment Approved By:**

Technical Lead: _____________________ Date: _____
DevOps Lead: _____________________ Date: _____
Product Owner: _____________________ Date: _____

**Post-Launch Review Scheduled:** _____________________

---

## 📞 Emergency Contacts

- **On-Call Engineer:** _____________________
- **Database Admin:** _____________________
- **DevOps Lead:** _____________________
- **Slack Channel:** #jisrvoc-incidents

---

**Status:** [ ] Pre-Deployment [ ] Deploying [ ] Deployed [ ] Rolled Back

**Notes:**
_______________________________________________________________________________
_______________________________________________________________________________
_______________________________________________________________________________
