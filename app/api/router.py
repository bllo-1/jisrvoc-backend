"""
API Router - Phase 3 Configuration

This file demonstrates how to switch to Phase 3 routes.
After running migrations, rename this file to router.py to activate Phase 3.
"""

from fastapi import APIRouter
from .routes import (
    overview_phase3,  # Phase 3 - production-ready aggregations
    feedback_new,  # Phase 1 - uses legacy feedback table (ACTIVE)
    themes_new,
    bets_new,
    customers_new,
    admin_new,
    webhooks_new,
    sync,
    classify,
    connectors,
    enrichment,
    clustering,
    intelligence,
)

api_router = APIRouter()

# ==================== Phase 1 Routes (ACTIVE) ====================
# These routes use the Phase 1 schema (feedback, customers tables)
# Phase 3 routes will be activated after migration

api_router.include_router(overview_phase3.router, prefix="/overview", tags=["Overview"])
api_router.include_router(feedback_new.router, prefix="/feedback", tags=["Feedback"])

# ==================== Existing Routes ====================
api_router.include_router(themes_new.router, prefix="/themes", tags=["Themes"])
api_router.include_router(bets_new.router, prefix="/bets", tags=["Bets"])
api_router.include_router(customers_new.router, prefix="/customers", tags=["Customers"])

# Admin endpoints
api_router.include_router(admin_new.router, prefix="/admin", tags=["Admin"])

# Data sync and classification endpoints
api_router.include_router(sync.router, tags=["Sync"])
api_router.include_router(classify.router, tags=["Classification"])
api_router.include_router(connectors.router, tags=["Connectors"])
api_router.include_router(enrichment.router, tags=["Enrichment"])

# Phase 2 - Intelligence Layer endpoints
api_router.include_router(clustering.router, tags=["Clustering"])
api_router.include_router(intelligence.router, tags=["Intelligence"])

# Public webhooks (these should be mounted at /api/public/webhooks, not /api/v1/webhooks)
# Handled separately in main.py


# ==================== Migration Notes ====================
#
# To activate Phase 3 routes:
# 1. Run migrations: `alembic upgrade head`
# 2. Verify schema: `psql jisrvoc -c "\dt"`
# 3. Rename this file: `mv router_phase3.py router.py`
# 4. Restart server
# 5. Test endpoints:
#    - GET /api/v1/overview/metrics
#    - GET /api/v1/feedback?area=payroll&urgency=high
#
# Rollback:
# 1. Restore old router: `git checkout router.py`
# 2. Restart server
