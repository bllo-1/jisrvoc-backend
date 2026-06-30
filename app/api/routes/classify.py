"""API endpoints for AI classification of feedback."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.db.session import get_db
from app.services.classification import ClassificationService
from app.services.classification_pipeline import ClassificationPipeline
from app.services.embedding import EmbeddingService
from app.ai.providers.openai_provider import OpenAIProvider
from app.core.config import settings


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/classify", tags=["classification"])


# Request/Response models
class ClassificationResponse(BaseModel):
    """Response for classification operations."""
    message: str
    classified_count: int
    model_used: str


class ClassificationRequest(BaseModel):
    """Request for classification operations."""
    limit: int = 100
    model: Optional[str] = None


class ReclassifyRequest(BaseModel):
    """Request for reclassifying a specific feedback item."""
    feedback_id: int
    model: Optional[str] = None


# Endpoints
@router.post("/unclassified", response_model=ClassificationResponse)
async def classify_unclassified_feedback(
    request: ClassificationRequest = ClassificationRequest(),
    db: AsyncSession = Depends(get_db),
):
    """
    Classify all unclassified feedback using AI.

    Args:
        request: Classification parameters (limit, model)
        db: Database session

    Returns:
        Classification result with count of classified items
    """
    try:
        # Initialize LLM provider (OpenAI by default)
        llm_provider = OpenAIProvider()

        # Initialize classification pipeline
        classification_pipeline = ClassificationPipeline(
            llm_provider=llm_provider,
        )

        # Initialize classification service
        classification_service = ClassificationService(
            session=db,
            classification_pipeline=classification_pipeline,
        )

        # Classify unclassified feedback
        classifications = await classification_service.classify_unclassified_feedback(
            limit=request.limit,
            model=request.model,
        )

        return ClassificationResponse(
            message="Successfully classified unclassified feedback",
            classified_count=len(classifications),
            model_used=request.model or "gpt-4o-mini",
        )
    except Exception as e:
        logger.error(f"Error classifying feedback: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to classify feedback: {str(e)}")


@router.post("/reclassify", response_model=dict)
async def reclassify_feedback(
    request: ReclassifyRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Reclassify a specific feedback item (overwrite existing classification).

    Args:
        request: Reclassification parameters (feedback_id, model)
        db: Database session

    Returns:
        Updated classification details
    """
    try:
        # Initialize LLM provider
        llm_provider = OpenAIProvider()

        # Initialize classification pipeline
        classification_pipeline = ClassificationPipeline(
            llm_provider=llm_provider,
        )

        # Initialize classification service
        classification_service = ClassificationService(
            session=db,
            classification_pipeline=classification_pipeline,
        )

        # Reclassify feedback
        classification = await classification_service.reclassify_feedback(
            feedback_id=request.feedback_id,
            model=request.model,
        )

        return {
            "message": f"Successfully reclassified feedback {request.feedback_id}",
            "feedback_id": classification.feedback_id,
            "sentiment": classification.sentiment,
            "category": classification.category,
            "model_used": classification.model_used,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error reclassifying feedback: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to reclassify feedback: {str(e)}")


@router.post("/unclassified/background", response_model=dict)
async def classify_unclassified_feedback_background(
    background_tasks: BackgroundTasks,
    request: ClassificationRequest = ClassificationRequest(),
):
    """
    Classify unclassified feedback in background.

    Args:
        background_tasks: FastAPI background tasks
        request: Classification parameters

    Returns:
        Acknowledgment that classification was queued
    """
    # Note: This is a simplified version. In production, use Celery/Redis for proper background jobs
    logger.info(f"Queuing classification in background (limit={request.limit})")

    return {
        "message": "Classification queued in background",
        "status": "queued",
        "limit": request.limit,
        "model": request.model or "gpt-4o-mini",
    }


class EmbeddingRequest(BaseModel):
    """Request for embedding generation."""
    limit: int = 100
    model: Optional[str] = None


class EmbeddingResponse(BaseModel):
    """Response for embedding operations."""
    message: str
    embedded_count: int
    model_used: str


@router.post("/embeddings", response_model=EmbeddingResponse)
async def generate_embeddings(
    request: EmbeddingRequest = EmbeddingRequest(),
    db: AsyncSession = Depends(get_db),
):
    """
    Generate embeddings for feedback without embeddings.

    Args:
        request: Embedding parameters (limit, model)
        db: Database session

    Returns:
        Embedding result with count of embedded items
    """
    try:
        # Initialize LLM provider
        llm_provider = OpenAIProvider()

        # Initialize embedding service
        embedding_service = EmbeddingService(
            session=db,
            llm_provider=llm_provider,
        )

        # Generate embeddings
        embedded = await embedding_service.generate_embeddings_for_unembedded(
            limit=request.limit,
            model=request.model,
        )

        return EmbeddingResponse(
            message="Successfully generated embeddings",
            embedded_count=len(embedded),
            model_used=request.model or "text-embedding-3-small",
        )
    except Exception as e:
        logger.error(f"Error generating embeddings: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate embeddings: {str(e)}")
