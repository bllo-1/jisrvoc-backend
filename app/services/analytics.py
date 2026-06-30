"""Analytics service for orchestrating complex queries and caching."""

import logging
from typing import Dict, List
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.feedback_item import FeedbackItemRepository
from app.repositories.theme import ThemeRepository
from app.repositories.bet import BetRepository
from app.schemas import (
    OverviewMetrics,
    UrgencyDistribution,
    TrendPoint,
    CountBucket,
    ThemeSummary
)

logger = logging.getLogger(__name__)


class AnalyticsService:
    """
    Service layer for analytics queries with caching and resilience.

    Orchestrates data from multiple repositories and handles:
    - Complex multi-repository aggregations
    - Caching strategy (future: Redis)
    - Graceful degradation on partial failures
    - Query performance monitoring
    """

    def __init__(self, session: AsyncSession):
        """Initialize analytics service with repository dependencies.

        Args:
            session: Async database session
        """
        self.session = session
        self.feedback_repo = FeedbackItemRepository(session)
        self.theme_repo = ThemeRepository(session)
        self.bet_repo = BetRepository(session)

    async def get_overview_metrics(self) -> OverviewMetrics:
        """Get overview dashboard metrics.

        Combines data from feedback, themes, and bets repositories.
        Future: Cache for 5 minutes.

        Returns:
            OverviewMetrics with counts and distributions

        Raises:
            Exception: If critical metrics fail (total_items, active_themes)
        """
        try:
            # Critical metrics (must succeed)
            total_items = await self.feedback_repo.get_total_count()
            active_themes = await self.theme_repo.get_active_count()

            # High-priority metrics (fail gracefully)
            try:
                high_urgency_open = await self.feedback_repo.get_high_urgency_count()
            except Exception as e:
                logger.error(f"Failed to get high urgency count: {e}")
                high_urgency_open = 0

            try:
                bets_in_flight = await self.bet_repo.count_in_flight()
            except Exception as e:
                logger.error(f"Failed to get bets in flight: {e}")
                bets_in_flight = 0

            # Urgency distribution (fail gracefully)
            try:
                urgency_dist_dict = await self.feedback_repo.get_urgency_distribution()
                urgency_distribution = UrgencyDistribution(
                    low=urgency_dist_dict.get("low", 0),
                    medium=urgency_dist_dict.get("medium", 0),
                    high=urgency_dist_dict.get("high", 0)
                )
            except Exception as e:
                logger.error(f"Failed to get urgency distribution: {e}")
                urgency_distribution = UrgencyDistribution(low=0, medium=0, high=0)

            return OverviewMetrics(
                total_items=total_items,
                active_themes=active_themes,
                high_urgency_open=high_urgency_open,
                bets_in_flight=bets_in_flight,
                urgency_distribution=urgency_distribution
            )

        except Exception as e:
            logger.error(f"Critical failure in get_overview_metrics: {e}")
            raise

    async def get_volume_trend(self, weeks: int = 12) -> List[TrendPoint]:
        """Get weekly feedback volume trend.

        Future: Cache for 1 hour (stable historical data).

        Args:
            weeks: Number of weeks to look back

        Returns:
            List of TrendPoint with week_start and count
        """
        try:
            trend_data = await self.feedback_repo.get_volume_trend(weeks)

            return [
                TrendPoint(
                    week_start=point["week_start"],
                    count=point["count"]
                )
                for point in trend_data
            ]

        except Exception as e:
            logger.error(f"Failed to get volume trend: {e}")
            # Return empty list for graceful degradation
            return []

    async def get_by_source_distribution(self) -> List[CountBucket]:
        """Get feedback distribution by source type.

        Future: Cache for 10 minutes.

        Returns:
            List of CountBucket with source and count
        """
        try:
            distribution = await self.feedback_repo.get_by_source_distribution()

            return [
                CountBucket(key=item["key"], count=item["count"])
                for item in distribution
            ]

        except Exception as e:
            logger.error(f"Failed to get source distribution: {e}")
            return []

    async def get_by_area_distribution(self) -> List[CountBucket]:
        """Get feedback distribution by product area.

        Future: Cache for 10 minutes.

        Returns:
            List of CountBucket with area and count
        """
        try:
            distribution = await self.feedback_repo.get_by_area_distribution()

            return [
                CountBucket(key=item["key"], count=item["count"])
                for item in distribution
            ]

        except Exception as e:
            logger.error(f"Failed to get area distribution: {e}")
            return []

    async def get_top_themes(self, limit: int = 5) -> List[ThemeSummary]:
        """Get top themes by vote weight for overview.

        Future: Cache for 10 minutes.

        Args:
            limit: Maximum number of themes to return

        Returns:
            List of ThemeSummary
        """
        try:
            themes = await self.theme_repo.get_top_themes(limit)

            return [
                ThemeSummary(
                    id=str(theme.id),
                    name_en=theme.name_en,
                    item_count=theme.item_count,
                    customer_count=theme.customer_count,
                    trend=theme.trend.value if theme.trend else "stable"
                )
                for theme in themes
            ]

        except Exception as e:
            logger.error(f"Failed to get top themes: {e}")
            return []

    async def close(self):
        """Close service resources (database session).

        Call this when done with the service to clean up resources.
        """
        await self.session.close()
