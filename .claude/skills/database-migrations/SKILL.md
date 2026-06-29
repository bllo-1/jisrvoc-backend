---
name: alembic-migration-workflow
description: Create and apply Alembic migrations for JisrVoC database schema changes with testing and rollback procedures
---

# Database Migrations with Alembic

## When to Use This Skill

Use when you need to:
- Add new tables or columns to the database
- Modify existing schema (change column types, add constraints)
- Create indexes for performance
- Apply database changes to production
- Rollback migrations if issues occur

## Setup (Already Complete)

Alembic is configured in the backend:
- Config: `alembic.ini`
- Migrations dir: `app/db/migrations/`
- Environment: `app/db/migrations/env.py`

## Workflow

### Step 1: Create Migration

```bash
cd /Users/jisr4/Desktop/JisrVoC/jisrvoc-backend

# Activate virtual environment
source venv/bin/activate

# Auto-generate migration from model changes
alembic revision --autogenerate -m "add embeddings to feedback table"

# Or create empty migration for manual SQL
alembic revision -m "add custom indexes"
```

**Naming Convention**: `YYYYMMDD_short_description`
Example: `20260629_add_embeddings_column`

### Step 2: Review Generated Migration

```python
# app/db/migrations/versions/20260629_add_embeddings.py

"""add embeddings to feedback table

Revision ID: abc123
Create Date: 2026-06-29
"""

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

def upgrade() -> None:
    # Add vector column for embeddings
    op.add_column('feedback',
        sa.Column('embedding', Vector(1536), nullable=True)
    )
    # Add index for vector similarity search
    op.execute('CREATE INDEX idx_feedback_embedding ON feedback USING ivfflat (embedding vector_cosine_ops)')

def downgrade() -> None:
    op.drop_index('idx_feedback_embedding')
    op.drop_column('feedback', 'embedding')
```

**Review Checklist**:
- [ ] Upgrade logic is correct
- [ ] Downgrade reverses all changes
- [ ] Indexes added where needed
- [ ] No data loss in downgrade
- [ ] Foreign key constraints handled

### Step 3: Test Migration Locally

```bash
# Check current database revision
alembic current

# Test upgrade
alembic upgrade head

# Verify schema changes
psql $DATABASE_URL -c "\d feedback"

# Test downgrade
alembic downgrade -1

# Verify rollback worked
alembic upgrade head
```

### Step 4: Deploy to Railway

```bash
# Commit migration file
git add app/db/migrations/versions/*.py
git commit -m "feat: add embeddings column to feedback

Migration adds vector embedding storage for similarity search.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"

# Push (Railway auto-deploys)
git push origin master
```

**Railway will automatically run migrations on startup** if configured in `start.sh`:

```bash
# start.sh
#!/bin/bash
alembic upgrade head  # Run migrations first
exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
```

### Step 5: Verify Production Migration

```bash
# Check logs for migration success
railway logs | grep -i "alembic\|migration"

# Expected output:
# INFO [alembic.runtime.migration] Running upgrade -> abc123, add embeddings to feedback table
# INFO [alembic.runtime.migration] Context impl PostgresqlImpl.

# Test API to ensure app still works
curl https://jisrvoc-backend-production.up.railway.app/api/v1/healthz
```

## Common Migration Patterns

### Adding a New Table

```python
def upgrade():
    op.create_table(
        'themes',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('feedback_count', sa.Integer(), default=0),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), onupdate=sa.func.now())
    )
    op.create_index('ix_themes_name', 'themes', ['name'])

def downgrade():
    op.drop_index('ix_themes_name')
    op.drop_table('themes')
```

### Adding Foreign Key

```python
def upgrade():
    op.add_column('feedback', sa.Column('theme_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_feedback_theme',
        'feedback', 'themes',
        ['theme_id'], ['id'],
        ondelete='SET NULL'
    )

def downgrade():
    op.drop_constraint('fk_feedback_theme', 'feedback', type_='foreignkey')
    op.drop_column('feedback', 'theme_id')
```

### Data Migration

```python
from sqlalchemy.sql import table, column

def upgrade():
    # Add new column
    op.add_column('feedback', sa.Column('status', sa.String(20), nullable=True))

    # Migrate existing data
    feedback = table('feedback', column('status'))
    op.execute(feedback.update().values(status='active'))

    # Make column non-nullable after backfill
    op.alter_column('feedback', 'status', nullable=False)

def downgrade():
    op.drop_column('feedback', 'status')
```

## Rollback Procedures

### Immediate Rollback (Production Issue)

```bash
# Check current revision
railway run alembic current

# Rollback one revision
railway run alembic downgrade -1

# Or rollback to specific revision
railway run alembic downgrade abc123

# Restart service
railway restart
```

### Git-Based Rollback

```bash
# Revert the migration commit
git revert <commit-hash>

# Push (triggers redeploy without migration)
git push origin master
```

## Troubleshooting

### Issue: Migration Fails on Deploy

**Symptom**: Logs show `alembic.util.exc.CommandError`

**Solutions**:
1. Check Railway logs for specific error
2. Test migration locally with same Postgres version
3. Ensure `DATABASE_URL` uses `postgresql+asyncpg://`

### Issue: Downgrade Fails

**Symptom**: `Can't drop column, other objects depend on it`

**Solution**: Add cascade in downgrade:
```python
def downgrade():
    op.drop_constraint('fk_name', 'table', type_='foreignkey')
    op.drop_column('table', 'column')
```

### Issue: Auto-generate Misses Changes

**Symptom**: `alembic revision --autogenerate` doesn't detect model changes

**Solutions**:
- Ensure models are imported in `app/db/base.py`
- Check `target_metadata` in `env.py` points to Base.metadata
- Manually create migration if auto-generate fails

## Best Practices

- **Test locally first**: Always run upgrade/downgrade locally
- **Small migrations**: One logical change per migration
- **Reversible**: Every upgrade must have working downgrade
- **No data loss**: Backfill data before making columns NOT NULL
- **Index performance**: Add indexes in separate migrations for large tables
- **Coordinate with deploys**: Run migrations during low-traffic periods

## Success Criteria

Migration is successful when:
- [ ] Upgrade runs without errors
- [ ] Downgrade reverses all changes
- [ ] API functionality unaffected
- [ ] No data loss
- [ ] Production deployment succeeds
- [ ] Application logs show no database errors

## Related Skills

- `jisrvoc-backend-context` - Backend architecture
- `railway-deployment` - Deploy with migrations
- `mock-to-real-data` - Create tables for real data

## Quick Reference

```bash
# Create migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback one
alembic downgrade -1

# Check current
alembic current

# Show history
alembic history

# Rollback to specific revision
alembic downgrade <revision_id>
```
