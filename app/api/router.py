from fastapi import APIRouter
from .routes import (
    overview_new,
    feedback_new,
    themes_new,
    bets_new,
    customers_new,
    admin_new,
    webhooks_new,
)

api_router = APIRouter()

# Core domain endpoints
api_router.include_router(overview_new.router, prefix="/overview", tags=["Overview"])
api_router.include_router(feedback_new.router, prefix="/feedback", tags=["Feedback"])
api_router.include_router(themes_new.router, prefix="/themes", tags=["Themes"])
api_router.include_router(bets_new.router, prefix="/bets", tags=["Bets"])
api_router.include_router(customers_new.router, prefix="/customers", tags=["Customers"])

# Admin endpoints (no prefix - /admin/* paths are in the route file)
api_router.include_router(admin_new.router, prefix="/admin", tags=["Admin"])

# Public webhooks (these should be mounted at /api/public/webhooks, not /api/v1/webhooks)
# Handled separately in main.py
