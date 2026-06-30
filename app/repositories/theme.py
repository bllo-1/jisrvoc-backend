"""Theme repository for CRUD and clustering operations."""
import logging
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from sqlalchemy.sql import Select
import numpy as np

from app.models.theme import Theme, ThemeTrend
from app.models.clustering import ThemeMembership

logger = logging.getLogger(__name__)


class ThemeRepository:
    """Repository for theme CRUD and clustering queries."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        name_en: str,
        description_en: Optional[str] = None,
        centroid: Optional[List[float]] = None,
        run_id: Optional[str] = None,
    ) -> Theme:
        """Create a new theme.

        Args:
            name_en: Theme name in English
            description_en: Theme description
            centroid: Vector centroid for similarity matching
            run_id: Clustering run ID that created this theme

        Returns:
            Created theme instance
        """
        theme = Theme(
            name_en=name_en,
            description_en=description_en,
            centroid=centroid,
            trend=ThemeTrend.NEW,
            last_run_id=run_id,
        )
        self.session.add(theme)
        await self.session.flush()
        logger.info(f"Created theme {theme.id}: {name_en}")
        return theme

    async def get_by_id(self, theme_id: str) -> Optional[Theme]:
        """Get theme by ID."""
        result = await self.session.execute(
            select(Theme).where(Theme.id == theme_id)
        )
        return result.scalars().first()

    async def get_active_themes(self) -> List[Theme]:
        """Get all active themes for matching."""
        result = await self.session.execute(
            select(Theme)
            .where(Theme.is_active == True)
            .order_by(Theme.last_run_id.desc())
        )
        return list(result.scalars().all())

    async def find_similar_theme(
        self,
        centroid: List[float],
        similarity_threshold: float = 0.7,
    ) -> Optional[Theme]:
        """Find most similar active theme by centroid cosine similarity.

        Args:
            centroid: Vector to compare against theme centroids
            similarity_threshold: Minimum cosine similarity (0.7 = 70%)

        Returns:
            Most similar theme if above threshold, None otherwise
        """
        # Get all active themes with centroids
        active_themes = await self.get_active_themes()

        if not active_themes:
            return None

        # Calculate cosine similarity for each theme
        best_theme = None
        best_similarity = similarity_threshold

        for theme in active_themes:
            if theme.centroid is None:
                continue

            # Cosine similarity: dot(a, b) / (norm(a) * norm(b))
            similarity = np.dot(centroid, theme.centroid) / (
                np.linalg.norm(centroid) * np.linalg.norm(theme.centroid)
            )

            if similarity > best_similarity:
                best_similarity = similarity
                best_theme = theme

        if best_theme:
            logger.info(
                f"Found similar theme {best_theme.id}: {best_theme.name_en} "
                f"(similarity={best_similarity:.2f})"
            )

        return best_theme

    async def update_theme_metadata(
        self,
        theme_id: str,
        item_count: int,
        customer_count: int,
        vote_weight: int,
        centroid: Optional[List[float]] = None,
        trend: Optional[ThemeTrend] = None,
        run_id: Optional[str] = None,
    ) -> Theme:
        """Update theme metadata after clustering run.

        Args:
            theme_id: Theme ID
            item_count: Number of feedback items in theme
            customer_count: Number of unique customers
            vote_weight: Sum of vote counts
            centroid: Updated centroid vector
            trend: Theme trend (new, rising, stable, declining)
            run_id: Clustering run ID

        Returns:
            Updated theme
        """
        theme = await self.get_by_id(theme_id)
        if not theme:
            raise ValueError(f"Theme {theme_id} not found")

        # Calculate trend if not provided
        if trend is None:
            if theme.item_count == 0:
                trend = ThemeTrend.NEW
            elif item_count > theme.item_count * 1.5:
                trend = ThemeTrend.RISING
            elif item_count < theme.item_count * 0.5:
                trend = ThemeTrend.DECLINING
            else:
                trend = ThemeTrend.STABLE

        theme.item_count = item_count
        theme.customer_count = customer_count
        theme.vote_weight = vote_weight
        if centroid:
            theme.centroid = centroid
        theme.trend = trend
        if run_id:
            theme.last_run_id = run_id

        await self.session.flush()
        logger.info(f"Updated theme {theme_id}: {item_count} items, trend={trend}")
        return theme

    async def get_top_themes(self, limit: int = 10) -> List[Theme]:
        """Get top themes by vote weight for bet generation.

        Args:
            limit: Maximum number of themes to return

        Returns:
            List of themes ordered by vote weight descending
        """
        result = await self.session.execute(
            select(Theme)
            .where(and_(
                Theme.is_active == True,
                Theme.item_count > 0,
            ))
            .order_by(Theme.vote_weight.desc(), Theme.item_count.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_active_count(self) -> int:
        """Get count of active themes.

        Returns:
            Count of active themes
        """
        result = await self.session.execute(
            select(func.count())
            .select_from(Theme)
            .where(Theme.is_active == True)
        )
        return result.scalar_one()

    async def deactivate_stale_themes(self, run_id: str) -> int:
        """Mark themes not updated in this run as inactive.

        Args:
            run_id: Current clustering run ID

        Returns:
            Number of themes deactivated
        """
        result = await self.session.execute(
            select(Theme).where(and_(
                Theme.is_active == True,
                Theme.last_run_id != run_id,
            ))
        )
        stale_themes = list(result.scalars().all())

        for theme in stale_themes:
            theme.is_active = False

        await self.session.flush()
        logger.info(f"Deactivated {len(stale_themes)} stale themes")
        return len(stale_themes)

    async def commit(self):
        """Commit the current transaction."""
        await self.session.commit()

    async def rollback(self):
        """Rollback the current transaction."""
        await self.session.rollback()
