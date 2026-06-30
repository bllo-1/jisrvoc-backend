"""Celery worker for weekly clustering and theme generation."""
import logging
from typing import Dict

from app.core.celery_app import celery_app
from app.db.session import AsyncSessionLocal
from app.services.clustering import ClusteringService
from app.services.bet_generation import BetGenerationService
from app.services.slack_service import SlackService
from app.ai.llm_provider import create_llm_provider
from app.repositories.theme import ThemeRepository

logger = logging.getLogger(__name__)


@celery_app.task(name="app.workers.clustering_worker.run_weekly_clustering")
def run_weekly_clustering() -> Dict:
    """Weekly clustering task: cluster feedback → generate themes → create bets → send summary.

    Scheduled to run every Monday at 2 AM via Celery Beat.

    Returns:
        Dict with clustering and bet generation results
    """
    logger.info("Starting weekly clustering task")

    # Run async clustering in sync Celery task
    import asyncio
    return asyncio.run(_run_clustering_async())


async def _run_clustering_async() -> Dict:
    """Async implementation of clustering workflow."""
    result = {
        "clustering": {},
        "bet_generation": {},
        "slack_notification": False,
    }

    # Create database session
    async with AsyncSessionLocal() as session:
        try:
            # Initialize services
            llm_provider = create_llm_provider()
            clustering_service = ClusteringService(session, llm_provider)
            bet_service = BetGenerationService(session, llm_provider)
            slack_service = SlackService()

            # Step 1: Run clustering
            logger.info("Step 1/3: Running clustering")
            clustering_result = await clustering_service.cluster_and_generate_themes(
                days=7,  # Last 7 days of feedback
                min_cluster_size=5,  # Minimum 5 items per cluster
            )
            result["clustering"] = clustering_result

            # Check if clustering succeeded
            if clustering_result.get("status") != "completed":
                logger.warning(f"Clustering did not complete: {clustering_result.get('status')}")
                return result

            # Step 2: Generate product bets from top themes
            logger.info("Step 2/3: Generating product bets")
            bet_result = await bet_service.generate_bets_from_top_themes(
                limit=5,  # Top 5 themes
                min_customers=3,  # At least 3 customers
            )
            result["bet_generation"] = bet_result

            # Step 3: Send Slack summary
            logger.info("Step 3/3: Sending Slack summary")
            if slack_service.is_enabled():
                # Get top themes for summary
                theme_repo = ThemeRepository(session)
                top_themes = await theme_repo.get_top_themes(limit=5)

                success = await slack_service.send_clustering_summary(
                    themes_created=len(clustering_result.get("themes_created", [])),
                    themes_updated=len(clustering_result.get("themes_updated", [])),
                    themes_deactivated=clustering_result.get("themes_deactivated", 0),
                    top_themes=top_themes,
                )
                result["slack_notification"] = success

            logger.info(
                f"Weekly clustering complete: "
                f"{len(clustering_result.get('themes_created', []))} new themes, "
                f"{len(bet_result.get('bet_ids', []))} bets generated"
            )

            return result

        except Exception as e:
            logger.error(f"Clustering task failed: {e}", exc_info=True)
            raise


@celery_app.task(name="app.workers.clustering_worker.trigger_manual_clustering")
def trigger_manual_clustering(days: int = 7, min_cluster_size: int = 5) -> Dict:
    """Manually triggered clustering task (called via API).

    Args:
        days: Number of days of feedback to cluster
        min_cluster_size: Minimum cluster size for HDBSCAN

    Returns:
        Dict with clustering results
    """
    logger.info(f"Starting manual clustering task (days={days}, min_cluster_size={min_cluster_size})")

    import asyncio
    return asyncio.run(_run_manual_clustering_async(days, min_cluster_size))


async def _run_manual_clustering_async(days: int, min_cluster_size: int) -> Dict:
    """Async implementation of manual clustering."""
    async with AsyncSessionLocal() as session:
        try:
            llm_provider = create_llm_provider()
            clustering_service = ClusteringService(session, llm_provider)

            result = await clustering_service.cluster_and_generate_themes(
                days=days,
                min_cluster_size=min_cluster_size,
            )

            logger.info(f"Manual clustering complete: {result.get('cluster_count', 0)} clusters found")
            return result

        except Exception as e:
            logger.error(f"Manual clustering task failed: {e}", exc_info=True)
            raise


@celery_app.task(name="app.workers.clustering_worker.generate_bets_for_themes")
def generate_bets_for_themes(limit: int = 5, min_customers: int = 3) -> Dict:
    """Manually triggered bet generation (called via API).

    Args:
        limit: Maximum number of bets to generate
        min_customers: Minimum customer count threshold

    Returns:
        Dict with bet generation results
    """
    logger.info(f"Starting manual bet generation (limit={limit}, min_customers={min_customers})")

    import asyncio
    return asyncio.run(_run_bet_generation_async(limit, min_customers))


async def _run_bet_generation_async(limit: int, min_customers: int) -> Dict:
    """Async implementation of bet generation."""
    async with AsyncSessionLocal() as session:
        try:
            llm_provider = create_llm_provider()
            bet_service = BetGenerationService(session, llm_provider)
            slack_service = SlackService()

            result = await bet_service.generate_bets_from_top_themes(
                limit=limit,
                min_customers=min_customers,
            )

            # Send Slack notifications for each bet
            if slack_service.is_enabled() and result.get("bet_ids"):
                theme_repo = ThemeRepository(session)
                for bet_id in result["bet_ids"][:3]:  # Notify for top 3 bets
                    bet = await bet_service.bet_repo.get_by_id(bet_id)
                    if bet and bet.theme_id:
                        theme = await theme_repo.get_by_id(str(bet.theme_id))
                        if theme:
                            await slack_service.send_bet_notification(
                                bet_title=bet.title,
                                theme_name=theme.name_en,
                                customer_count=bet.est_customer_count or 0,
                                feedback_count=theme.item_count,
                            )

            logger.info(f"Manual bet generation complete: {len(result.get('bet_ids', []))} bets created")
            return result

        except Exception as e:
            logger.error(f"Bet generation task failed: {e}", exc_info=True)
            raise
