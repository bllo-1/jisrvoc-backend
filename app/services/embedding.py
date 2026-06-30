"""Embedding service - generates and stores embeddings for feedback."""

import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.feedback import FeedbackRepository
from app.ai.llm_provider import BaseLLMProvider
from app.models.feedback import Feedback


logger = logging.getLogger(__name__)


class EmbeddingService:
    """
    Service to generate embeddings for feedback.

    Coordinates:
    1. Fetch feedback without embeddings
    2. Generate embeddings using LLM provider
    3. Update feedback with embeddings
    """

    def __init__(
        self,
        session: AsyncSession,
        llm_provider: BaseLLMProvider,
    ):
        """Initialize embedding service.

        Args:
            session: Database session
            llm_provider: LLM provider for generating embeddings
        """
        self.session = session
        self.llm_provider = llm_provider
        self.feedback_repo = FeedbackRepository(session)

    async def generate_embedding(
        self,
        feedback: Feedback,
        model: Optional[str] = None,
    ) -> Feedback:
        """
        Generate embedding for a single feedback item.

        Args:
            feedback: Feedback instance to generate embedding for
            model: Optional model override

        Returns:
            Updated feedback instance with embedding
        """
        logger.info(f"Generating embedding for feedback {feedback.id}")

        # Combine title and content for embedding
        text = f"{feedback.title}\n\n{feedback.content}"

        # Generate embedding
        embedding = await self.llm_provider.generate_embedding(
            text=text,
            model=model,
        )

        # Update feedback with embedding (just modify object, commit happens at the end)
        feedback.embedding = embedding

        logger.info(f"Generated embedding for feedback {feedback.id} ({len(embedding)} dimensions)")

        return feedback

    async def generate_embeddings_for_unembedded(
        self,
        limit: int = 100,
        model: Optional[str] = None,
    ) -> list[Feedback]:
        """
        Generate embeddings for all feedback without embeddings.

        Args:
            limit: Maximum number of items to process
            model: Optional model override

        Returns:
            List of updated feedback items
        """
        logger.info(f"Starting embedding generation for feedback without embeddings (limit={limit})")

        # Fetch feedback without embeddings
        from sqlalchemy import select
        result = await self.session.execute(
            select(Feedback)
            .where(Feedback.embedding.is_(None))
            .order_by(Feedback.created_at.desc())
            .limit(limit)
        )
        unembedded = list(result.scalars().all())
        logger.info(f"Found {len(unembedded)} feedback items without embeddings")

        embedded = []
        for feedback in unembedded:
            try:
                updated_feedback = await self.generate_embedding(feedback, model=model)
                embedded.append(updated_feedback)
            except Exception as e:
                logger.error(
                    f"Error generating embedding for feedback {feedback.id}: {e}",
                    exc_info=True,
                )
                continue

        # Commit all changes
        await self.session.commit()

        logger.info(f"Generated embeddings for {len(embedded)} feedback items")
        return embedded
