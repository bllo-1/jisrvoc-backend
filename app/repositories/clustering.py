"""Clustering run repository for tracking clustering executions."""
import logging
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid

from app.models.clustering import ClusteringRun, ThemeMembership

logger = logging.getLogger(__name__)


class ClusteringRunRepository:
    """Repository for clustering run tracking."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_run(self) -> ClusteringRun:
        """Create a new clustering run.

        Returns:
            Created clustering run instance
        """
        run = ClusteringRun(status="running")
        self.session.add(run)
        await self.session.flush()
        logger.info(f"Created clustering run {run.id}")
        return run

    async def complete_run(
        self,
        run_id: str,
        item_count: int,
        status: str = "completed",
    ) -> ClusteringRun:
        """Mark clustering run as complete.

        Args:
            run_id: Run ID
            item_count: Number of items processed
            status: Final status (completed, failed)

        Returns:
            Updated run instance
        """
        run = await self.get_run(run_id)
        if not run:
            raise ValueError(f"Run {run_id} not found")

        from datetime import datetime
        run.finished_at = datetime.utcnow()
        run.item_count = item_count
        run.status = status

        await self.session.flush()
        logger.info(f"Completed clustering run {run_id}: {item_count} items")
        return run

    async def get_run(self, run_id: str) -> Optional[ClusteringRun]:
        """Get clustering run by ID."""
        result = await self.session.execute(
            select(ClusteringRun).where(ClusteringRun.id == run_id)
        )
        return result.scalars().first()

    async def add_membership(
        self,
        theme_id: str,
        feedback_id: str,
        run_id: str,
        similarity: Optional[float] = None,
    ) -> ThemeMembership:
        """Add feedback to theme for this run.

        Args:
            theme_id: Theme ID
            feedback_id: Feedback ID
            run_id: Clustering run ID
            similarity: Cosine similarity to theme centroid

        Returns:
            Created membership instance
        """
        membership = ThemeMembership(
            theme_id=uuid.UUID(theme_id),
            feedback_id=uuid.UUID(feedback_id),
            run_id=uuid.UUID(run_id),
            similarity=similarity,
        )
        self.session.add(membership)
        await self.session.flush()
        return membership

    async def commit(self):
        """Commit the current transaction."""
        await self.session.commit()

    async def rollback(self):
        """Rollback the current transaction."""
        await self.session.rollback()
