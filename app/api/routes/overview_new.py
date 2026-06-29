"""
Overview API endpoints - dashboard metrics and aggregations.
Matches frontend contract from jisrvoc-frontend/src/lib/api/overview.ts
"""
from fastapi import APIRouter
from typing import List
from ...schemas_new import OverviewMetrics, Theme, UrgencyDistribution
from ... import mock_data

router = APIRouter()


@router.get("/metrics", response_model=OverviewMetrics)
async def get_metrics():
    """
    @endpoint GET /api/v1/overview/metrics
    Returns dashboard KPIs and distributions.
    """
    return OverviewMetrics(
        total_feedback=mock_data.TOTAL_FEEDBACK_COUNT,
        active_themes=len(mock_data.THEMES),
        high_urgency_open=mock_data.URGENCY_DISTRIBUTION["High"],
        bets_in_flight=len([b for b in mock_data.BETS if b.status.value not in ["Shipped", "Declined"]]),
        weekly_volume=mock_data.WEEKLY_VOLUME,
        source_breakdown=mock_data.SOURCE_BREAKDOWN,
        product_area_breakdown=mock_data.PRODUCT_AREA_BREAKDOWN,
        urgency_distribution=UrgencyDistribution(
            low=mock_data.URGENCY_DISTRIBUTION["Low"],
            medium=mock_data.URGENCY_DISTRIBUTION["Medium"],
            high=mock_data.URGENCY_DISTRIBUTION["High"],
        ),
    )


@router.get("/top-themes", response_model=List[Theme])
async def get_top_themes(limit: int = 5):
    """
    @endpoint GET /api/v1/overview/top-themes?limit=5
    Returns top themes sorted by item count.
    """
    sorted_themes = sorted(mock_data.THEMES, key=lambda t: t.item_count, reverse=True)
    return sorted_themes[:limit]
