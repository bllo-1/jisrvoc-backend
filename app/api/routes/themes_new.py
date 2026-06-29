"""
Themes API endpoints - clustering, trends, merging.
Matches frontend contract from jisrvoc-frontend/src/lib/api/themes.ts
"""
from fastapi import APIRouter, Query
from typing import Optional, List
from ...schemas_new import (
    Theme,
    FeedbackItem,
    VoteTrendPoint,
    ThemeMergeRequest,
    ThemeMergeResponse,
    ThemeRenameRequest,
    ProductArea,
    Segment,
)
from ... import mock_data
from datetime import datetime, timedelta

router = APIRouter()


@router.get("", response_model=List[Theme])
async def list_themes(
    product_area: Optional[ProductArea] = None,
    segment: Optional[Segment] = None,
    min_votes: Optional[int] = None,
):
    """
    @endpoint GET /api/v1/themes
    Returns all themes with optional filters.
    """
    filtered = list(mock_data.THEMES)

    # Apply filters
    if product_area:
        filtered = [t for t in filtered if t.product_area == product_area]
    if segment:
        filtered = [t for t in filtered if segment in t.segments]
    if min_votes is not None:
        filtered = [t for t in filtered if t.vote_weight >= min_votes]

    # Sort by vote_weight descending (most important first)
    filtered.sort(key=lambda t: t.vote_weight, reverse=True)

    return filtered


@router.get("/{theme_id}", response_model=Theme)
async def get_theme(theme_id: str):
    """
    @endpoint GET /api/v1/themes/:id
    Returns single theme by ID.
    """
    theme = next((t for t in mock_data.THEMES if t.id == theme_id), None)
    if not theme:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Theme {theme_id} not found")
    return theme


@router.get("/{theme_id}/items", response_model=List[FeedbackItem])
async def get_theme_items(theme_id: str):
    """
    @endpoint GET /api/v1/themes/:id/items
    Returns all feedback items clustered under this theme.
    """
    # Verify theme exists
    theme = next((t for t in mock_data.THEMES if t.id == theme_id), None)
    if not theme:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Theme {theme_id} not found")

    # Get feedback items for this theme
    items = mock_data.get_feedback_for_theme(theme_id)

    # Sort by date descending
    items.sort(key=lambda f: f.date, reverse=True)

    return items


@router.get("/{theme_id}/trend", response_model=List[VoteTrendPoint])
async def get_theme_trend(theme_id: str, weeks: int = Query(8, le=52)):
    """
    @endpoint GET /api/v1/themes/:id/trend?weeks=8
    Returns weekly vote counts for the last N weeks.
    Used for sparkline visualization.
    """
    # Verify theme exists
    theme = next((t for t in mock_data.THEMES if t.id == theme_id), None)
    if not theme:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Theme {theme_id} not found")

    # Get all feedback for this theme
    items = mock_data.get_feedback_for_theme(theme_id)

    # Generate weekly buckets
    today = datetime.now().date()
    weekly_counts = {}

    for i in range(weeks):
        week_start = today - timedelta(days=today.weekday()) - timedelta(weeks=i)
        weekly_counts[week_start.isoformat()] = 0

    # Count items per week
    for item in items:
        item_date = datetime.fromisoformat(item.date).date()
        item_week = item_date - timedelta(days=item_date.weekday())
        week_key = item_week.isoformat()
        if week_key in weekly_counts:
            weekly_counts[week_key] += 1

    # Convert to response format
    trend_points = [
        VoteTrendPoint(week=week, votes=count)
        for week, count in sorted(weekly_counts.items())
    ]

    return trend_points


@router.post("/{theme_id}/merge", response_model=ThemeMergeResponse)
async def merge_themes(theme_id: str, request: ThemeMergeRequest):
    """
    @endpoint POST /api/v1/themes/:id/merge
    Merges source theme into target theme.
    Reassigns all feedback items and deletes source theme.
    In production, this triggers re-clustering and vote recalculation.
    """
    source_id = request.source_id
    target_id = request.target_id

    # Verify both themes exist
    source = next((t for t in mock_data.THEMES if t.id == source_id), None)
    target = next((t for t in mock_data.THEMES if t.id == target_id), None)

    if not source:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Source theme {source_id} not found")
    if not target:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Target theme {target_id} not found")

    # Get items from source theme
    source_items = mock_data.get_feedback_for_theme(source_id)

    # In production, this would:
    # 1. UPDATE feedback SET theme_id = target_id WHERE theme_id = source_id
    # 2. Recalculate target theme vote_weight, customer_count, segments
    # 3. DELETE source theme
    # 4. Trigger bet reassignment if source had bet_id

    return ThemeMergeResponse(
        merged_into=target_id,
        released_items=len(source_items),
        source_id=source_id,
    )


@router.patch("/{theme_id}", response_model=Theme)
async def rename_theme(theme_id: str, request: ThemeRenameRequest):
    """
    @endpoint PATCH /api/v1/themes/:id
    Updates theme name and/or description.
    """
    theme = next((t for t in mock_data.THEMES if t.id == theme_id), None)
    if not theme:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Theme {theme_id} not found")

    # Apply edits (in mock mode, we create a copy with updates)
    updated_data = theme.model_dump()
    if request.name is not None:
        updated_data["name"] = request.name
    if request.description is not None:
        updated_data["description"] = request.description

    updated_theme = Theme(**updated_data)

    # In production, this would UPDATE the database

    return updated_theme
