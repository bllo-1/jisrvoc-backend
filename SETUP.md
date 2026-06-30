# JisrVoC Backend Setup Guide

## Phase 1 Setup - HubSpot Integration & AI Classification

### Prerequisites
- Python 3.10+
- PostgreSQL (or use Railway PostgreSQL - already configured)
- Redis (optional for background jobs)

### 1. Install Dependencies

```bash
# Activate virtual environment
source venv/bin/activate

# Install all dependencies
pip install -r requirements.txt
```

### 2. Configure API Keys

Edit `.env` file and add your API keys:

```bash
# OpenAI API Key (required)
OPENAI_API_KEY=sk-your-openai-api-key-here

# HubSpot API Key (required)
HUBSPOT_API_KEY=your-hubspot-api-key-here
```

**How to get API keys:**

- **OpenAI**: https://platform.openai.com/api-keys
- **HubSpot**: Settings → Integrations → Private Apps → Create private app
  - Required scopes: `tickets` (read), `crm.objects.contacts.read`, `crm.objects.companies.read`

### 3. Run Database Migrations

The Railway PostgreSQL database is already configured. To run migrations:

```bash
# Run migrations on Railway database
DATABASE_URL="your-railway-database-url" alembic upgrade head

# Or use the DATABASE_URL from your .env file
alembic upgrade head
```

### 4. Start the Server

```bash
# Start FastAPI server with auto-reload
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

The API will be available at: http://localhost:8000

API Documentation: http://localhost:8000/docs

### 5. Test the Integration

#### Sync HubSpot Tickets

```bash
curl -X POST http://localhost:8000/api/v1/sync/hubspot \
  -H "Content-Type: application/json" \
  -d '{
    "limit": 10
  }'
```

Expected response:
```json
{
  "message": "Successfully synced HubSpot tickets",
  "synced_count": 10,
  "source": "hubspot"
}
```

#### Classify Unclassified Feedback

```bash
curl -X POST http://localhost:8000/api/v1/classify/unclassified \
  -H "Content-Type: application/json" \
  -d '{
    "limit": 10,
    "model": "gpt-4o-mini"
  }'
```

Expected response:
```json
{
  "message": "Successfully classified unclassified feedback",
  "classified_count": 10,
  "model_used": "gpt-4o-mini"
}
```

## Available Endpoints

### Sync Endpoints

- `POST /api/v1/sync/hubspot` - Sync tickets from HubSpot
  - Body: `{ "limit": 100, "after": "cursor" }`

- `POST /api/v1/sync/zendesk` - Sync tickets from Zendesk (requires Zendesk credentials)
  - Body: `{ "limit": 100, "after": "cursor" }`

### Classification Endpoints

- `POST /api/v1/classify/unclassified` - Classify all unclassified feedback
  - Body: `{ "limit": 100, "model": "gpt-4o-mini" }`

- `POST /api/v1/classify/reclassify` - Reclassify a specific feedback item
  - Body: `{ "feedback_id": 123, "model": "gpt-4o-mini" }`

### Background Job Variants

- `POST /api/v1/sync/hubspot/background` - Queue HubSpot sync in background
- `POST /api/v1/sync/zendesk/background` - Queue Zendesk sync in background
- `POST /api/v1/classify/unclassified/background` - Queue classification in background

## Architecture Overview

```
External Sources (HubSpot/Zendesk)
           ↓
    Connectors (Rate-limited)
           ↓
  Feedback Sync Service
           ↓
   Database (PostgreSQL + pgvector)
           ↓
  Classification Service
           ↓
    OpenAI API (GPT-4o-mini)
           ↓
   Classification Storage
```

## Database Schema

### Tables

1. **feedback** - Core feedback/tickets from external sources
   - `id`, `source`, `external_id`, `title`, `content`
   - `customer_id`, `company_id`, `embedding`
   - Unique constraint on `(source, external_id)`

2. **customers** - Individual contacts/users
   - `id`, `email`, `name`, `company_id`
   - External IDs for HubSpot and Zendesk

3. **companies** - Organizations/accounts
   - `id`, `domain`, `company_name`
   - External IDs for HubSpot and Zendesk

4. **classifications** - AI-generated classifications
   - `id`, `feedback_id`, `sentiment`, `category`
   - `topics`, `summary`, `model_used`

## Troubleshooting

### Database Connection Issues

```bash
# Test database connection
psql "your-railway-database-url"

# Check if migrations are up to date
alembic current
alembic history
```

### API Key Issues

```bash
# Verify API keys are loaded
python -c "from app.core.config import settings; print(f'OpenAI: {settings.openai_api_key[:10]}...')"
```

### HubSpot Rate Limits

The HubSpot connector includes automatic rate limiting (10 req/sec). If you hit rate limits:
- Reduce `limit` parameter in sync requests
- Wait before retrying
- Check HubSpot API usage in your HubSpot account

## Next Steps

1. **Set up scheduled syncs** - Use cron jobs or Celery to sync periodically
2. **Add webhooks** - Real-time sync when new tickets are created
3. **Implement embedding generation** - Add vector search for similar feedback
4. **Deploy to production** - Railway deployment guide coming soon

## Support

For issues or questions:
- Check the API documentation: http://localhost:8000/docs
- Review logs: Check console output for errors
- Database queries: Use Railway's PostgreSQL dashboard
