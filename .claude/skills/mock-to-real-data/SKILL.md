---
name: switch-from-mock-data
description: Transition JisrVoC from USE_MOCK_DATA=true to real database and API integrations with testing and rollback plan
---

# Switching from Mock Data to Real Data

## When to Use This Skill

Use when transitioning from MVP mock data mode to real data in Phase 1:
- Switch `USE_MOCK_DATA` flag to `false`
- Connect real database
- Integrate HubSpot/Zendesk APIs
- Enable AI enrichment pipeline
- Test end-to-end data flow

## Current State

```python
# app/core/config.py
USE_MOCK_DATA = True  # Currently using hardcoded mock data

# Mock data locations:
# - app/api/v1/themes.py (returns MOCK_THEMES)
# - app/api/v1/feedback.py (returns MOCK_FEEDBACK)
# - app/api/v1/customers.py (returns MOCK_CUSTOMERS)
# - app/api/v1/bets.py (returns MOCK_BETS)
```

## Transition Checklist

### Prerequisites

- [ ] Database migrations applied (tables exist)
- [ ] HubSpot connector implemented and tested
- [ ] Zendesk connector implemented and tested
- [ ] AI enrichment pipeline ready
- [ ] Background jobs configured
- [ ] Redis cache available (for LLM caching)

### Phase 1: Database Setup

```bash
# 1. Verify PostgreSQL addon exists on Railway
railway variables | grep DATABASE_URL

# 2. Run migrations to create tables
railway run alembic upgrade head

# 3. Seed initial data (optional)
railway run python -m app.scripts.seed_database
```

**Create seed script** for testing:

```python
# app/scripts/seed_database.py

"""Seed database with sample data for testing."""

import asyncio
from app.db.session import async_session_maker
from app.repositories.theme_repository import ThemeRepository
from app.schemas.theme import ThemeCreate

async def seed():
    async with async_session_maker() as db:
        theme_repo = ThemeRepository()

        # Create sample themes
        themes = [
            ThemeCreate(name="Authentication Issues", description="Login/signup problems"),
            ThemeCreate(name="Performance Complaints", description="Slow load times"),
            ThemeCreate(name="Mobile UX Feedback", description="Mobile app usability"),
        ]

        for theme_data in themes:
            await theme_repo.create(db, theme_data)
        await db.commit()
        print(f"Seeded {len(themes)} themes")

if __name__ == "__main__":
    asyncio.run(seed())
```

### Phase 2: Update API Endpoints

Modify endpoints to use real database instead of mock data:

```python
# app/api/v1/themes.py (BEFORE)

@router.get("/", response_model=list[ThemeRead])
async def list_themes():
    if settings.use_mock_data:
        return MOCK_THEMES
    # Real implementation not reached
```

```python
# app/api/v1/themes.py (AFTER)

@router.get("/", response_model=list[ThemeRead])
async def list_themes(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    if settings.use_mock_data:
        return MOCK_THEMES

    # Real implementation
    themes = await theme_service.get_all(db, skip, limit)
    return themes
```

**Update all endpoints**:
- `app/api/v1/themes.py`
- `app/api/v1/feedback.py`
- `app/api/v1/customers.py`
- `app/api/v1/bets.py`

### Phase 3: Configure Environment Variables

```bash
# Set on Railway
railway variables set USE_MOCK_DATA=false

# Add connector credentials
railway variables set HUBSPOT_API_KEY="..."
railway variables set ZENDESK_EMAIL="..."
railway variables set ZENDESK_API_TOKEN="..."
railway variables set ZENDESK_SUBDOMAIN="..."

# Add AI credentials
railway variables set OPENAI_API_KEY="sk-..."

# Add Redis for caching
railway add  # Select Redis
```

### Phase 4: Initial Data Sync

Run first sync to populate database:

```bash
# Trigger sync via API (add sync endpoint)
curl -X POST https://jisrvoc-backend-production.up.railway.app/api/v1/sync/hubspot

curl -X POST https://jisrvoc-backend-production.up.railway.app/api/v1/sync/zendesk

# Monitor logs
railway logs --follow
```

### Phase 5: Enable Background Jobs

Set up automated syncing with Railway Cron (or external cron service):

```python
# app/api/v1/cron.py

from fastapi import APIRouter, Header, HTTPException

router = APIRouter(prefix="/cron", tags=["cron"])

@router.post("/sync-hubspot")
async def cron_sync_hubspot(
    authorization: str = Header(...),
    db: AsyncSession = Depends(get_db)
):
    """Railway cron endpoint for HubSpot sync."""
    # Verify cron secret
    if authorization != f"Bearer {settings.cron_secret}":
        raise HTTPException(401, "Unauthorized")

    sync_service = SyncService(db)
    connector = HubSpotConnector(settings.hubspot_api_key)

    async with connector:
        stats = await sync_service.sync_hubspot_tickets(connector)

    return {"status": "success", "stats": stats}
```

**Configure in Railway**:
```json
// railway.json
{
  "deploy": {
    "cron": [
      {
        "schedule": "0 */6 * * *",  // Every 6 hours
        "endpoint": "/api/v1/cron/sync-hubspot",
        "headers": {
          "Authorization": "${{ secrets.CRON_SECRET }}"
        }
      }
    ]
  }
}
```

### Phase 6: Testing

Test each data flow:

```bash
# 1. Verify database has data
railway connect PostgreSQL
\c railway
SELECT COUNT(*) FROM feedback;
SELECT COUNT(*) FROM themes;

# 2. Test API endpoints return real data
curl https://jisrvoc-backend-production.up.railway.app/api/v1/feedback | jq '.[:3]'

# 3. Verify AI enrichment works
# Check that new feedback gets classified
curl https://jisrvoc-backend-production.up.railway.app/api/v1/feedback/1 | jq '.classification_metadata'

# 4. Test frontend integration
open https://jisrvoc-frontend-production.up.railway.app
```

## Rollback Plan

If issues occur after switching:

### Quick Rollback: Re-enable Mock Data

```bash
# Switch back to mock data immediately
railway variables set USE_MOCK_DATA=true

# Railway auto-redeploys, app serves mock data again
```

### Full Rollback: Revert Code

```bash
# Revert the commit that switched to real data
git revert <commit-hash>

# Push to trigger redeploy
git push origin master
```

## Incremental Approach (Recommended)

Instead of switching all at once, enable real data gradually:

### Step 1: Hybrid Mode

```python
# app/api/v1/feedback.py

@router.get("/", response_model=list[FeedbackRead])
async def list_feedback(
    use_real_data: bool = False,  # Query param to toggle
    db: AsyncSession = Depends(get_db)
):
    if not use_real_data and settings.use_mock_data:
        return MOCK_FEEDBACK

    # Real data
    feedback = await feedback_service.get_all(db)
    return feedback
```

Test with: `?use_real_data=true`

### Step 2: Enable Per-Endpoint

Switch one endpoint at a time:
1. ✅ `/feedback` → Real data
2. Test thoroughly
3. ✅ `/themes` → Real data
4. Test thoroughly
5. ✅ `/customers` → Real data
6. Test thoroughly
7. ✅ `/bets` → Real data

### Step 3: Full Switch

Once all endpoints tested:
```bash
railway variables set USE_MOCK_DATA=false
```

## Monitoring After Switch

Watch for issues:

```bash
# Monitor error rates
railway logs | grep -i "error\|exception"

# Check API response times
railway logs | grep -i "duration\|latency"

# Monitor database connections
railway logs | grep -i "database\|connection"

# Check sync job success
railway logs | grep -i "sync.*complete"
```

Set up alerts for:
- API error rate > 5%
- Response time > 2 seconds
- Database connection failures
- Sync job failures

## Common Issues

### Issue 1: Empty Data After Switch

**Symptom**: API returns `[]` for all endpoints

**Solution**:
```bash
# Check if database has data
railway connect PostgreSQL
SELECT COUNT(*) FROM feedback;

# If zero, run sync manually
curl -X POST .../api/v1/sync/hubspot
```

### Issue 2: Slow API Responses

**Symptom**: Endpoints timeout or take > 5 seconds

**Solution**:
- Add database indexes (use migrations)
- Enable Redis caching
- Optimize queries (use `select_related`/`joinedload`)

### Issue 3: Classification Failing

**Symptom**: `classification_metadata` is null for all feedback

**Solution**:
```bash
# Check OpenAI API key is set
railway variables | grep OPENAI

# Check logs for API errors
railway logs | grep -i "openai\|classification"

# Test classification manually
railway run python -m app.scripts.test_classification
```

## Success Criteria

Real data mode is successful when:
- [ ] All endpoints return data from database (not mock)
- [ ] HubSpot/Zendesk sync runs without errors
- [ ] AI enrichment works (classification, embeddings, sentiment)
- [ ] API response times < 2 seconds
- [ ] No increase in error rate
- [ ] Frontend displays real data correctly
- [ ] Background jobs running on schedule

## Related Skills

- `jisrvoc-backend-context` - Backend architecture
- `connector-development` - HubSpot/Zendesk integration
- `ai-pipeline` - AI enrichment setup
- `database-migrations` - Create required tables
- `railway-deployment` - Deploy changes

## Quick Command Reference

```bash
# Check mock data status
railway variables | grep USE_MOCK_DATA

# Switch to real data
railway variables set USE_MOCK_DATA=false

# Rollback to mock data
railway variables set USE_MOCK_DATA=true

# Trigger manual sync
curl -X POST <api-url>/sync/hubspot

# Check database data
railway connect PostgreSQL
```
