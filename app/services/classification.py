"""Classification service - coordinates AI classification of feedback."""

import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.feedback import FeedbackRepository
from app.repositories.classification import ClassificationRepository
from app.services.classification_pipeline import ClassificationPipeline
from app.models.feedback import Feedback
from app.models.classification import Classification


logger = logging.getLogger(__name__)


class ClassificationService:
    """
    Service to classify feedback using AI.

    Coordinates:
    1. Fetch unclassified feedback from database
    2. Run AI classification pipeline
    3. Store classification results
    """

    def __init__(
        self,
        session: AsyncSession,
        classification_pipeline: ClassificationPipeline,
    ):
        """Initialize classification service.

        Args:
            session: Database session
            classification_pipeline: AI classification pipeline
        """
        self.session = session
        self.classification_pipeline = classification_pipeline
        self.feedback_repo = FeedbackRepository(session)
        self.classification_repo = ClassificationRepository(session)

    async def classify_feedback(
        self,
        feedback: Feedback,
        model: Optional[str] = None,
    ) -> Classification:
        """
        Classify a single feedback item.

        Args:
            feedback: Feedback instance to classify
            model: Optional model override

        Returns:
            Classification instance
        """
        logger.info(f"Classifying feedback {feedback.id} from {feedback.source}:{feedback.external_id}")

        # Run AI classification
        result = await self.classification_pipeline.classify_feedback(
            title=feedback.title,
            content=feedback.content,
            source=feedback.source,
            model=model,
        )

        # Get model info
        model_used = model or self.classification_pipeline.llm_provider.default_model
        model_version = model_used  # Use model name as version for OpenAI

        # Upsert classification
        classification = await self.classification_repo.upsert_for_feedback(
            feedback_id=feedback.id,
            sentiment=result.sentiment,
            sentiment_score=result.sentiment_score,
            category=result.category,
            category_confidence=result.category_confidence,
            product_area=result.product_area,
            topics=result.topics,
            summary=result.summary,
            model_used=model_used,
            model_version=model_version,
            raw_response=result.model_dump() if hasattr(result, "model_dump") else None,
        )

        await self.classification_repo.commit()
        logger.info(
            f"Classified feedback {feedback.id}: "
            f"sentiment={classification.sentiment}, category={classification.category}"
        )

        return classification

    async def classify_unclassified_feedback(
        self,
        limit: int = 100,
        model: Optional[str] = None,
    ) -> list[Classification]:
        """
        Classify all unclassified feedback in database.

        Args:
            limit: Maximum number of items to classify
            model: Optional model override

        Returns:
            List of created classifications
        """
        logger.info(f"Starting classification of unclassified feedback (limit={limit})")

        # Fetch unclassified feedback
        unclassified = await self.feedback_repo.get_unclassified(limit=limit)
        logger.info(f"Found {len(unclassified)} unclassified feedback items")

        classifications = []
        for feedback in unclassified:
            try:
                classification = await self.classify_feedback(feedback, model=model)
                classifications.append(classification)
            except Exception as e:
                logger.error(
                    f"Error classifying feedback {feedback.id}: {e}",
                    exc_info=True,
                )
                continue

        logger.info(f"Classified {len(classifications)} feedback items")
        return classifications

    async def reclassify_feedback(
        self,
        feedback_id: int,
        model: Optional[str] = None,
    ) -> Classification:
        """
        Reclassify an existing feedback item (overwrite existing classification).

        Args:
            feedback_id: Feedback ID to reclassify
            model: Optional model override

        Returns:
            Updated classification instance
        """
        feedback = await self.feedback_repo.get_by_id(feedback_id)
        if not feedback:
            raise ValueError(f"Feedback {feedback_id} not found")

        logger.info(f"Reclassifying feedback {feedback_id}")
        return await self.classify_feedback(feedback, model=model)
