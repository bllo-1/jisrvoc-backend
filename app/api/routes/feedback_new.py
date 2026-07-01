"""
Feedback API endpoints - item listing, enrichment, tagging.
Matches frontend contract from jisrvoc-frontend/src/lib/api/feedback.ts
"""
from fastapi import APIRouter, Query, Depends, HTTPException, Request
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
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
    Language,
)
from ... import mock_data
from ...db.session import get_db
from ...repositories.feedback import FeedbackRepository
from ...repositories.theme import ThemeRepository
from ...models.feedback import Feedback
from ...core.config import settings
from ...agents.orchestrator import AgentOrchestrator

router = APIRouter()


# Response models for agent enrichment endpoints
class AgentEnrichmentResponse(BaseModel):
    """Response from agent enrichment endpoint."""
    success: bool
    feedback_id: str
    enrichment: Dict[str, Any]
    agent_results: List[Dict[str, Any]]
    execution_time_ms: float


class RulesReloadResponse(BaseModel):
    """Response from rules reload endpoint."""
    success: bool
    message: str
    agent_status: Dict[str, Any]


def map_feedback_to_item(feedback: Feedback) -> FeedbackItem:
    """Map Phase 1 Feedback model to Phase 3 FeedbackItem schema."""
    # Map source to enum
    source_map = {
        "hubspot": Source.hubspot,
        "zendesk": Source.zendesk,
        "canny": Source.canny,
        "jira": Source.jira,
    }

    # Default enrichment values for un-enriched feedback
    return FeedbackItem(
        id=str(feedback.id),
        summary=feedback.title,
        raw_text=feedback.content,
        source=source_map.get(feedback.source.lower(), Source.hubspot),
        source_ref=feedback.external_id,
        category=Category.pain_point,  # Default - will be enriched later
        product_area=ProductArea.other,  # Default - will be enriched later
        sentiment=Sentiment.neutral,  # Default - will be enriched later
        urgency=Urgency.medium,  # Default - will be enriched later
        language=Language.en,  # Default - will be enriched later
        customer=feedback.customer_email or "Unknown",
        customer_id=str(feedback.customer_id) if feedback.customer_id else "unknown",
        segment=Segment.smb,  # Default - will be enriched later
        date=feedback.created_at.isoformat(),
        theme_id=None,
        split_from=None,
        tags=[],
    )


@router.get("", response_model=FeedbackPage)
async def list_feedback(
    db: AsyncSession = Depends(get_db),
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
    # Parse cursor to offset
    offset = 0
    if cursor:
        try:
            offset = int(cursor.split("-")[1])
        except (IndexError, ValueError):
            offset = 0

    # Map source enum to database value
    source_filter = None
    if source:
        source_map = {
            Source.hubspot: "hubspot",
            Source.zendesk: "zendesk",
            Source.canny: "canny",
            Source.jira: "jira",
        }
        source_filter = source_map.get(source)

    # Query database
    feedback_repo = FeedbackRepository(db)
    feedback_items, total = await feedback_repo.list_all(
        limit=limit,
        offset=offset,
        source=source_filter
    )

    # Map to FeedbackItem schema
    items = [map_feedback_to_item(f) for f in feedback_items]

    # NOTE: Phase 1 doesn't have enrichment data yet, so category/product_area/sentiment/urgency/segment filters
    # are not applied. These filters will work once Phase 2 enrichment is implemented.
    # For now, we only filter by source at the database level.

    # Apply in-memory filters for enrichment fields (once enriched)
    if category:
        items = [f for f in items if f.category == category]
    if product_area:
        items = [f for f in items if f.product_area == product_area]
    if sentiment:
        items = [f for f in items if f.sentiment == sentiment]
    if urgency:
        items = [f for f in items if f.urgency == urgency]
    if segment:
        items = [f for f in items if f.segment == segment]
    if theme_id:
        items = [f for f in items if f.theme_id == theme_id]
    if customer_id:
        items = [f for f in items if f.customer_id == customer_id]

    # Calculate next cursor
    next_cursor = None
    if offset + limit < total:
        next_cursor = f"idx-{offset + limit}"

    return FeedbackPage(
        items=items,
        next_cursor=next_cursor,
        total=total,
    )


@router.get("/{feedback_id}", response_model=FeedbackItem)
async def get_feedback(feedback_id: str, db: AsyncSession = Depends(get_db)):
    """
    @endpoint GET /api/v1/feedback/:id
    Returns single feedback item by ID.
    """
    try:
        feedback_id_int = int(feedback_id)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid feedback ID: {feedback_id}")

    feedback_repo = FeedbackRepository(db)
    feedback = await feedback_repo.get_by_id(feedback_id_int)

    if not feedback:
        raise HTTPException(status_code=404, detail=f"Feedback {feedback_id} not found")

    return map_feedback_to_item(feedback)


@router.get("/{feedback_id}/enrichment", response_model=EnrichmentMeta)
async def get_enrichment(feedback_id: str, db: AsyncSession = Depends(get_db)):
    """
    @endpoint GET /api/v1/feedback/:id/enrichment
    Returns AI enrichment metadata for a feedback item.
    """
    try:
        feedback_id_int = int(feedback_id)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid feedback ID: {feedback_id}")

    # Verify feedback exists
    feedback_repo = FeedbackRepository(db)
    feedback = await feedback_repo.get_by_id(feedback_id_int)

    if not feedback:
        raise HTTPException(status_code=404, detail=f"Feedback {feedback_id} not found")

    # Mock enrichment metadata (Phase 2 will implement real enrichment)
    return EnrichmentMeta(
        model="claude-sonnet-4",
        model_version="20250514",
        confidence=0.89,
        pm_corrected=False,
    )


@router.patch("/{feedback_id}/tags", response_model=FeedbackItem)
async def update_tags(feedback_id: str, edits: FeedbackTagEdit, db: AsyncSession = Depends(get_db)):
    """
    @endpoint PATCH /api/v1/feedback/:id/tags
    Updates enrichment tags (category, product_area, sentiment, urgency).
    Phase 1: Returns updated item without persisting changes
    Phase 2: Will update Classification table and trigger re-clustering
    """
    try:
        feedback_id_int = int(feedback_id)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid feedback ID: {feedback_id}")

    # Find the feedback item
    feedback_repo = FeedbackRepository(db)
    feedback = await feedback_repo.get_by_id(feedback_id_int)

    if not feedback:
        raise HTTPException(status_code=404, detail=f"Feedback {feedback_id} not found")

    # Map to FeedbackItem
    item = map_feedback_to_item(feedback)

    # Apply edits (Phase 1: in-memory only)
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

    # Phase 2 TODO:
    # 1. Update Classification table with new tags
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


# ============================================================================
# AGENT-BASED ENRICHMENT ENDPOINTS (Phase 5)
# ============================================================================

@router.post("/enrich", response_model=AgentEnrichmentResponse)
async def enrich_feedback(
    feedback_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    @endpoint POST /api/v1/feedback/enrich
    Enriches feedback using appropriate pipeline (agent-based or LLM-based).

    This endpoint uses feature flags to route between:
    - Agent pipeline (gradual rollout via AGENT_ROLLOUT_PERCENTAGE)
    - Old LLM pipeline (fallback for remaining traffic)

    The routing decision is consistent per feedback_id using hash-based bucketing.

    Returns:
        Enrichment result with metadata about which pipeline was used
    """
    from ...services.feature_flags import (
        should_use_agents,
        record_agent_execution,
        record_old_pipeline_execution
    )
    from ...ai.llm_provider import create_llm_provider, LLMProvider
    from ...services.classification_pipeline import ClassificationPipeline
    import time

    # Get correlation ID from request
    correlation_id = getattr(request.state, "correlation_id", None)

    try:
        # Parse feedback ID
        try:
            feedback_id_int = int(feedback_id)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid feedback ID: {feedback_id}")

        # Fetch feedback from database
        feedback_repo = FeedbackRepository(db)
        feedback = await feedback_repo.get_by_id(feedback_id_int)

        if not feedback:
            raise HTTPException(status_code=404, detail=f"Feedback {feedback_id} not found")

        # Feature flag decision: agent vs old pipeline
        use_agents = should_use_agents(feedback_id)

        if use_agents:
            # ============================================================
            # AGENT PIPELINE (new)
            # ============================================================
            start_time = time.time()

            try:
                # Get orchestrator from app state
                orchestrator = getattr(request.app.state, "orchestrator", None)
                if not orchestrator:
                    # Fallback: create orchestrator on-demand
                    theme_repo = ThemeRepository(db)
                    orchestrator = AgentOrchestrator(theme_repository=theme_repo)

                # Run enrichment pipeline
                success, enrichment, agent_results = await orchestrator.enrich_feedback(
                    feedback_id=feedback_id,
                    raw_text=feedback.content,
                    language="EN",  # TODO: Detect language
                    correlation_id=correlation_id,
                )

                execution_time_ms = (time.time() - start_time) * 1000

                # Record metrics
                record_agent_execution(
                    success=success,
                    execution_time_ms=execution_time_ms,
                    error=None if success else "Agent pipeline returned success=False"
                )

                # Convert agent results to serializable format
                agent_results_serialized = [
                    {
                        "agent_name": r.agent_name,
                        "status": r.status.value,
                        "tags_added": r.tags_added,
                        "confidence_scores": r.confidence_scores,
                        "metadata": r.metadata,
                        "error_message": r.error_message,
                        "execution_time_ms": r.execution_time_ms,
                    }
                    for r in agent_results
                ]

                # Add pipeline metadata
                enrichment["pipeline_used"] = "agent"
                enrichment["execution_time_ms"] = execution_time_ms

                return AgentEnrichmentResponse(
                    success=success,
                    feedback_id=feedback_id,
                    enrichment=enrichment,
                    agent_results=agent_results_serialized,
                    execution_time_ms=execution_time_ms,
                )

            except Exception as e:
                execution_time_ms = (time.time() - start_time) * 1000
                error_msg = str(e)

                # Record error metrics
                record_agent_execution(
                    success=False,
                    execution_time_ms=execution_time_ms,
                    error=error_msg
                )

                raise HTTPException(
                    status_code=500,
                    detail=f"Agent enrichment failed: {error_msg}"
                )

        else:
            # ============================================================
            # OLD LLM PIPELINE (fallback)
            # ============================================================
            start_time = time.time()

            try:
                # Initialize old pipeline
                provider_type = LLMProvider(settings.llm_provider)
                llm_provider = create_llm_provider(provider_type)
                old_pipeline = ClassificationPipeline(llm_provider)

                # Run classification
                classification = await old_pipeline.classify_feedback(
                    title=feedback.title or "",
                    content=feedback.content,
                    source=feedback.source,
                )

                execution_time_ms = (time.time() - start_time) * 1000

                # Record metrics
                record_old_pipeline_execution(execution_time_ms)

                # Convert to enrichment format (backward compatible)
                enrichment = {
                    "pipeline_used": "llm",
                    "sentiment": classification.sentiment,
                    "sentiment_score": classification.sentiment_score,
                    "category": classification.category,
                    "product_area": classification.product_area,
                    "topics": classification.topics,
                    "summary": classification.summary,
                    "confidence": classification.category_confidence,
                    "execution_time_ms": execution_time_ms,
                }

                # Mock agent results structure for consistency
                agent_results = []

                return AgentEnrichmentResponse(
                    success=True,
                    feedback_id=feedback_id,
                    enrichment=enrichment,
                    agent_results=agent_results,
                    execution_time_ms=execution_time_ms,
                )

            except Exception as e:
                execution_time_ms = (time.time() - start_time) * 1000
                error_msg = str(e)

                raise HTTPException(
                    status_code=500,
                    detail=f"LLM enrichment failed: {error_msg}"
                )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Enrichment failed: {str(e)}"
        )


@router.post("/enrich-with-agents", response_model=AgentEnrichmentResponse)
async def enrich_with_agents(
    feedback_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    @endpoint POST /api/v1/feedback/enrich-with-agents
    DEPRECATED: Use POST /api/v1/feedback/enrich instead.

    This endpoint is kept for backward compatibility but now delegates to
    the feature-flag-aware /enrich endpoint.
    """
    return await enrich_feedback(feedback_id, request, db)


@router.post("/admin/reload-rules", response_model=RulesReloadResponse)
async def reload_rules(request: Request):
    """
    @endpoint POST /api/v1/feedback/admin/reload-rules
    Hot-reloads all YAML rules without restarting the application.

    Allows PMs to update disambiguation, compliance, and taxonomy rules
    and test changes immediately without downtime.

    Returns updated agent status including rule counts.
    """
    try:
        # Get orchestrator from app state
        orchestrator = getattr(request.app.state, "orchestrator", None)
        if not orchestrator:
            raise HTTPException(
                status_code=503,
                detail="Orchestrator not initialized. Check application startup."
            )

        # Reload rules
        success = orchestrator.reload_rules()

        if success:
            agent_status = orchestrator.get_agent_status()
            return RulesReloadResponse(
                success=True,
                message="Rules reloaded successfully",
                agent_status=agent_status,
            )
        else:
            raise HTTPException(
                status_code=500,
                detail="Failed to reload rules. Check logs for details."
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Rule reload failed: {str(e)}"
        )
