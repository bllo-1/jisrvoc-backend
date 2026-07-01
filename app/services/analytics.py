"""Analytics service for orchestrating complex queries and caching."""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.feedback_item import FeedbackItemRepository
from app.repositories.theme import ThemeRepository
from app.repositories.bet import BetRepository
from app.models.feedback import Feedback
from app.schemas_new import (
    OverviewMetrics,
    UrgencyDistribution
)
from app.schemas import (
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

            # Chart data (fail gracefully with empty lists)
            try:
                volume_trend = await self.get_volume_trend(12)
                weekly_volume = [
                    {"week": point.week_start.isoformat(), "count": point.count}
                    for point in volume_trend
                ]
            except Exception as e:
                logger.error(f"Failed to get volume trend: {e}")
                weekly_volume = []

            try:
                source_dist = await self.get_by_source_distribution()
                source_breakdown = [
                    {"source": bucket.key, "count": bucket.count}
                    for bucket in source_dist
                ]
            except Exception as e:
                logger.error(f"Failed to get source breakdown: {e}")
                source_breakdown = []

            try:
                area_dist = await self.get_by_area_distribution()
                product_area_breakdown = [
                    {"area": bucket.key, "count": bucket.count}
                    for bucket in area_dist
                ]
            except Exception as e:
                logger.error(f"Failed to get product area breakdown: {e}")
                product_area_breakdown = []

            return OverviewMetrics(
                total_feedback=total_items,
                active_themes=active_themes,
                high_urgency_open=high_urgency_open,
                bets_in_flight=bets_in_flight,
                weekly_volume=weekly_volume,
                source_breakdown=source_breakdown,
                product_area_breakdown=product_area_breakdown,
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


# ============================================================================
# AGENT PIPELINE MONITORING (Phase 5)
# ============================================================================

async def get_agent_metrics(
    db: AsyncSession,
    hours_back: int = 24,
) -> Dict[str, Any]:
    """
    Get agent pipeline execution metrics.

    Calculates success rate, average latency, and error rate per agent
    from recent enrichment operations.

    Args:
        db: Database session
        hours_back: Number of hours to look back (default: 24)

    Returns:
        Dictionary with per-agent metrics:
        {
            "triage": {
                "total_executions": 1234,
                "success_count": 1200,
                "error_count": 34,
                "success_rate": 0.972,
                "avg_execution_time_ms": 45.2,
                "p95_execution_time_ms": 120.5,
            },
            "llm": {...},
            ...
        }

    Note:
        In Phase 5, agent execution logs are not persisted to database.
        This function returns mock data. In Phase 6, add agent_execution_log table.
    """
    # TODO Phase 6: Query agent_execution_log table
    # For now, return mock structure to demonstrate the interface

    logger.info(
        "Getting agent metrics",
        extra={"hours_back": hours_back}
    )

    # Mock data structure (replace with real queries in Phase 6)
    return {
        "triage": {
            "total_executions": 0,
            "success_count": 0,
            "error_count": 0,
            "success_rate": 0.0,
            "avg_execution_time_ms": 0.0,
            "p95_execution_time_ms": 0.0,
        },
        "time_window": {
            "hours_back": hours_back,
            "start_time": (datetime.utcnow() - timedelta(hours=hours_back)).isoformat(),
            "end_time": datetime.utcnow().isoformat(),
        },
        "note": "Agent execution logs not persisted yet. Add agent_execution_log table in Phase 6."
    }


async def get_classification_accuracy(
    db: AsyncSession,
    days_back: int = 7,
) -> Dict[str, Any]:
    """
    Compare agent classifications vs PM corrections.

    Calculates how often PMs correct agent-assigned product areas,
    which indicates classification accuracy.

    Args:
        db: Database session
        days_back: Number of days to analyze (default: 7)

    Returns:
        Dictionary with accuracy metrics:
        {
            "total_agent_classifications": 500,
            "pm_corrections": 25,
            "correction_rate": 0.05,  # 5% of classifications corrected
            "accuracy_rate": 0.95,
            "corrections_by_area": {
                "Finance": 10,
                "Payroll": 5,
                ...
            }
        }

    Note:
        Requires enrichment_meta table with pm_corrected flag.
        Currently returns mock data. Implement in Phase 6.
    """
    logger.info(
        "Getting classification accuracy",
        extra={"days_back": days_back}
    )

    # TODO Phase 6: Query enrichment_meta table for pm_corrected=true records
    # SELECT
    #   COUNT(*) as total,
    #   SUM(CASE WHEN pm_corrected THEN 1 ELSE 0 END) as corrections
    # FROM enrichment_meta
    # WHERE created_at > NOW() - INTERVAL '7 days'

    return {
        "total_agent_classifications": 0,
        "pm_corrections": 0,
        "correction_rate": 0.0,
        "accuracy_rate": 0.0,
        "corrections_by_area": {},
        "time_window": {
            "days_back": days_back,
            "start_date": (datetime.utcnow() - timedelta(days=days_back)).date().isoformat(),
            "end_date": datetime.utcnow().date().isoformat(),
        },
        "note": "Enrichment metadata not persisted yet. Add enrichment_meta table in Phase 6."
    }


def get_rule_usage_stats() -> Dict[str, Any]:
    """
    Get statistics on which disambiguation/compliance rules fire most often.

    Analyzes rule engine to show:
    - Most frequently matched rules
    - Rules that never match (candidates for removal)
    - Average confidence scores per rule

    Returns:
        Dictionary with rule usage statistics:
        {
            "disambiguation_rules": [
                {
                    "rule_id": "leave_absence",
                    "match_count": 1234,
                    "avg_confidence": 0.95,
                    "last_matched": "2026-07-01T10:30:00Z"
                },
                ...
            ],
            "compliance_rules": [
                {
                    "regulation": "GOSI",
                    "match_count": 456,
                    "tags_applied": 456
                },
                ...
            ],
            "unused_rules": ["old_rule_1", "deprecated_rule_2"]
        }

    Note:
        Currently returns rule definitions from YAML.
        In Phase 6, track actual match counts in database or Redis.
    """
    from .rule_engine import get_rule_engine

    logger.info("Getting rule usage statistics")

    rule_engine = get_rule_engine()

    # Get loaded rule counts
    disambiguation_rules = []
    for rule in rule_engine.disambiguation_rules:
        disambiguation_rules.append({
            "term": rule.term,
            "variants": len(rule.variants),
            "match_count": 0,  # TODO: Track in Redis or DB
            "note": "Match counts not tracked yet"
        })

    compliance_rules = []
    for regulation in rule_engine.compliance_regulations:
        compliance_rules.append({
            "regulation": regulation.name_en,
            "keywords_count": len(regulation.keywords_en) + len(regulation.keywords_ar),
            "match_count": 0,  # TODO: Track in Redis or DB
            "note": "Match counts not tracked yet"
        })

    scope_rules = []
    for scope in rule_engine.l1_scopes:
        scope_rules.append({
            "scope": scope.scope,
            "keywords_count": len(scope.keywords_en) + len(scope.keywords_ar),
            "match_count": 0,  # TODO: Track in Redis or DB
            "note": "Match counts not tracked yet"
        })

    return {
        "loaded_at": rule_engine._last_load_time.isoformat() if rule_engine._last_load_time else None,
        "disambiguation_rules": {
            "total": len(disambiguation_rules),
            "rules": disambiguation_rules[:10],  # Top 10
        },
        "compliance_rules": {
            "total": len(compliance_rules),
            "rules": compliance_rules,
        },
        "scope_rules": {
            "total": len(scope_rules),
            "rules": scope_rules[:10],  # Top 10
        },
        "note": "Rule match tracking not implemented yet. Add Redis counters in Phase 6."
    }


async def get_disagreement_rate(
    db: AsyncSession,
    limit: int = 100,
) -> Dict[str, Any]:
    """
    Calculate disagreement rate between agent and old pipeline.

    Useful for monitoring during gradual rollout. High disagreement rate
    may indicate agent pipeline needs tuning.

    Args:
        db: Database session
        limit: Number of recent items to compare

    Returns:
        Dictionary with disagreement analysis:
        {
            "total_compared": 100,
            "agreements": 87,
            "disagreements": 13,
            "agreement_rate": 0.87,
            "disagreement_patterns": {
                "old_area → agent_area": count,
                ...
            }
        }

    Note:
        Requires both pipelines to persist classifications.
        Currently returns mock data. Implement in Phase 6.
    """
    logger.info(
        "Getting pipeline disagreement rate",
        extra={"limit": limit}
    )

    # TODO Phase 6: Query classification table for items with both agent and LLM results
    # Compare product_area fields and aggregate disagreements

    return {
        "total_compared": 0,
        "agreements": 0,
        "disagreements": 0,
        "agreement_rate": 0.0,
        "disagreement_patterns": {},
        "note": "Pipeline comparison not implemented yet. Use scripts/compare_pipelines.py for offline analysis."
    }


async def get_dashboard_summary(
    db: AsyncSession
) -> Dict[str, Any]:
    """
    Get high-level summary for monitoring dashboard.

    Combines key metrics from all analytics functions into a single view.

    Args:
        db: Database session

    Returns:
        Dictionary with dashboard summary:
        {
            "feature_status": {...},
            "rollout_metrics": {...},
            "agent_health": {...},
            "classification_accuracy": {...},
            "rule_engine_status": {...}
        }
    """
    from .feature_flags import get_feature_status

    logger.info("Getting dashboard summary")

    # Get feature flag status
    feature_status = get_feature_status()

    # Get agent metrics (24h)
    agent_metrics = await get_agent_metrics(db, hours_back=24)

    # Get classification accuracy (7 days)
    accuracy = await get_classification_accuracy(db, days_back=7)

    # Get rule usage stats
    rule_stats = get_rule_usage_stats()

    # Get disagreement rate
    disagreement = await get_disagreement_rate(db, limit=100)

    return {
        "timestamp": datetime.utcnow().isoformat(),
        "feature_status": feature_status,
        "agent_metrics_24h": agent_metrics,
        "classification_accuracy_7d": accuracy,
        "rule_engine": rule_stats,
        "pipeline_comparison": disagreement,
    }
