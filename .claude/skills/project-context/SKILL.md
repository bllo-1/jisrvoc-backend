---
name: jisrvoc-backend-context
description: JisrVoC backend architecture, tech stack (FastAPI, SQLAlchemy), and project conventions for Voice of Customer analytics
---

# JisrVoC Backend Project Context

## Overview

**JisrVoC** (Jisr Voice of Customer) is an AI-powered platform for analyzing customer feedback from multiple sources (HubSpot, Zendesk, Canny) to identify themes, generate product insights, and recommend strategic bets.

**Current Status:** MVP deployed on Railway with mock data mode enabled.

## When to Use This Skill

**Always load this skill first** when working on backend tasks. This provides essential context about:
- System architecture and design patterns
- Tech stack and dependencies
- Current project state and phase
- Development conventions and standards

## System Architecture

### Three-Layer Pattern

```
┌─────────────────────────────────────────┐
│         API Layer (FastAPI)             │
│   Routes → Endpoints → Request/Response │
└─────────────┬───────────────────────────┘
              │
┌─────────────▼───────────────────────────┐
│         Service Layer                    │
│   Business Logic → Orchestration        │
└─────────────┬───────────────────────────┘
              │
┌─────────────▼───────────────────────────┐
│      Repository Layer (SQLAlchemy)      │
│   Data Access → Database Operations     │
└─────────────────────────────────────────┘
```

### Directory Structure

```
app/
├── main.py                 # FastAPI application entry point
├── core/
│   ├── config.py          # Environment variables, settings
│   ├── deps.py            # Dependency injection (DB sessions)
│   └── security.py        # JWT auth, password hashing
├── api/v1/
│   ├── __init__.py
│   ├── themes.py          # Theme endpoints
│   ├── feedback.py        # Feedback endpoints
│   ├── customers.py       # Customer endpoints
│   └── bets.py            # Product bet endpoints
├── models/
│   ├── theme.py           # SQLAlchemy models
│   ├── feedback.py
│   ├── customer.py
│   └── bet.py
├── schemas/
│   ├── theme.py           # Pydantic schemas (request/response)
│   ├── feedback.py
│   ├── customer.py
│   └── bet.py
├── services/
│   ├── theme_service.py   # Business logic
│   ├── feedback_service.py
│   ├── customer_service.py
│   └── bet_service.py
├── repositories/
│   ├── theme_repository.py    # Database operations
│   ├── feedback_repository.py
│   ├── customer_repository.py
│   └── bet_repository.py
├── connectors/            # (Future) External API integrations
│   ├── hubspot.py
│   ├── zendesk.py
│   └── canny.py
├── ai/                    # (Future) AI/ML pipeline
│   ├── llm_provider.py    # OpenAI/Vertex AI abstraction
│   ├── embeddings.py
│   ├── classification.py
│   └── clustering.py
└── db/
    ├── base.py            # SQLAlchemy base
    ├── session.py         # Database session management
    └── migrations/        # Alembic migrations
```

## Tech Stack

### Core Framework
- **FastAPI 0.115+**: Modern async web framework
- **Python 3.11+**: Type hints, async/await
- **Uvicorn**: ASGI server

### Database & ORM
- **PostgreSQL 15+**: Primary database
- **SQLAlchemy 2.0+**: Async ORM
- **Alembic**: Database migrations
- **asyncpg**: PostgreSQL async driver

### Validation & Serialization
- **Pydantic V2**: Request/response validation
- **Python-multipart**: File upload support

### Authentication (Phase 1)
- **python-jose**: JWT tokens
- **passlib[bcrypt]**: Password hashing

### External Integrations (Phase 1-2)
- **httpx**: Async HTTP client
- **hubspot-api-client**: HubSpot SDK
- **zenpy**: Zendesk SDK
- **openai**: OpenAI API client (testing phase)

### AI/ML (Phase 2)
- **numpy**: Numerical operations
- **scikit-learn**: Clustering (HDBSCAN)
- **OpenAI API**: Classification, embeddings, sentiment (testing)
- **Vertex AI**: Production LLM (migration target)

### Development Tools
- **pytest**: Testing framework
- **pytest-asyncio**: Async test support
- **httpx**: Test client for FastAPI
- **black**: Code formatting
- **mypy**: Type checking

## Current State

### Deployment
- **Platform**: Railway (US/EU regions)
- **Database**: Railway PostgreSQL addon
- **Environment**: Production environment active
- **URLs**:
  - API: https://jisrvoc-backend-production.up.railway.app
  - Health: /api/v1/healthz
  - Docs: /docs (Swagger UI)

### Mode
```python
# app/core/config.py
USE_MOCK_DATA = True  # Currently using mock data
```

**Mock Data Active**: All endpoints return hardcoded sample data (10 themes, 20 feedback items, 8 customers, 8 bets).

**Phase 1 Goal**: Switch to `USE_MOCK_DATA=False` with real database and API integrations.

### API Endpoints (Current)

| Endpoint | Method | Description | Status |
|----------|--------|-------------|--------|
| `/api/v1/healthz` | GET | Health check | ✅ Live |
| `/api/v1/themes` | GET | List themes | ✅ Mock |
| `/api/v1/feedback` | GET | List feedback | ✅ Mock |
| `/api/v1/customers` | GET | List customers | ✅ Mock |
| `/api/v1/bets` | GET | List product bets | ✅ Mock |

## Development Conventions

### Code Style

1. **Naming**:
   - `snake_case` for variables, functions, file names
   - `PascalCase` for classes
   - `UPPER_SNAKE_CASE` for constants

2. **Type Hints**:
   ```python
   # Always use type hints
   async def get_theme(theme_id: int, db: AsyncSession) -> Theme | None:
       return await theme_repository.get_by_id(db, theme_id)
   ```

3. **Async/Await**:
   - All database operations must be async
   - Use `async def` and `await` consistently
   ```python
   # Good
   async def create_feedback(db: AsyncSession, data: FeedbackCreate) -> Feedback:
       return await feedback_repository.create(db, data)

   # Bad (don't mix sync/async)
   def create_feedback(db: Session, data: FeedbackCreate) -> Feedback:
       return feedback_repository.create(db, data)
   ```

4. **Error Handling**:
   ```python
   from fastapi import HTTPException, status

   if not theme:
       raise HTTPException(
           status_code=status.HTTP_404_NOT_FOUND,
           detail=f"Theme {theme_id} not found"
       )
   ```

### API Patterns

1. **Router Structure**:
   ```python
   from fastapi import APIRouter, Depends
   from sqlalchemy.ext.asyncio import AsyncSession
   from app.core.deps import get_db

   router = APIRouter(prefix="/themes", tags=["themes"])

   @router.get("/", response_model=list[ThemeRead])
   async def list_themes(
       skip: int = 0,
       limit: int = 100,
       db: AsyncSession = Depends(get_db)
   ):
       themes = await theme_service.get_all(db, skip, limit)
       return themes
   ```

2. **Dependency Injection**:
   ```python
   # Use Depends() for database sessions
   async def get_db() -> AsyncGenerator[AsyncSession, None]:
       async with async_session_maker() as session:
           yield session
   ```

3. **Pydantic Schemas**:
   ```python
   # Separate schemas for Create, Update, Read
   class ThemeBase(BaseModel):
       name: str
       description: str | None = None

   class ThemeCreate(ThemeBase):
       pass

   class ThemeRead(ThemeBase):
       id: int
       feedback_count: int
       created_at: datetime

       model_config = ConfigDict(from_attributes=True)
   ```

### Database Patterns

1. **Models**:
   ```python
   from sqlalchemy import Column, Integer, String, DateTime
   from sqlalchemy.orm import relationship
   from app.db.base import Base

   class Theme(Base):
       __tablename__ = "themes"

       id = Column(Integer, primary_key=True, index=True)
       name = Column(String, nullable=False, index=True)
       created_at = Column(DateTime, default=datetime.utcnow)

       # Relationships
       feedback = relationship("Feedback", back_populates="theme")
   ```

2. **Repository Pattern**:
   ```python
   class ThemeRepository:
       async def get_by_id(self, db: AsyncSession, theme_id: int) -> Theme | None:
           result = await db.execute(
               select(Theme).where(Theme.id == theme_id)
           )
           return result.scalar_one_or_none()

       async def create(self, db: AsyncSession, obj_in: ThemeCreate) -> Theme:
           db_obj = Theme(**obj_in.model_dump())
           db.add(db_obj)
           await db.commit()
           await db.refresh(db_obj)
           return db_obj
   ```

### Testing Patterns

1. **Async Tests**:
   ```python
   import pytest
   from httpx import AsyncClient
   from app.main import app

   @pytest.mark.asyncio
   async def test_get_themes():
       async with AsyncClient(app=app, base_url="http://test") as ac:
           response = await ac.get("/api/v1/themes")
       assert response.status_code == 200
       assert len(response.json()) > 0
   ```

2. **Fixtures**:
   ```python
   @pytest.fixture
   async def db_session():
       async with async_session_maker() as session:
           yield session
           await session.rollback()
   ```

## Railway Configuration

### Environment Variables

```bash
# Required
DATABASE_URL=postgresql+asyncpg://user:pass@host:port/db
PORT=8000

# Feature Flags
USE_MOCK_DATA=true  # Switch to false in Phase 1

# Auth (Phase 1)
SECRET_KEY=<generate-with-openssl>
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# OpenAI (Phase 1-3)
OPENAI_API_KEY=sk-...

# HubSpot (Phase 1)
HUBSPOT_API_KEY=...

# Zendesk (Phase 1)
ZENDESK_EMAIL=...
ZENDESK_API_TOKEN=...
ZENDESK_SUBDOMAIN=...
```

### Deployment Files

- **`railway.json`**: Build and start command configuration
- **`start.sh`**: Startup script binding to $PORT
- **`requirements.txt`**: Python dependencies
- **`runtime.txt`**: Python version specification

## Phase Roadmap Context

### Current: MVP Complete
- ✅ Basic API structure with mock data
- ✅ Railway deployment working
- ✅ Health checks and monitoring

### Next: Phase 0 (Decisions - Week 1)
- Document architecture decisions
- Set up LLM provider abstraction
- Map HubSpot/Zendesk fields

### Then: Phase 1 (Foundation - Weeks 2-5)
- Switch from mock to real database
- Build HubSpot/Zendesk connectors
- Implement OpenAI enrichment pipeline
- Add authentication system

### Future: Phases 2-5
- AI clustering and theme generation
- Dashboard optimization
- HubSpot write-back
- Production migration to GCP

## Related Skills

- `railway-deployment` - Deploy backend to Railway
- `database-migrations` - Create and apply Alembic migrations
- `connector-development` - Build external API connectors
- `ai-pipeline` - Integrate LLM for enrichment
- `mock-to-real-data` - Switch from mock to real data

## Key Files to Reference

- `/BACKEND_PLAN.md` - Complete implementation roadmap
- `/app/core/config.py` - Configuration and environment variables
- `/app/main.py` - FastAPI app initialization
- `/requirements.txt` - Dependencies

## Success Criteria

You understand the backend architecture when you can:
- [ ] Explain the three-layer pattern (API → Service → Repository)
- [ ] Identify whether code should be async or sync
- [ ] Know where to add new endpoints (api/v1/)
- [ ] Know where to add business logic (services/)
- [ ] Know where to add database operations (repositories/)
- [ ] Understand mock vs real data mode
- [ ] Reference Railway configuration requirements
