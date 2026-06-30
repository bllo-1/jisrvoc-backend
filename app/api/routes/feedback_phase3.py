"""Feedback routes with complex filtering - Phase 3 implementation."""

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from typing import Optional

from app.db.session import get_db
from app.repositories.feedback_item import FeedbackItemRepository
from app.models.feedback_item import (
    FeedbackCategory,
    ProductArea,
    Sentiment,
    Urgency,
    Language,
    Segment
)
from app.schemas import FeedbackPage, FeedbackItem, FeedbackDetail, TagCorrection

router = APIRouter()


@router.get("", response_model=FeedbackPage)
async def list_feedback(
    source: Optional[str] = None,
    area: Optional[ProductArea] = None,
    category: Optional[FeedbackCategory] = None,
    sentiment: Optional[Sentiment] = None,
    urgency: Optional[Urgency] = None,
    language: Optional[Language] = None,
    segment: Optional[Segment] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    q: Optional[str] = None,
    cursor: Optional[str] = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db)
):
    """List feedback with complex multi-dimensional filtering and cursor pagination.

    Args:
        source: Filter by source type (hubspot, zendesk, canny, jira)
        area: Filter by product area
        category: Filter by feedback category
        sentiment: Filter by sentiment
        urgency: Filter by urgency level
        language: Filter by language
        segment: Filter by customer segment
        date_from: Filter by start date (ISO 8601)
        date_to: Filter by end date (ISO 8601)
        q: Full-text search query on summary_en
        cursor: Cursor for pagination (ISO timestamp)
        limit: Max results per page (default: 50, max: 100)

    Returns:
        FeedbackPage with items, next_cursor, and total count
    """
    # Validate limit
    if limit > 100:
        limit = 100

    # Parse date filters
    date_from_dt = None
    date_to_dt = None
    if date_from:
        try:
            date_from_dt = datetime.fromisoformat(date_from)
        except ValueError:
            raise HTTPException(400, f"Invalid date_from format: {date_from}")

    if date_to:
        try:
            date_to_dt = datetime.fromisoformat(date_to)
        except ValueError:
            raise HTTPException(400, f"Invalid date_to format: {date_to}")

    # Query repository
    repo = FeedbackItemRepository(db)

    items, next_cursor, total = await repo.list_with_filters(
        source=source,
        area=area,
        category=category,
        sentiment=sentiment,
        urgency=urgency,
        language=language,
        segment=segment,
        date_from=date_from_dt,
        date_to=date_to_dt,
        search_query=q,
        cursor=cursor,
        limit=limit
    )

    # Map to schema
    feedback_items = [
        FeedbackItem(
            id=str(item.id),
            summary_en=item.summary_en or "",
            source=item.parent_ticket.source_type.value if item.parent_ticket else "unknown",
            category=item.category.value if item.category else None,
            area=item.area.value if item.area else None,
            sentiment=item.sentiment.value if item.sentiment else None,
            urgency=item.urgency.value if item.urgency else None,
            language=item.language.value if item.language else "en",
            segment=item.segment.value if item.segment else None,
            customer_id=item.customer_id,
            customer_name=item.customer.name if item.customer else None,
            is_split=item.is_split,
            parent_ticket_id=str(item.parent_ticket_id),
            occurred_at=item.occurred_at
        )
        for item in items
    ]

    return FeedbackPage(
        items=feedback_items,
        next_cursor=next_cursor,
        total=total
    )


@router.get("/{item_id}", response_model=FeedbackDetail)
async def get_feedback(item_id: str, db: AsyncSession = Depends(get_db)):
    """Get detailed feedback item by ID.

    Args:
        item_id: Feedback item UUID

    Returns:
        FeedbackDetail with full information

    Raises:
        404: If feedback item not found
    """
    repo = FeedbackItemRepository(db)

    try:
        item = await repo.get_by_id(item_id)
    except Exception as e:
        raise HTTPException(400, f"Invalid ID format: {e}")

    if not item:
        raise HTTPException(404, "Feedback item not found")

    # Get raw text from parent ticket
    raw_text = None
    raw_language = None
    if item.parent_ticket:
        raw_text = item.parent_ticket.body or item.parent_ticket.subject
        raw_language = item.parent_ticket.language_raw.value if item.parent_ticket.language_raw else None

    # Get enrichment metadata
    enrichment_model = None
    enrichment_confidence = None
    pm_corrected = False
    if item.enrichment:
        enrichment_model = f"{item.enrichment.model}:{item.enrichment.model_version}"
        enrichment_confidence = item.enrichment.confidence
        pm_corrected = item.enrichment.pm_corrected

    return FeedbackDetail(
        id=str(item.id),
        summary_en=item.summary_en or "",
        source=item.parent_ticket.source_type.value if item.parent_ticket else "unknown",
        category=item.category.value if item.category else None,
        area=item.area.value if item.area else None,
        sentiment=item.sentiment.value if item.sentiment else None,
        urgency=item.urgency.value if item.urgency else None,
        language=item.language.value if item.language else "en",
        segment=item.segment.value if item.segment else None,
        customer_id=item.customer_id,
        customer_name=item.customer.name if item.customer else None,
        is_split=item.is_split,
        parent_ticket_id=str(item.parent_ticket_id),
        occurred_at=item.occurred_at,
        raw_text=raw_text,
        raw_language=raw_language,
        enrichment_model=enrichment_model,
        enrichment_confidence=enrichment_confidence,
        pm_corrected=pm_corrected
    )


@router.patch("/{item_id}/tags", response_model=FeedbackItem)
async def correct_tags(
    item_id: str,
    body: TagCorrection,
    db: AsyncSession = Depends(get_db)
):
    """Correct AI-generated tags (human-in-the-loop).

    Updates feedback item tags and marks enrichment as PM-corrected
    for continuous improvement tracking.

    Args:
        item_id: Feedback item UUID
        body: Tag corrections

    Returns:
        Updated FeedbackItem

    Raises:
        404: If feedback item not found
    """
    repo = FeedbackItemRepository(db)

    try:
        item = await repo.get_by_id(item_id)
    except Exception as e:
        raise HTTPException(400, f"Invalid ID format: {e}")

    if not item:
        raise HTTPException(404, "Feedback item not found")

    # Apply corrections
    update_data = {}
    if body.category is not None:
        update_data["category"] = FeedbackCategory(body.category)
    if body.area is not None:
        update_data["area"] = ProductArea(body.area)
    if body.sentiment is not None:
        update_data["sentiment"] = Sentiment(body.sentiment)
    if body.urgency is not None:
        update_data["urgency"] = Urgency(body.urgency)

    if update_data:
        item = await repo.update(item, **update_data)

        # Mark enrichment as corrected
        if item.enrichment:
            item.enrichment.pm_corrected = True
            # TODO: Set corrected_by from auth context

        await db.commit()

    return FeedbackItem(
        id=str(item.id),
        summary_en=item.summary_en or "",
        source=item.parent_ticket.source_type.value if item.parent_ticket else "unknown",
        category=item.category.value if item.category else None,
        area=item.area.value if item.area else None,
        sentiment=item.sentiment.value if item.sentiment else None,
        urgency=item.urgency.value if item.urgency else None,
        language=item.language.value if item.language else "en",
        segment=item.segment.value if item.segment else None,
        customer_id=item.customer_id,
        customer_name=item.customer.name if item.customer else None,
        is_split=item.is_split,
        parent_ticket_id=str(item.parent_ticket_id),
        occurred_at=item.occurred_at
    )
