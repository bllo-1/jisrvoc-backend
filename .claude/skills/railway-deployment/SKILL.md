---
name: railway-deploy-backend
description: Deploy JisrVoC backend to Railway with proper environment variables, health checks, and rollback procedures
---

# Railway Deployment Workflow for JisrVoC Backend

## When to Use This Skill

Use this skill when you need to:
- Deploy backend code changes to Railway
- Update environment variables
- Troubleshoot deployment failures
- Roll back to a previous deployment
- Set up a new Railway service from scratch

## Prerequisites

- [ ] Railway CLI installed (`npm i -g @railway/cli` or `brew install railway`)
- [ ] Authenticated to Railway (`railway login`)
- [ ] Backend tests passing locally
- [ ] Git changes committed (Railway deploys from GitHub)
- [ ] Railway project and service already exist

## Current Deployment Status

**Platform**: Railway
**Project**: jisrvoc-backend
**Service**: jisrvoc-backend
**Environment**: production
**Repository**: https://github.com/bllo-1/jisrvoc-backend
**Live URL**: https://jisrvoc-backend-production.up.railway.app

## Workflow

### Step 1: Pre-Deployment Checks

Before deploying, verify the code is ready:

```bash
# Navigate to backend directory
cd /Users/jisr4/Desktop/JisrVoC/jisrvoc-backend

# Run tests (when test suite exists)
source venv/bin/activate
pytest

# Verify health check endpoint works locally
# Start server: uvicorn app.main:app --reload
# Test: curl http://localhost:8000/api/v1/healthz
# Expected: {"status": "healthy"}
```

**Checklist**:
- [ ] All tests passing
- [ ] Health check endpoint responds
- [ ] No uncommitted changes that should be deployed
- [ ] Environment variables documented

### Step 2: Commit and Push Changes

Railway auto-deploys from GitHub when code is pushed:

```bash
# Check current branch
git branch --show-current

# Stage changes
git add .

# Commit with descriptive message
git commit -m "feat: add HubSpot connector with OAuth flow

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"

# Push to GitHub (triggers Railway deployment)
git push origin master
```

### Step 3: Monitor Deployment

Watch the deployment progress:

```bash
# Check deployment status
railway status

# Stream build and deploy logs
railway logs --follow

# Or check specific deployment
railway logs --deployment <deployment-id>
```

**Key Log Indicators**:
- ✅ `Building...` → `Build successful` → `Deploying...` → `Deployed`
- ❌ `Build failed` → Check build logs for errors
- ❌ `Deployment crashed` → Check runtime logs

### Step 4: Verify Deployment

Once deployed, test the live service:

```bash
# Health check
curl https://jisrvoc-backend-production.up.railway.app/api/v1/healthz

# Expected response:
# {"status": "healthy"}

# Test an API endpoint
curl https://jisrvoc-backend-production.up.railway.app/api/v1/themes

# Check Swagger docs
open https://jisrvoc-backend-production.up.railway.app/docs
```

**Verification Checklist**:
- [ ] Health check returns 200 OK
- [ ] API endpoints respond correctly
- [ ] No 500 errors in logs
- [ ] Database connection working (check logs)

### Step 5: Update Environment Variables (If Needed)

If you need to add or change environment variables:

```bash
# Set a variable
railway variables set OPENAI_API_KEY="sk-..."

# Set multiple variables
railway variables set \
  HUBSPOT_API_KEY="..." \
  ZENDESK_API_TOKEN="..." \
  USE_MOCK_DATA="false"

# View current variables
railway variables

# Note: Changing variables triggers a redeploy
```

**Critical Variables**:
```bash
# Database (auto-provided by Railway PostgreSQL addon)
DATABASE_URL=postgresql://...

# Application
PORT=8000                    # Auto-provided by Railway
USE_MOCK_DATA=true          # Set to false in Phase 1

# Security (Phase 1)
SECRET_KEY=<generate-random-key>
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# OpenAI (Phase 1)
OPENAI_API_KEY=sk-...

# HubSpot (Phase 1)
HUBSPOT_API_KEY=...

# Zendesk (Phase 1)
ZENDESK_EMAIL=...
ZENDESK_API_TOKEN=...
ZENDESK_SUBDOMAIN=...
```

## Common Issues & Solutions

### Issue 1: Build Fails with Dependency Error

**Symptom**: `ERROR: Could not find a version that satisfies the requirement X`

**Solution**:
```bash
# Update requirements.txt locally
pip freeze > requirements.txt

# Commit and push
git add requirements.txt
git commit -m "fix: update dependencies"
git push
```

### Issue 2: Deployment Crashes on Startup

**Symptom**: Logs show `Application failed to respond` or `Worker timeout`

**Solution 1**: Check if PORT binding is correct
```bash
# Verify start.sh uses $PORT
cat start.sh
# Should contain: --port ${PORT:-8000}
```

**Solution 2**: Check database connection
```bash
# View logs for connection errors
railway logs | grep -i "database\|connection\|postgres"

# Verify DATABASE_URL is set
railway variables | grep DATABASE_URL
```

**Solution 3**: Check for syntax errors
```bash
# Test locally first
python -m app.main
```

### Issue 3: Health Check Failing

**Symptom**: Railway shows "unhealthy" status

**Solution**:
```bash
# Check health check configuration in railway.json
cat railway.json
# Should have:
# "healthcheckPath": "/api/v1/healthz"
# "healthcheckTimeout": 100

# Test health endpoint
curl https://jisrvoc-backend-production.up.railway.app/api/v1/healthz

# If 404, verify route exists in app/main.py
```

### Issue 4: 502 Bad Gateway

**Symptom**: All requests return 502

**Solution**:
```bash
# Check if service is running
railway logs --tail 50

# Look for:
# - Python exceptions
# - Port binding errors
# - Database connection failures

# Restart service if needed
railway restart
```

## Rollback Procedure

If a deployment introduces a bug:

### Option 1: Redeploy Previous Version (Fast)

```bash
# List recent deployments
railway deployments

# Rollback to specific deployment
railway rollback <deployment-id>

# Or rollback to previous deployment
railway rollback
```

### Option 2: Revert Git Commit (Clean)

```bash
# Find the bad commit
git log --oneline -5

# Revert the commit (creates new commit)
git revert <commit-hash>

# Push (triggers new deployment)
git push origin master
```

### Option 3: Emergency Variable Change

```bash
# If issue is environment variable related
# Revert to previous value (triggers redeploy)
railway variables set USE_MOCK_DATA="true"
```

## Advanced: Setting Up Railway from Scratch

If you need to create a new Railway service:

### 1. Create Railway Project

```bash
# Initialize Railway in project directory
cd /Users/jisr4/Desktop/JisrVoC/jisrvoc-backend
railway init

# Follow prompts to create new project or link existing
```

### 2. Connect GitHub Repository

```bash
# Link GitHub repo for auto-deployment
railway link

# Or create new service with GitHub
railway up
```

**Via Railway Dashboard**:
1. Go to Railway dashboard
2. New Project → Deploy from GitHub
3. Select repository: `bllo-1/jisrvoc-backend`
4. Select branch: `master`

### 3. Add PostgreSQL Database

```bash
# Add PostgreSQL addon
railway add

# Select: PostgreSQL
# Railway will automatically set DATABASE_URL
```

**Via Railway Dashboard**:
1. Open project → New → Database → PostgreSQL
2. Railway auto-configures DATABASE_URL reference

### 4. Configure Service Settings

Edit `railway.json`:
```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "NIXPACKS"
  },
  "deploy": {
    "startCommand": "./start.sh",
    "healthcheckPath": "/api/v1/healthz",
    "healthcheckTimeout": 100,
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10
  }
}
```

### 5. Set Environment Variables

```bash
# Required for deployment
railway variables set PORT=8000
railway variables set USE_MOCK_DATA=true

# Add others as needed
railway variables set SECRET_KEY="$(openssl rand -hex 32)"
```

### 6. Deploy

```bash
# Trigger first deployment
git push origin master

# Monitor
railway logs --follow
```

## Deployment Scripts

### scripts/deploy.sh

Create this helper script for quick deployments:

```bash
#!/bin/bash
set -e

echo "🚀 Deploying JisrVoC Backend to Railway"

# Pre-flight checks
echo "📋 Running pre-flight checks..."
pytest || { echo "❌ Tests failed"; exit 1; }

echo "✅ Tests passed"

# Commit and push
echo "📦 Committing changes..."
read -p "Commit message: " message
git add .
git commit -m "$message

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"

echo "⬆️  Pushing to GitHub..."
git push origin master

echo "👀 Monitoring deployment..."
railway logs --follow
```

Usage:
```bash
chmod +x .claude/skills/railway-deployment/scripts/deploy.sh
.claude/skills/railway-deployment/scripts/deploy.sh
```

## Success Criteria

Deployment is successful when:
- [ ] Build completes without errors
- [ ] Deployment status shows "Success"
- [ ] Health check endpoint returns 200 OK
- [ ] API endpoints respond correctly
- [ ] No error logs in Railway dashboard
- [ ] Swagger docs accessible at /docs

## Related Skills

- `jisrvoc-backend-context` - Understand backend architecture
- `database-migrations` - Apply database changes before deploying
- `mock-to-real-data` - Switch from mock to real data mode

## Quick Reference

### Useful Commands

```bash
# Check current deployment
railway status

# View logs
railway logs
railway logs --follow           # Stream logs
railway logs --deployment ID    # Specific deployment

# Environment variables
railway variables                   # List all
railway variables set KEY=VALUE     # Set variable
railway variables unset KEY         # Remove variable

# Deployments
railway deployments                 # List recent
railway rollback                    # Rollback to previous
railway rollback DEPLOYMENT_ID      # Rollback to specific

# Service management
railway restart                     # Restart service
railway up                          # Deploy current directory

# Link/switch
railway link                        # Link to project
railway environment                 # Switch environment
```

### Environment URLs

- **Production API**: https://jisrvoc-backend-production.up.railway.app
- **API Docs**: https://jisrvoc-backend-production.up.railway.app/docs
- **Health Check**: https://jisrvoc-backend-production.up.railway.app/api/v1/healthz
- **Railway Dashboard**: https://railway.app/project/<project-id>

### Support

- Railway Docs: https://docs.railway.app
- Railway Discord: https://discord.gg/railway
- GitHub Issues: https://github.com/bllo-1/jisrvoc-backend/issues
