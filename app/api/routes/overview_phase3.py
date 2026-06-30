"""Overview routes for dashboard metrics - Phase 3 implementation."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.analytics import AnalyticsService
from app.schemas import OverviewMetrics, TrendPoint, CountBucket, ThemeSummary

router = APIRouter()


@router.get("/metrics", response_model=OverviewMetrics)
async def metrics(db: AsyncSession = Depends(get_db)):
    """Get overview dashboard metrics.

    Returns total feedback count, active themes, high urgency items,
    bets in flight, and urgency distribution.
    """
    analytics = AnalyticsService(db)
    try:
        return await analytics.get_overview_metrics()
    finally:
        await analytics.close()


@router.get("/volume-trend", response_model=list[TrendPoint])
async def volume_trend(weeks: int = 12, db: AsyncSession = Depends(get_db)):
    """Get feedback volume trend by week.

    Args:
        weeks: Number of weeks to look back (default: 12)

    Returns:
        List of TrendPoint with week_start and count
    """
    analytics = AnalyticsService(db)
    try:
        return await analytics.get_volume_trend(weeks)
    finally:
        await analytics.close()


@router.get("/by-source", response_model=list[CountBucket])
async def by_source(db: AsyncSession = Depends(get_db)):
    """Get feedback distribution by source type.

    Returns:
        List of CountBucket with source key and count
    """
    analytics = AnalyticsService(db)
    try:
        return await analytics.get_by_source_distribution()
    finally:
        await analytics.close()


@router.get("/by-product-area", response_model=list[CountBucket])
async def by_product_area(db: AsyncSession = Depends(get_db)):
    """Get feedback distribution by product area.

    Returns:
        List of CountBucket with area key and count
    """
    analytics = AnalyticsService(db)
    try:
        return await analytics.get_by_area_distribution()
    finally:
        await analytics.close()


@router.get("/top-themes", response_model=list[ThemeSummary])
async def top_themes(limit: int = 5, db: AsyncSession = Depends(get_db)):
    """Get top themes by vote weight.

    Args:
        limit: Maximum number of themes (default: 5)

    Returns:
        List of ThemeSummary
    """
    analytics = AnalyticsService(db)
    try:
        return await analytics.get_top_themes(limit)
    finally:
        await analytics.close()
