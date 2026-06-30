"""Clustering service for theme generation with stable identity."""
import logging
from typing import List, Dict, Tuple, Optional
import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import hdbscan
from collections import defaultdict, Counter

from app.models.feedback import Feedback
from app.models.theme import Theme, ThemeTrend
from app.repositories.theme import ThemeRepository
from app.repositories.clustering import ClusteringRunRepository
from app.ai.llm_provider import LLMProvider

logger = logging.getLogger(__name__)


class ClusteringService:
    """Service for clustering feedback into themes with stable identity.

    Uses HDBSCAN for clustering embeddings, then matches new clusters to
    existing themes by centroid similarity to maintain stable theme identity.
    """

    def __init__(self, session: AsyncSession, llm_provider: LLMProvider):
        self.session = session
        self.llm_provider = llm_provider
        self.theme_repo = ThemeRepository(session)
        self.run_repo = ClusteringRunRepository(session)

    async def get_enriched_feedback(self, days: int = 7) -> List[Feedback]:
        """Get feedback with embeddings from last N days.

        Args:
            days: Number of days to look back

        Returns:
            List of feedback items with embeddings
        """
        from datetime import datetime, timedelta
        cutoff = datetime.utcnow() - timedelta(days=days)

        result = await self.session.execute(
            select(Feedback)
            .where(Feedback.embedding.isnot(None))
            .where(Feedback.created_at >= cutoff)
            .order_by(Feedback.created_at.desc())
        )
        feedback_list = list(result.scalars().all())
        logger.info(f"Retrieved {len(feedback_list)} enriched feedback items from last {days} days")
        return feedback_list

    def cluster_embeddings(
        self,
        embeddings: np.ndarray,
        min_cluster_size: int = 5,
        min_samples: int = 3,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Cluster embeddings using HDBSCAN.

        Args:
            embeddings: Array of shape (n_samples, n_features)
            min_cluster_size: Minimum cluster size
            min_samples: Minimum samples for core points

        Returns:
            Tuple of (cluster_labels, cluster_probabilities)
            Labels are -1 for noise, 0+ for clusters
        """
        logger.info(f"Clustering {len(embeddings)} embeddings with HDBSCAN")

        clusterer = hdbscan.HDBSCAN(
            min_cluster_size=min_cluster_size,
            min_samples=min_samples,
            metric="cosine",
            cluster_selection_method="eom",  # Excess of mass
        )

        labels = clusterer.fit_predict(embeddings)
        probabilities = clusterer.probabilities_

        n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
        n_noise = list(labels).count(-1)
        logger.info(f"Found {n_clusters} clusters, {n_noise} noise points")

        return labels, probabilities

    def calculate_cluster_centroid(
        self,
        embeddings: np.ndarray,
        indices: List[int],
    ) -> np.ndarray:
        """Calculate cluster centroid (mean embedding).

        Args:
            embeddings: All embeddings
            indices: Indices of embeddings in this cluster

        Returns:
            Centroid vector (mean of cluster embeddings)
        """
        cluster_embeddings = embeddings[indices]
        centroid = np.mean(cluster_embeddings, axis=0)
        # Normalize to unit vector for cosine similarity
        centroid = centroid / np.linalg.norm(centroid)
        return centroid

    async def match_or_create_theme(
        self,
        centroid: np.ndarray,
        feedback_items: List[Feedback],
        run_id: str,
    ) -> Theme:
        """Match cluster to existing theme or create new one.

        Args:
            centroid: Cluster centroid vector
            feedback_items: Feedback items in this cluster
            run_id: Current clustering run ID

        Returns:
            Matched or created theme
        """
        # Try to find similar existing theme
        similar_theme = await self.theme_repo.find_similar_theme(
            centroid=centroid.tolist(),
            similarity_threshold=0.7,  # 70% similarity
        )

        if similar_theme:
            logger.info(f"Matched cluster to existing theme {similar_theme.id}: {similar_theme.name_en}")
            return similar_theme

        # Create new theme
        theme_name = await self.generate_theme_name(feedback_items)
        theme_description = await self.generate_theme_description(feedback_items)

        new_theme = await self.theme_repo.create(
            name_en=theme_name,
            description_en=theme_description,
            centroid=centroid.tolist(),
            run_id=run_id,
        )
        logger.info(f"Created new theme {new_theme.id}: {theme_name}")
        return new_theme

    async def generate_theme_name(self, feedback_items: List[Feedback]) -> str:
        """Generate theme name using LLM.

        Args:
            feedback_items: Feedback items in cluster

        Returns:
            Short theme name (3-5 words)
        """
        # Take up to 5 representative feedback items
        sample_feedback = feedback_items[:5]
        feedback_text = "\n".join([f"- {f.title}: {f.content[:200]}" for f in sample_feedback])

        prompt = f"""Analyze these customer feedback items and generate a short, descriptive theme name (3-5 words).

Feedback items:
{feedback_text}

Theme name:"""

        response = await self.llm_provider.complete(
            prompt=prompt,
            max_tokens=20,
            temperature=0.3,
        )

        theme_name = response.strip().strip('"').strip("'")
        return theme_name[:100]  # Max length

    async def generate_theme_description(self, feedback_items: List[Feedback]) -> str:
        """Generate theme description using LLM.

        Args:
            feedback_items: Feedback items in cluster

        Returns:
            Theme description (1-2 sentences)
        """
        sample_feedback = feedback_items[:10]
        feedback_text = "\n".join([f"- {f.title}: {f.content[:200]}" for f in sample_feedback])

        prompt = f"""Analyze these customer feedback items and write a 1-2 sentence description of the common theme.

Feedback items:
{feedback_text}

Description:"""

        response = await self.llm_provider.complete(
            prompt=prompt,
            max_tokens=100,
            temperature=0.3,
        )

        return response.strip()

    async def calculate_theme_metadata(
        self,
        feedback_items: List[Feedback],
    ) -> Dict:
        """Calculate theme metadata (counts, vote weight, etc).

        Args:
            feedback_items: Feedback items in theme

        Returns:
            Dict with item_count, customer_count, vote_weight
        """
        item_count = len(feedback_items)

        # Count unique customers
        customer_ids = {f.customer_id for f in feedback_items if f.customer_id}
        customer_count = len(customer_ids)

        # TODO: Calculate vote weight from vote table when implemented
        vote_weight = item_count  # Placeholder: 1 vote per feedback

        return {
            "item_count": item_count,
            "customer_count": customer_count,
            "vote_weight": vote_weight,
        }

    async def cluster_and_generate_themes(
        self,
        days: int = 7,
        min_cluster_size: int = 5,
    ) -> Dict:
        """Full clustering pipeline: cluster → match → update themes.

        Args:
            days: Days of feedback to cluster
            min_cluster_size: Minimum cluster size for HDBSCAN

        Returns:
            Summary dict with counts and theme IDs
        """
        # Create clustering run
        run = await self.run_repo.create_run()
        run_id = str(run.id)

        try:
            # Get enriched feedback
            feedback_list = await self.get_enriched_feedback(days=days)
            if len(feedback_list) < min_cluster_size:
                logger.warning(f"Not enough feedback items ({len(feedback_list)} < {min_cluster_size})")
                await self.run_repo.complete_run(run_id, item_count=0, status="skipped")
                return {"run_id": run_id, "status": "skipped", "reason": "insufficient_data"}

            # Extract embeddings
            embeddings = np.array([f.embedding for f in feedback_list])

            # Cluster
            labels, probabilities = self.cluster_embeddings(
                embeddings,
                min_cluster_size=min_cluster_size,
            )

            # Group feedback by cluster
            clusters: Dict[int, List[int]] = defaultdict(list)
            for idx, label in enumerate(labels):
                if label != -1:  # Skip noise
                    clusters[label].append(idx)

            # Process each cluster
            themes_created = []
            themes_updated = []

            for cluster_id, indices in clusters.items():
                # Calculate centroid
                centroid = self.calculate_cluster_centroid(embeddings, indices)

                # Get feedback items
                cluster_feedback = [feedback_list[i] for i in indices]

                # Match or create theme
                theme = await self.match_or_create_theme(
                    centroid=centroid,
                    feedback_items=cluster_feedback,
                    run_id=run_id,
                )

                # Calculate metadata
                metadata = await self.calculate_theme_metadata(cluster_feedback)

                # Update theme
                await self.theme_repo.update_theme_metadata(
                    theme_id=str(theme.id),
                    item_count=metadata["item_count"],
                    customer_count=metadata["customer_count"],
                    vote_weight=metadata["vote_weight"],
                    centroid=centroid.tolist(),
                    run_id=run_id,
                )

                # Add theme memberships
                for feedback_item in cluster_feedback:
                    await self.run_repo.add_membership(
                        theme_id=str(theme.id),
                        feedback_id=str(feedback_item.id),
                        run_id=run_id,
                        similarity=float(probabilities[cluster_feedback.index(feedback_item)]),
                    )

                if theme.trend == ThemeTrend.NEW:
                    themes_created.append(str(theme.id))
                else:
                    themes_updated.append(str(theme.id))

            # Deactivate stale themes
            deactivated = await self.theme_repo.deactivate_stale_themes(run_id)

            # Complete run
            await self.run_repo.complete_run(
                run_id,
                item_count=len(feedback_list),
                status="completed",
            )

            # Commit all changes
            await self.session.commit()

            logger.info(
                f"Clustering complete: {len(themes_created)} new themes, "
                f"{len(themes_updated)} updated, {deactivated} deactivated"
            )

            return {
                "run_id": run_id,
                "status": "completed",
                "feedback_count": len(feedback_list),
                "cluster_count": len(clusters),
                "themes_created": themes_created,
                "themes_updated": themes_updated,
                "themes_deactivated": deactivated,
            }

        except Exception as e:
            logger.error(f"Clustering failed: {e}", exc_info=True)
            await self.run_repo.complete_run(run_id, item_count=0, status="failed")
            await self.session.commit()
            raise
