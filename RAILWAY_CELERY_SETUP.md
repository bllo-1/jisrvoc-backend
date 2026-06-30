# Railway Celery Services Setup Guide

## Overview

You need to create 2 additional services in Railway for background task processing:
1. **celery-worker** - Processes background tasks (enrichment, write-back, etc.)
2. **celery-beat** - Scheduler for periodic tasks (clustering, alerts, etc.)

---

## Step 1: Create Celery Worker Service

### Via Railway Dashboard

1. **Open your Railway project:**
   - Go to: https://railway.app/project/277ed31f-00dd-4a0d-84a3-84a1e527b745
   - Environment: `production`

2. **Create new service:**
   - Click **"+ New"** button
   - Select **"GitHub Repo"**
   - Choose: `bllo-1/jisrvoc-backend`
   - Service name: `celery-worker`

3. **Configure the service:**
   - Go to **Settings** tab
   - Scroll to **"Deploy"** section
   - Set **Start Command**: `./start-celery-worker.sh`
   - Set **Healthcheck Path**: (leave empty - Celery doesn't have HTTP endpoint)

4. **Environment Variables:**

   Railway will automatically inject these variables from the project:
   - `DATABASE_URL` ✓ (shared from Postgres service)
   - `REDIS_URL` ✓ (shared from Redis service)
   - `OPENAI_API_KEY` ✓ (already set)
   - `HUBSPOT_API_KEY` ✓ (already set)

   Additional variables needed (set in Variables tab):
   ```bash
   APP_ENV=production
   USE_MOCK_DATA=false
   LOG_LEVEL=INFO
   EMBEDDING_DIM=1024
   ```

5. **Deploy:**
   - Click **"Deploy"**
   - Railway will build and start the Celery worker

---

## Step 2: Create Celery Beat Service

### Via Railway Dashboard

1. **Create new service:**
   - Click **"+ New"** button
   - Select **"GitHub Repo"**
   - Choose: `bllo-1/jisrvoc-backend`
   - Service name: `celery-beat`

2. **Configure the service:**
   - Go to **Settings** tab
   - Scroll to **"Deploy"** section
   - Set **Start Command**: `./start-celery-beat.sh`
   - Set **Healthcheck Path**: (leave empty)

3. **Environment Variables:**

   Same as worker - Railway auto-injects shared variables:
   - `DATABASE_URL` ✓
   - `REDIS_URL` ✓
   - `OPENAI_API_KEY` ✓
   - `HUBSPOT_API_KEY` ✓

   Additional variables (set in Variables tab):
   ```bash
   APP_ENV=production
   USE_MOCK_DATA=false
   LOG_LEVEL=INFO
   EMBEDDING_DIM=1024
   ```

4. **Deploy:**
   - Click **"Deploy"**
   - Railway will build and start the Celery beat scheduler

---

## Step 3: Verify Services

### Check Service Status

In Railway dashboard, you should see all services **Online**:
- ✅ jisrvoc-backend (API)
- ✅ celery-worker
- ✅ celery-beat
- ✅ Postgres
- ✅ Redis

### Check Logs

1. **Celery Worker Logs:**
   ```bash
   railway service link celery-worker
   railway logs
   ```

   You should see:
   ```
   Starting Celery worker...
   celery@<hostname> ready.
   [2026-06-30 ...] Connected to redis://redis.railway.internal:6379/0
   [2026-06-30 ...] Registered tasks:
     - app.workers.writeback_worker.*
     - app.workers.chargebee_enrichment_worker.*
     - app.workers.clustering_worker.*
   ```

2. **Celery Beat Logs:**
   ```bash
   railway service link celery-beat
   railway logs
   ```

   You should see:
   ```
   Starting Celery beat scheduler...
   beat: Starting...
   Scheduler: Sending due task run-weekly-clustering (...)
   ```

---

## Step 4: Test Background Tasks

### Test HubSpot Write-Back (Celery Worker)

```bash
# Update a bet status (triggers write-back task)
curl -X PATCH https://jisrvoc-backend-production.up.railway.app/api/v1/bets/b1/status \
  -H "Content-Type: application/json" \
  -d '{"status": "shipped"}'

# Check celery-worker logs for task execution
railway service link celery-worker
railway logs --tail
```

### Test Scheduled Tasks (Celery Beat)

Celery beat runs these tasks automatically:
- **Weekly clustering:** Monday 2 AM UTC
- **Urgent alerts:** Every 5 minutes
- **Chargebee enrichment:** Daily 3 AM UTC (if API key configured)

Check the schedule in logs:
```bash
railway service link celery-beat
railway logs | grep "Scheduler:"
```

---

## Troubleshooting

### Issue: "Task timeout" or "Worker not responding"

**Solution:** Increase worker concurrency or scale workers

```bash
# Edit start-celery-worker.sh to increase concurrency
--concurrency=8  # from 4 to 8
```

### Issue: "Connection refused to Redis"

**Check Redis URL:**
```bash
railway service link celery-worker
railway variables | grep REDIS_URL
```

Should be: `redis://default:<password>@redis.railway.internal:6379`

### Issue: "No tasks registered"

**Ensure app imports workers:**
Check that `app/core/celery_app.py` imports all worker modules.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│                Railway Project                       │
│                                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────┐ │
│  │ jisrvoc-     │  │ celery-      │  │ celery-   │ │
│  │ backend      │  │ worker       │  │ beat      │ │
│  │ (API)        │  │              │  │           │ │
│  └──────┬───────┘  └──────┬───────┘  └─────┬─────┘ │
│         │                 │                 │       │
│         └─────────────────┴─────────────────┘       │
│                           │                         │
│         ┌─────────────────┴─────────────────┐       │
│         │                                   │       │
│  ┌──────▼──────┐                    ┌──────▼────┐  │
│  │  Postgres   │                    │   Redis   │  │
│  │  (Database) │                    │  (Queue)  │  │
│  └─────────────┘                    └───────────┘  │
└─────────────────────────────────────────────────────┘
```

**How it works:**
1. **API** receives requests → queues tasks in Redis
2. **Celery Worker** pulls tasks from Redis → executes them
3. **Celery Beat** triggers scheduled tasks → queues them in Redis
4. All services share **Postgres** (data) and **Redis** (queue)

---

## Next Steps After Setup

1. ✅ Verify all 5 services are online
2. ✅ Check logs for errors
3. ✅ Test task execution (HubSpot sync)
4. ✅ Monitor queue depth

---

## Quick Commands Reference

```bash
# Switch between services
railway service link jisrvoc-backend
railway service link celery-worker
railway service link celery-beat

# View logs
railway logs
railway logs --tail  # follow logs

# Check status
railway service status

# Restart service
railway service restart

# Set environment variable
railway variables set KEY="value"
```

---

**Ready?** Open the Railway dashboard and create the services! 🚀

Dashboard URL: https://railway.app/project/277ed31f-00dd-4a0d-84a3-84a1e527b745
