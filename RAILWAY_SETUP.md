# Railway Deployment Setup Guide

**Status:** Ready to deploy to Railway
**Time Required:** 15-30 minutes

---

## 🚂 Step 1: Railway Authentication

First, you need to authenticate with Railway:

```bash
# Install Railway CLI (if not already installed)
npm install -g @railway/cli

# Login to Railway
railway login
```

This will open a browser window for authentication. Once authenticated, return to the terminal.

---

## 🗂️ Step 2: Create or Link Railway Project

### Option A: Create New Project

```bash
cd /Users/jisr4/Desktop/JisrVoC/jisrvoc-backend

# Initialize new Railway project
railway init

# This will prompt you to:
# 1. Create a new project or link existing
# 2. Name your project (e.g., "jisrvoc-backend")
```

### Option B: Link Existing Project

If you already have a Railway project:

```bash
# List your projects
railway list

# Link to existing project
railway link <project-id>
```

---

## 🗄️ Step 3: Add Database Services

### Add PostgreSQL

```bash
# Add PostgreSQL with pgvector
railway add -d postgres

# Note: Railway's PostgreSQL includes pgvector by default
# The DATABASE_URL will be automatically set
```

### Add Redis

```bash
# Add Redis
railway add -d redis

# The REDIS_URL will be automatically set
```

---

## 🔧 Step 4: Set Environment Variables

Set all required environment variables:

```bash
# Required - AI/ML
railway variables set OPENAI_API_KEY="your-openai-api-key"
railway variables set EMBEDDING_DIM="1536"

# Required - Connectors
railway variables set HUBSPOT_API_KEY="your-hubspot-api-key"

# Optional - Phase 5 (Chargebee)
railway variables set CHARGEBEE_API_KEY="your-chargebee-api-key"
railway variables set CHARGEBEE_SITE="jisr"

# Optional - Notifications
railway variables set SLACK_BOT_TOKEN="your-slack-token"
railway variables set SLACK_WEBHOOK_URL="https://hooks.slack.com/services/..."

# Application Settings
railway variables set APP_ENV="production"
railway variables set USE_MOCK_DATA="false"
railway variables set LOG_LEVEL="INFO"

# Optional - Monitoring
railway variables set SENTRY_DSN="your-sentry-dsn"
```

**Important:** DATABASE_URL and REDIS_URL are automatically set when you add the services.

---

## 🚀 Step 5: Create Services

Railway needs three separate services:

### Service 1: API Server

```bash
# Create API service
railway service create api

# Link to the service
railway service link api

# Set start command for API
railway variables set --service api PORT="8000"
```

### Service 2: Celery Worker

```bash
# Create Celery worker service
railway service create celery-worker

# Link to the service
railway service link celery-worker

# Override start command for Celery worker
# (Railway will use Dockerfile by default, but we need custom command)
```

**Note:** For celery-worker, you'll need to set a custom start command in Railway dashboard:
```bash
celery -A app.core.celery_app worker --loglevel=info --concurrency=4 --queues=writeback,notifications,chargebee_enrichment,clustering,alerts
```

### Service 3: Celery Beat

```bash
# Create Celery beat service
railway service create celery-beat

# Link to the service
railway service link celery-beat

# Override start command for Celery beat
```

**Note:** For celery-beat, set custom start command in Railway dashboard:
```bash
celery -A app.core.celery_app beat --loglevel=info
```

---

## 📦 Step 6: Deploy

Now deploy all services:

```bash
# Deploy the application
railway up

# This will:
# 1. Build Docker image from Dockerfile
# 2. Push to Railway
# 3. Start all services
```

**Monitor deployment:**
```bash
# Watch logs
railway logs

# Check service status
railway status
```

---

## 🗄️ Step 7: Run Database Migrations

Once deployed, run migrations:

```bash
# Run migrations on Railway
railway run alembic upgrade head

# Verify tables created
railway run 'psql $DATABASE_URL -c "\dt"'
```

---

## ✅ Step 8: Verify Deployment

### Check Health Endpoints

```bash
# Get the API URL
railway domain

# Test health check (replace with your domain)
curl https://your-app.railway.app/health
curl https://your-app.railway.app/api/v1/readyz
```

### Run Verification Script

```bash
# Download and run verification locally against Railway
export API_URL=https://your-app.railway.app
./scripts/verify_deployment.sh
```

---

## 📊 Step 9: Initial Data Load

### Sync HubSpot Data

```bash
# Trigger HubSpot sync
curl -X POST https://your-app.railway.app/api/v1/connectors/hubspot/sync

# Check feedback created
curl https://your-app.railway.app/api/v1/feedback?limit=10
```

### Run Enrichment

```bash
# Trigger enrichment pipeline
curl -X POST https://your-app.railway.app/api/v1/enrichment/process
```

---

## 🔍 Monitoring & Debugging

### View Logs

```bash
# All services
railway logs

# Specific service
railway logs --service api
railway logs --service celery-worker
railway logs --service celery-beat
```

### Check Environment Variables

```bash
# List all variables
railway variables

# Check specific service variables
railway variables --service api
```

### Check Service Status

```bash
# Service status
railway status

# Service info
railway service
```

---

## 🛠️ Troubleshooting

### Issue: "Unauthorized" error

**Solution:**
```bash
railway logout
railway login
```

### Issue: Migrations fail

**Solution:**
```bash
# Check database connection
railway run 'psql $DATABASE_URL -c "SELECT 1"'

# Enable pgvector (if needed)
railway run 'psql $DATABASE_URL -c "CREATE EXTENSION IF NOT EXISTS vector;"'

# Retry migration
railway run alembic upgrade head
```

### Issue: Celery worker not processing tasks

**Solution:**
1. Check worker logs: `railway logs --service celery-worker`
2. Verify Redis connection: Check REDIS_URL in variables
3. Verify worker command includes all queues
4. Restart service from Railway dashboard

### Issue: API not accessible

**Solution:**
```bash
# Check if service is running
railway status

# Check logs for errors
railway logs --service api

# Verify domain is set
railway domain
```

---

## 🔐 Railway Dashboard Configuration

Some settings need to be configured in the Railway dashboard (https://railway.app):

### For celery-worker service:
1. Go to your project → celery-worker service
2. Click "Settings" → "Start Command"
3. Set: `celery -A app.core.celery_app worker --loglevel=info --concurrency=4 --queues=writeback,notifications,chargebee_enrichment,clustering,alerts`
4. Click "Deploy"

### For celery-beat service:
1. Go to your project → celery-beat service
2. Click "Settings" → "Start Command"
3. Set: `celery -A app.core.celery_app beat --loglevel=info`
4. Click "Deploy"

### For API service:
1. Railway will use the Dockerfile CMD by default
2. If you need to override, set: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

---

## 📈 Cost Estimate (Railway)

**Hobby Plan (Free):**
- $5/month credit
- Good for development/testing
- Limited resources

**Pro Plan:**
- Pay-as-you-go
- Estimated cost for JisrVOC:
  - API: ~$5-10/month
  - Celery Worker: ~$5-10/month
  - Celery Beat: ~$5/month
  - PostgreSQL: ~$10-20/month
  - Redis: ~$5/month
  - **Total: ~$30-50/month**

---

## 🎯 Quick Command Reference

```bash
# Authentication
railway login
railway logout
railway whoami

# Project Management
railway init                    # Create/link project
railway list                    # List projects
railway link <project-id>       # Link to project

# Service Management
railway service create <name>   # Create service
railway service link <name>     # Link to service
railway service list            # List services

# Deployment
railway up                      # Deploy
railway down                    # Stop services

# Variables
railway variables               # List variables
railway variables set KEY=value # Set variable

# Database
railway add -d postgres         # Add PostgreSQL
railway add -d redis            # Add Redis

# Monitoring
railway logs                    # View logs
railway status                  # Service status
railway domain                  # Get domain

# Execution
railway run <command>           # Run command on Railway
```

---

## ✅ Deployment Checklist

Once completed, you should have:

- [ ] Railway account authenticated
- [ ] Project created ("jisrvoc-backend")
- [ ] PostgreSQL database added
- [ ] Redis added
- [ ] 3 services created (api, celery-worker, celery-beat)
- [ ] All environment variables set
- [ ] Code deployed (`railway up`)
- [ ] Migrations applied
- [ ] Health checks passing
- [ ] HubSpot sync working
- [ ] Enrichment pipeline working

---

## 📞 Next Steps After Deployment

1. **Monitor for 24-48 hours**
   - Watch logs for errors
   - Check health endpoints regularly
   - Monitor Celery queue depths

2. **Initial Data Load**
   - Sync historical HubSpot tickets
   - Run enrichment pipeline
   - Wait for first clustering (Monday 2 AM)

3. **Team Training**
   - Share API documentation URL
   - Train team on dashboard
   - Set up monitoring alerts

---

**Need Help?**
- Railway Docs: https://docs.railway.app
- Railway Discord: https://discord.gg/railway
- JisrVOC Docs: See `PRODUCTION_DEPLOYMENT.md`

---

**You're ready to deploy to Railway!** 🚂

Start with Step 1 (Authentication) and work through the steps sequentially.
