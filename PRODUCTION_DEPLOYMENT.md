# JisrVOC Production Deployment Guide

**Version:** Phases 1-5 Complete
**Last Updated:** 2026-06-30

---

## 🎯 Overview

This guide covers deploying JisrVOC to production with all phases (1-5) enabled:
- **Phase 1:** Data ingestion & enrichment pipeline
- **Phase 2:** Clustering & theme generation
- **Phase 3:** Dashboard & analytics
- **Phase 4:** HubSpot write-back & loop closure
- **Phase 5:** Chargebee customer enrichment (optional - requires API key)

---

## ✅ Pre-Deployment Checklist

### Required Services
- [ ] PostgreSQL 16+ with `pgvector` extension
- [ ] Redis 7+
- [ ] Docker & Docker Compose (if using containers)

### Required API Keys
- [ ] **OpenAI API Key** (for classification & embeddings)
- [ ] **HubSpot API Key** (for ticket sync & write-back)
- [ ] **Chargebee API Key** (optional - for Phase 5)
- [ ] **Slack Webhook URL** (optional - for notifications)

### Optional Services
- [ ] Sentry DSN (error tracking)
- [ ] Prometheus + Grafana (metrics & monitoring)

---

## 🚀 Deployment Options

### Option 1: Docker Compose (Recommended for Dev/Staging)

**Pros:** Fast setup, all dependencies included
**Cons:** Not auto-scaling, manual monitoring

```bash
# 1. Clone repository
git clone <your-repo-url>
cd jisrvoc-backend

# 2. Create production .env
cp .env.example .env

# Edit .env with production values
nano .env

# 3. Build and start services
docker compose up --build -d

# 4. Run database migrations
docker compose exec api alembic upgrade head

# 5. Verify deployment
curl http://localhost:8000/health
curl http://localhost:8000/api/v1/readyz
```

### Option 2: Railway (Recommended for Production)

**Pros:** Auto-scaling, managed PostgreSQL/Redis, zero-downtime deploys
**Cons:** Requires Railway account

```bash
# 1. Install Railway CLI
npm install -g @railway/cli

# 2. Login and link project
railway login
railway init

# 3. Add services
railway service create api
railway service create celery-worker
railway service create celery-beat

# 4. Add managed databases
railway add postgresql
railway add redis

# 5. Set environment variables (see section below)
railway variables set OPENAI_API_KEY=...
railway variables set HUBSPOT_API_KEY=...

# 6. Deploy
railway up

# 7. Run migrations
railway run alembic upgrade head
```

### Option 3: Manual Deployment (AWS/GCP/Azure)

See detailed guide in `docs/MANUAL_DEPLOYMENT.md`

---

## 🔐 Environment Variables

### Required Variables

```bash
# Application
APP_ENV=production
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/jisrvoc
REDIS_URL=redis://host:6379/0
USE_MOCK_DATA=false  # IMPORTANT: Set to false in production!

# AI/ML
OPENAI_API_KEY=sk-...
EMBEDDING_DIM=1536  # text-embedding-3-small

# Connectors
HUBSPOT_API_KEY=pat-na1-...

# Observability (Optional but Recommended)
SENTRY_DSN=https://...@sentry.io/...
LOG_LEVEL=INFO
```

### Optional Variables (Phase 5)

```bash
# Chargebee (Phase 5 - Customer Enrichment)
CHARGEBEE_API_KEY=test_...
CHARGEBEE_SITE=jisr

# Slack (Phase 4 - Notifications)
SLACK_BOT_TOKEN=xoxb-...
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
SLACK_CHANNEL_URGENT=#urgent-feedback

# Zendesk (Phase 1 - Alternative Ingestion)
ZENDESK_SUBDOMAIN=jisr
ZENDESK_EMAIL=support@jisr.com
ZENDESK_API_TOKEN=...
```

---

## 📦 Database Setup

### Step 1: Create Database

```sql
-- Connect to PostgreSQL as superuser
psql postgres

-- Create database and user
CREATE DATABASE jisrvoc;
CREATE USER jisrvoc WITH PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE jisrvoc TO jisrvoc;

-- Enable pgvector extension
\c jisrvoc
CREATE EXTENSION IF NOT EXISTS vector;
```

### Step 2: Run Migrations

```bash
# If using Docker Compose
docker compose exec api alembic upgrade head

# If using Railway
railway run alembic upgrade head

# If manual deployment
alembic upgrade head
```

### Step 3: Verify Schema

```bash
psql $DATABASE_URL -c "\dt"
```

**Expected tables:**
- raw_ticket (immutable source records)
- feedback_item (enriched feedback)
- enrichment (AI classifications)
- embedding (vector embeddings)
- vote (vote tracking)
- theme (clustered themes)
- product_bet (PM decisions)
- writeback_log (HubSpot write-back audit)
- customer, source_connector, etc.

---

## 🔄 Celery Worker Configuration

### Queues Overview

JisrVOC uses **5 Celery queues** for different task types:

1. **writeback** - HubSpot write-back (Phase 4)
2. **notifications** - Slack notifications (Phase 4)
3. **chargebee_enrichment** - Customer enrichment (Phase 5)
4. **clustering** - Weekly theme clustering (Phase 2)
5. **alerts** - Urgent feedback alerts (Phase 2)

### Worker Deployment

```bash
# Start Celery worker with all queues
celery -A app.core.celery_app worker \
  --loglevel=info \
  --concurrency=4 \
  --queues=writeback,notifications,chargebee_enrichment,clustering,alerts

# Start Celery beat (scheduler)
celery -A app.core.celery_app beat --loglevel=info
```

### Scheduled Tasks

Celery beat runs these periodic tasks:

- **Weekly clustering:** Monday 2 AM UTC
- **Urgent alerts:** Every 5 minutes
- **Chargebee enrichment:** Daily 3 AM UTC (Phase 5)

### Monitoring Celery

```bash
# Check active queues
celery -A app.core.celery_app inspect active_queues

# Check running tasks
celery -A app.core.celery_app inspect active

# Check task stats
celery -A app.core.celery_app inspect stats
```

---

## 🏥 Health Checks

### Endpoints

1. **`GET /health`** - Basic liveness check
   - Returns 200 if API is running
   - Used by load balancers

2. **`GET /api/v1/readyz`** - Readiness check
   - Checks database connectivity
   - Checks Redis connectivity
   - Returns status + dependency health

### Example Health Check

```bash
curl http://localhost:8000/health
# {"status":"ok"}

curl http://localhost:8000/api/v1/readyz
# {
#   "status": "ready",
#   "environment": "production",
#   "mockData": false,
#   "checks": {
#     "database": "ok",
#     "redis": "ok"
#   }
# }
```

---

## 📊 Post-Deployment Verification

### 1. Check API Health

```bash
# Health check
curl https://your-domain.com/health

# Readiness check
curl https://your-domain.com/api/v1/readyz

# OpenAPI docs
open https://your-domain.com/docs
```

### 2. Test Data Ingestion (Phase 1)

```bash
# HubSpot sync
curl -X POST https://your-domain.com/api/v1/connectors/hubspot/sync \
  -H "Content-Type: application/json"

# Check feedback was created
curl https://your-domain.com/api/v1/feedback?limit=10
```

### 3. Test Enrichment Pipeline (Phase 1)

```bash
# Trigger enrichment
curl -X POST https://your-domain.com/api/v1/enrichment/process

# Verify enrichment completed
psql $DATABASE_URL -c "SELECT COUNT(*) FROM enrichment;"
```

### 4. Test Dashboard (Phase 3)

```bash
# Overview metrics
curl https://your-domain.com/api/v1/overview/metrics

# Feedback feed with filters
curl "https://your-domain.com/api/v1/feedback?urgency=High&limit=10"
```

### 5. Test Write-Back (Phase 4)

```bash
# Create a test bet (use real bet ID from database)
curl -X PATCH https://your-domain.com/api/v1/bets/{bet_id} \
  -H "Content-Type: application/json" \
  -d '{"status": "shipped"}'

# Verify writeback_log entry
psql $DATABASE_URL -c "SELECT * FROM writeback_log ORDER BY performed_at DESC LIMIT 5;"
```

### 6. Test Chargebee Enrichment (Phase 5 - Optional)

```bash
# Only if you have Chargebee API key
# Trigger enrichment for one feedback item
python -c "
from app.workers.chargebee_enrichment_worker import enrich_feedback_item
result = enrich_feedback_item.delay('feedback-uuid-here')
print(result.get(timeout=30))
"
```

---

## 📈 Monitoring & Observability

### Logs

```bash
# API logs (Docker Compose)
docker compose logs -f api

# Celery worker logs
docker compose logs -f celery-worker

# Railway logs
railway logs
```

### Metrics to Monitor

1. **API Performance**
   - p95 response time: <500ms (dashboard), <200ms (feed)
   - Error rate: <1%
   - Request rate: varies

2. **Celery Workers**
   - Queue depth: <100 tasks/queue
   - Task success rate: >99%
   - Task duration: varies by task type

3. **Database**
   - Connection pool usage
   - Query duration (p95 <500ms)
   - Disk usage

4. **Redis**
   - Memory usage
   - Cache hit rate: >70% target
   - Connection count

### Alerting Rules

Set up alerts for:
- API error rate >5% for 5 minutes
- Celery queue depth >1000 for 10 minutes
- Database query time p95 >1s for 5 minutes
- HubSpot write-back failure rate >10% for 15 minutes
- Disk usage >80%

---

## 🔄 Rollback Plan

If deployment fails:

### 1. Immediate Rollback

```bash
# Docker Compose
docker compose down
git checkout <previous-commit>
docker compose up --build -d

# Railway
railway rollback
```

### 2. Database Rollback

```bash
# Downgrade migrations (if needed)
alembic downgrade -1  # Or specific revision

# Restore from backup
pg_restore -d jisrvoc backup.sql
```

### 3. Verify Rollback

```bash
curl https://your-domain.com/health
curl https://your-domain.com/api/v1/readyz
```

---

## 🔐 Security Considerations

### API Keys
- **Never commit API keys to git**
- Use secrets manager (AWS Secrets Manager, Railway Secrets, etc.)
- Rotate keys every 90 days

### Database
- Use strong passwords (min 20 chars)
- Enable SSL connections
- Restrict network access (VPC/firewall)
- Regular backups (daily minimum)

### Application
- Enable CORS only for known domains
- Use HTTPS in production
- Enable Sentry for error tracking
- Rate limiting on public endpoints

### Compliance (Saudi Arabia)
- Host all services in Saudi region
- Keep PII in-Kingdom (database + Redis)
- Preserve audit trails (writeback_log, raw_ticket)
- Email hashes in Redis cache (privacy)

---

## 📋 Initial Backfill (First Deployment)

After deploying to production:

### 1. Sync Historical HubSpot Data

```bash
# Sync last 1000 tickets
curl -X POST https://your-domain.com/api/v1/connectors/hubspot/sync \
  -H "Content-Type: application/json" \
  -d '{"limit": 1000}'
```

### 2. Run Enrichment Pipeline

```bash
# Enrich all synced feedback
curl -X POST https://your-domain.com/api/v1/enrichment/process
```

### 3. Run Clustering (Optional)

```bash
# Trigger clustering manually
python -c "
from app.workers.clustering_worker import run_weekly_clustering
run_weekly_clustering.delay()
"
```

### 4. Chargebee Enrichment (Optional - Phase 5)

```bash
# Enrich first 100 items (test)
python -c "
from app.workers.chargebee_enrichment_worker import enrich_unenriched_feedback
result = enrich_unenriched_feedback.delay(limit=100)
print(result.get(timeout=600))
"

# After validation, enrich all
# (runs automatically via nightly schedule after this)
```

---

## 🆘 Troubleshooting

### Issue: "Connection refused" errors

**Cause:** Database or Redis not accessible

**Solution:**
```bash
# Check database
psql $DATABASE_URL -c "SELECT 1"

# Check Redis
redis-cli -u $REDIS_URL ping

# Verify network connectivity
```

### Issue: Celery tasks not processing

**Cause:** Worker not running or wrong queue

**Solution:**
```bash
# Check worker status
celery -A app.core.celery_app inspect active

# Restart worker
pkill -f celery
celery -A app.core.celery_app worker --loglevel=info --concurrency=4 \
  --queues=writeback,notifications,chargebee_enrichment,clustering,alerts &
```

### Issue: High memory usage

**Cause:** Too many concurrent tasks

**Solution:**
```bash
# Reduce Celery concurrency
celery -A app.core.celery_app worker --concurrency=2

# Or scale horizontally (more workers, less concurrency each)
```

### Issue: Migrations fail

**Cause:** Schema conflicts or missing pgvector

**Solution:**
```bash
# Check current migration
alembic current

# Ensure pgvector installed
psql $DATABASE_URL -c "CREATE EXTENSION IF NOT EXISTS vector;"

# Retry migration
alembic upgrade head
```

---

## 📞 Support

- **Documentation:** `/docs` folder
- **API Docs:** https://your-domain.com/docs
- **Issues:** GitHub Issues (if applicable)
- **Logs:** Check Sentry or application logs

---

## ✅ Production Readiness Checklist

Before declaring "production ready":

### Infrastructure
- [ ] Database backups automated (daily)
- [ ] Redis persistence enabled (AOF or RDB)
- [ ] SSL/TLS enabled
- [ ] Load balancer configured (if needed)
- [ ] Auto-scaling rules defined

### Monitoring
- [ ] Health checks configured
- [ ] Error tracking (Sentry) enabled
- [ ] Log aggregation working
- [ ] Alerting rules tested
- [ ] On-call rotation defined

### Security
- [ ] API keys in secrets manager
- [ ] CORS configured for production domain only
- [ ] Rate limiting enabled on public endpoints
- [ ] Security headers configured
- [ ] Compliance checklist reviewed

### Performance
- [ ] Database indexes verified
- [ ] Redis caching enabled
- [ ] API response times <500ms p95
- [ ] Celery rate limits configured

### Testing
- [ ] Smoke tests passed
- [ ] Load testing completed (if needed)
- [ ] Rollback plan tested
- [ ] Disaster recovery plan documented

---

**Deployment Complete!** 🎉

Your JisrVOC system is now running in production with Phases 1-5 enabled.

**Next Steps:**
1. Monitor for 48 hours
2. Run initial backfill (HubSpot sync + enrichment)
3. Train team on dashboard usage
4. Set up weekly review of insights
