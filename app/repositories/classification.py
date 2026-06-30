"""Classification repository for database operations."""

from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.classification import Classification
from app.repositories.base import BaseRepository


class ClassificationRepository(BaseRepository[Classification]):
    """Repository for Classification model operations."""

    def __init__(self, session: AsyncSession):
        """Initialize classification repository."""
        super().__init__(Classification, session)

    async def get_by_feedback_id(self, feedback_id: int) -> Optional[Classification]:
        """Get classification for a feedback item.

        Args:
            feedback_id: Feedback ID

        Returns:
            Classification instance or None if not found
        """
        result = await self.session.execute(
            select(Classification).where(Classification.feedback_id == feedback_id)
        )
        return result.scalar_one_or_none()

    async def upsert_for_feedback(
        self,
        feedback_id: int,
        sentiment: str,
        sentiment_score: float,
        category: str,
        category_confidence: float,
        product_area: Optional[str],
        topics: list[str],
        summary: str,
        model_used: str,
        model_version: str,
        raw_response: Optional[dict] = None,
    ) -> Classification:
        """Create or update classification for feedback.

        Args:
            feedback_id: Feedback ID
            sentiment: Sentiment classification
            sentiment_score: Sentiment score (-1.0 to 1.0)
            category: Category classification
            category_confidence: Category confidence (0.0 to 1.0)
            product_area: Product area if detected
            topics: List of topics
            summary: Summary text
            model_used: Model name used
            model_version: Model version
            raw_response: Raw AI response

        Returns:
            Classification instance
        """
        # Check if classification already exists
        existing = await self.get_by_feedback_id(feedback_id)

        if existing:
            # Update existing classification
            return await self.update(
                existing,
                sentiment=sentiment,
                sentiment_score=sentiment_score,
                category=category,
                category_confidence=category_confidence,
                product_area=product_area,
                topics=topics,
                summary=summary,
                model_used=model_used,
                model_version=model_version,
                raw_response=raw_response,
            )
        else:
            # Create new classification
            return await self.create(
                feedback_id=feedback_id,
                sentiment=sentiment,
                sentiment_score=sentiment_score,
                category=category,
                category_confidence=category_confidence,
                product_area=product_area,
                topics=topics,
                summary=summary,
                model_used=model_used,
                model_version=model_version,
                raw_response=raw_response,
            )
