"""Async enrichment pipeline (Phase 1). Wire to Celery/Arq + an in-region LLM.

Pipeline per raw ticket:
  1. decompose()  -> split multi-point tickets into cards (PRD 6.3)
  2. enrich()     -> category, area, sentiment, urgency, language, EN summary (PRD 6.1/6.2)
  3. embed()      -> multilingual vector for cross-language clustering
All steps persist structured output + model/version for audit and re-runs.
"""
import logging
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.feedback import Feedback
from app.services.classification import ClassificationService
from app.services.embedding import EmbeddingService
from app.repositories.feedback import FeedbackRepository
from app.ai.llm_provider import create_llm_provider

logger = logging.getLogger(__name__)


class EnrichmentWorker:
    """
    Worker to enrich feedback with AI-generated metadata.

    Phase 1 implementation using existing classification and embedding services.
    Integrates: classify (category, sentiment, etc.) + embeddings.
    """

    def __init__(self, session: AsyncSession):
        """Initialize enrichment worker.

        Args:
            session: Database session
        """
        self.session = session
        self.feedback_repo = FeedbackRepository(session)
        self.llm_provider = create_llm_provider()
        self.classification_service = ClassificationService(session, self.llm_provider)
        self.embedding_service = EmbeddingService(session, self.llm_provider)

    async def decompose(self, raw_text: str) -> list[str]:
        """Return distinct points. Single-topic tickets return one element.

        For Phase 1, we treat each feedback as a single point.
        Future: LLM-based decomposition for multi-point feedback.

        Args:
            raw_text: Raw feedback text

        Returns:
            List of decomposed feedback points (currently just [raw_text])
        """
        # Phase 1: No decomposition, treat as single point
        # Phase 2: Use LLM to split multi-point feedback
        logger.debug(f"Decomposing feedback (Phase 1: no decomposition)")
        return [raw_text]

    async def enrich(self, feedback: Feedback, model: Optional[str] = None) -> Feedback:
        """Enrich feedback with classification metadata.

        Uses ClassificationService to add:
        - category
        - product_area
        - sentiment
        - urgency
        - language
        - summary (English)

        Args:
            feedback: Feedback instance to enrich
            model: Optional model override

        Returns:
            Enriched feedback instance
        """
        logger.info(f"Enriching feedback {feedback.id}")

        # Use classification service to enrich
        classification = await self.classification_service.classify_feedback(
            feedback=feedback,
            model=model,
        )

        logger.info(f"Enriched feedback {feedback.id}: category={classification.category}, sentiment={classification.sentiment}")
        return feedback

    async def embed(self, feedback: Feedback, model: Optional[str] = None) -> Feedback:
        """Generate multilingual embedding for feedback.

        Args:
            feedback: Feedback instance to embed
            model: Optional embedding model override

        Returns:
            Feedback instance with embedding
        """
        logger.info(f"Generating embedding for feedback {feedback.id}")

        # Use embedding service
        await self.embedding_service.generate_embedding(
            feedback=feedback,
            model=model,
        )

        logger.info(f"Generated embedding for feedback {feedback.id}")
        return feedback

    async def process_feedback(
        self,
        feedback: Feedback,
        classification_model: Optional[str] = None,
        embedding_model: Optional[str] = None,
    ) -> Feedback:
        """
        Full enrichment pipeline for a single feedback item.

        Steps:
        1. Decompose (Phase 1: no-op)
        2. Enrich with classification
        3. Generate embedding

        Args:
            feedback: Feedback instance to process
            classification_model: Optional classification model override
            embedding_model: Optional embedding model override

        Returns:
            Fully enriched feedback instance
        """
        logger.info(f"Starting enrichment pipeline for feedback {feedback.id}")

        try:
            # Step 1: Decompose (currently no-op)
            points = await self.decompose(feedback.content)
            logger.debug(f"Decomposed into {len(points)} points")

            # Step 2: Enrich with classification
            await self.enrich(feedback, model=classification_model)

            # Step 3: Generate embedding
            await self.embed(feedback, model=embedding_model)

            # Commit all changes
            await self.session.commit()

            logger.info(f"Completed enrichment pipeline for feedback {feedback.id}")
            return feedback

        except Exception as e:
            logger.error(f"Error in enrichment pipeline for feedback {feedback.id}: {e}", exc_info=True)
            await self.session.rollback()
            raise

    async def process_unenriched_feedback(
        self,
        limit: int = 100,
        classification_model: Optional[str] = None,
        embedding_model: Optional[str] = None,
    ) -> int:
        """
        Process all feedback that hasn't been enriched yet.

        Args:
            limit: Maximum number of feedback items to process
            classification_model: Optional classification model override
            embedding_model: Optional embedding model override

        Returns:
            Number of feedback items successfully enriched
        """
        logger.info(f"Starting batch enrichment (limit={limit})")

        # Get unenriched feedback (no classification or embedding)
        from sqlalchemy import select, and_
        result = await self.session.execute(
            select(Feedback)
            .outerjoin(Feedback.classifications)
            .where(
                and_(
                    Feedback.classifications == None,
                    Feedback.embedding.is_(None)
                )
            )
            .order_by(Feedback.created_at.desc())
            .limit(limit)
        )
        unenriched = list(result.scalars().all())
        logger.info(f"Found {len(unenriched)} unenriched feedback items")

        enriched_count = 0
        for feedback in unenriched:
            try:
                await self.process_feedback(
                    feedback=feedback,
                    classification_model=classification_model,
                    embedding_model=embedding_model,
                )
                enriched_count += 1
            except Exception as e:
                logger.error(f"Error enriching feedback {feedback.id}: {e}", exc_info=True)
                continue

        logger.info(f"Enriched {enriched_count}/{len(unenriched)} feedback items")
        return enriched_count


# Legacy function stubs for backwards compatibility
async def decompose(raw_text: str) -> list[str]:
    """Return distinct points. Single-topic tickets return one element."""
    worker = EnrichmentWorker(session=None)  # type: ignore
    return await worker.decompose(raw_text)


async def enrich(card_text: str) -> dict:
    """Return {summary_en, category, area, sentiment, urgency, language} via in-region LLM."""
    raise NotImplementedError("Use EnrichmentWorker.enrich() instead")


async def embed(text: str) -> list[float]:
    """Return a multilingual embedding (dim must match db schema vector(N))."""
    raise NotImplementedError("Use EnrichmentWorker.embed() instead")


async def process_ticket(ticket_id: str) -> None:
    """Entry point consumed from the ingestion queue."""
    raise NotImplementedError("Use EnrichmentWorker.process_feedback() instead")
