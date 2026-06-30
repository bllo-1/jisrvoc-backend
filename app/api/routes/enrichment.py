"""API endpoints for enrichment pipeline operations."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.db.session import get_db
from app.workers.enrichment import EnrichmentWorker


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/enrichment", tags=["enrichment"])


# Request/Response models
class EnrichmentRequest(BaseModel):
    """Request for enrichment operations."""
    limit: int = 100
    classification_model: Optional[str] = None
    embedding_model: Optional[str] = None


class EnrichmentResponse(BaseModel):
    """Response for enrichment operations."""
    message: str
    enriched_count: int


# Endpoints
@router.post("/process", response_model=EnrichmentResponse)
async def enrich_feedback(
    request: EnrichmentRequest = EnrichmentRequest(),
    db: AsyncSession = Depends(get_db),
):
    """
    Run enrichment pipeline on unenriched feedback.

    Processes feedback through the full pipeline:
    1. Decompose (Phase 1: no-op)
    2. Classify (category, sentiment, urgency, etc.)
    3. Embed (multilingual vector embeddings)

    Args:
        request: Enrichment parameters (limit, model overrides)
        db: Database session

    Returns:
        Enrichment result with count of processed items
    """
    try:
        # Initialize enrichment worker
        worker = EnrichmentWorker(session=db)

        # Process unenriched feedback
        enriched_count = await worker.process_unenriched_feedback(
            limit=request.limit,
            classification_model=request.classification_model,
            embedding_model=request.embedding_model,
        )

        return EnrichmentResponse(
            message=f"Successfully enriched {enriched_count} feedback items",
            enriched_count=enriched_count,
        )
    except Exception as e:
        logger.error(f"Error enriching feedback: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to enrich feedback: {str(e)}")
