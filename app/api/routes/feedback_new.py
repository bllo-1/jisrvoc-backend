"""
Feedback API endpoints - item listing, enrichment, tagging.
Matches frontend contract from jisrvoc-frontend/src/lib/api/feedback.ts
"""
from fastapi import APIRouter, Query
from typing import Optional, List
from ...schemas_new import (
    FeedbackItem,
    FeedbackPage,
    EnrichmentMeta,
    FeedbackTagEdit,
    Category,
    ProductArea,
    Sentiment,
    Urgency,
    Source,
    Segment,
)
from ... import mock_data

router = APIRouter()


@router.get("", response_model=FeedbackPage)
async def list_feedback(
    cursor: Optional[str] = None,
    limit: int = Query(20, le=100),
    category: Optional[Category] = None,
    product_area: Optional[ProductArea] = None,
    sentiment: Optional[Sentiment] = None,
    urgency: Optional[Urgency] = None,
    source: Optional[Source] = None,
    segment: Optional[Segment] = None,
    theme_id: Optional[str] = None,
    customer_id: Optional[str] = None,
):
    """
    @endpoint GET /api/v1/feedback
    Returns paginated feedback with optional filters.
    """
    # Start with all feedback
    filtered = list(mock_data.FEEDBACK)

    # Apply filters
    if category:
        filtered = [f for f in filtered if f.category == category]
    if product_area:
        filtered = [f for f in filtered if f.product_area == product_area]
    if sentiment:
        filtered = [f for f in filtered if f.sentiment == sentiment]
    if urgency:
        filtered = [f for f in filtered if f.urgency == urgency]
    if source:
        filtered = [f for f in filtered if f.source == source]
    if segment:
        filtered = [f for f in filtered if f.segment == segment]
    if theme_id:
        filtered = [f for f in filtered if f.theme_id == theme_id]
    if customer_id:
        filtered = [f for f in filtered if f.customer_id == customer_id]

    # Sort by date descending (newest first)
    filtered.sort(key=lambda f: f.date, reverse=True)

    # Cursor pagination (simplified for mock)
    start_idx = 0
    if cursor:
        # Cursor format: "idx-{number}"
        try:
            start_idx = int(cursor.split("-")[1])
        except (IndexError, ValueError):
            start_idx = 0

    page_items = filtered[start_idx:start_idx + limit]
    next_cursor = None
    if start_idx + limit < len(filtered):
        next_cursor = f"idx-{start_idx + limit}"

    return FeedbackPage(
        items=page_items,
        next_cursor=next_cursor,
        total=len(filtered),
    )


@router.get("/{feedback_id}", response_model=FeedbackItem)
async def get_feedback(feedback_id: str):
    """
    @endpoint GET /api/v1/feedback/:id
    Returns single feedback item by ID.
    """
    item = next((f for f in mock_data.FEEDBACK if f.id == feedback_id), None)
    if not item:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Feedback {feedback_id} not found")
    return item


@router.get("/{feedback_id}/enrichment", response_model=EnrichmentMeta)
async def get_enrichment(feedback_id: str):
    """
    @endpoint GET /api/v1/feedback/:id/enrichment
    Returns AI enrichment metadata for a feedback item.
    """
    # Verify feedback exists
    item = next((f for f in mock_data.FEEDBACK if f.id == feedback_id), None)
    if not item:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Feedback {feedback_id} not found")

    # Mock enrichment metadata
    return EnrichmentMeta(
        model="claude-sonnet-4",
        model_version="20250514",
        confidence=0.89,
        pm_corrected=False,
    )


@router.patch("/{feedback_id}/tags", response_model=FeedbackItem)
async def update_tags(feedback_id: str, edits: FeedbackTagEdit):
    """
    @endpoint PATCH /api/v1/feedback/:id/tags
    Updates enrichment tags (category, product_area, sentiment, urgency).
    In production, this would update DB and trigger enrichment metadata update.
    """
    # Find the item in mock data
    item = next((f for f in mock_data.FEEDBACK if f.id == feedback_id), None)
    if not item:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Feedback {feedback_id} not found")

    # Apply edits (in mock mode, we create a copy with updates)
    updated_data = item.model_dump()
    if edits.category is not None:
        updated_data["category"] = edits.category
    if edits.product_area is not None:
        updated_data["product_area"] = edits.product_area
    if edits.sentiment is not None:
        updated_data["sentiment"] = edits.sentiment
    if edits.urgency is not None:
        updated_data["urgency"] = edits.urgency

    updated_item = FeedbackItem(**updated_data)

    # In production, this would:
    # 1. Update the database
    # 2. Create EnrichmentMeta record with pm_corrected=True
    # 3. Trigger re-clustering if category/product_area changed

    return updated_item


@router.get("/parent/{raw_ticket_ref}", response_model=List[FeedbackItem])
async def get_siblings(raw_ticket_ref: str):
    """
    @endpoint GET /api/v1/feedback/parent/:rawTicketRef
    Returns all feedback items that were split from the same parent ticket.
    Used for showing related split items in the UI.
    """
    # Find items where split_from matches the reference
    siblings = [f for f in mock_data.FEEDBACK if f.split_from == raw_ticket_ref]

    # Also include any item that has this source_ref as its parent
    parent = next((f for f in mock_data.FEEDBACK if f.source_ref == raw_ticket_ref), None)
    if parent:
        siblings.append(parent)

    # Sort by ID for consistent ordering
    siblings.sort(key=lambda f: f.id)

    return siblings
