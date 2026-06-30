"""Product bet generation service using LLM."""
import logging
from typing import List, Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import json

from app.models.feedback import Feedback
from app.models.theme import Theme
from app.models.bet import ProductBet, Segment
from app.models.clustering import ThemeMembership
from app.repositories.theme import ThemeRepository
from app.repositories.bet import BetRepository
from app.ai.llm_provider import LLMProvider

logger = logging.getLogger(__name__)


class BetGenerationService:
    """Service for generating product bets from themes using LLM.

    Analyzes top themes by vote weight and generates AI-drafted product
    opportunities with problem statements, affected segments, and impact estimates.
    """

    def __init__(self, session: AsyncSession, llm_provider: LLMProvider):
        self.session = session
        self.llm_provider = llm_provider
        self.theme_repo = ThemeRepository(session)
        self.bet_repo = BetRepository(session)

    async def get_theme_feedback(self, theme_id: str, limit: int = 20) -> List[Feedback]:
        """Get feedback items for a theme (from latest clustering run).

        Args:
            theme_id: Theme ID
            limit: Maximum number of feedback items to retrieve

        Returns:
            List of feedback items in this theme
        """
        # Get latest run ID for this theme
        theme = await self.theme_repo.get_by_id(theme_id)
        if not theme or not theme.last_run_id:
            return []

        # Get feedback via theme membership
        result = await self.session.execute(
            select(Feedback)
            .join(ThemeMembership, ThemeMembership.feedback_id == Feedback.id)
            .where(ThemeMembership.theme_id == theme_id)
            .where(ThemeMembership.run_id == theme.last_run_id)
            .order_by(ThemeMembership.similarity.desc())
            .limit(limit)
        )
        feedback_list = list(result.scalars().all())
        logger.info(f"Retrieved {len(feedback_list)} feedback items for theme {theme_id}")
        return feedback_list

    async def generate_bet_from_theme(self, theme: Theme) -> Dict:
        """Generate product bet draft from theme using LLM.

        Args:
            theme: Theme to generate bet from

        Returns:
            Dict with title, problem_statement, why_now, affected_segments
        """
        # Get representative feedback
        feedback_items = await self.get_theme_feedback(str(theme.id), limit=10)

        if not feedback_items:
            logger.warning(f"No feedback found for theme {theme.id}, skipping bet generation")
            return {}

        # Build context for LLM
        feedback_text = "\n".join([
            f"- [{f.classification or 'unknown'}] {f.title}: {f.content[:200]}"
            for f in feedback_items[:5]
        ])

        prompt = f"""You are a product manager analyzing customer feedback themes to identify product opportunities.

Theme: {theme.name_en}
Description: {theme.description_en}
Customer Impact: {theme.customer_count} customers, {theme.item_count} feedback items

Representative Feedback:
{feedback_text}

Based on this theme, draft a product bet (opportunity) with the following structure:

1. Title: A concise, action-oriented title (5-8 words)
2. Problem Statement: What customer problem does this address? (2-3 sentences)
3. Why Now: Why is this important to address now? (1-2 sentences)
4. Affected Segments: Which customer segments are impacted? Choose from: enterprise, smb, individual, all

Return ONLY a valid JSON object with these fields:
{{
  "title": "...",
  "problem_statement": "...",
  "why_now": "...",
  "affected_segments": ["enterprise" | "smb" | "individual" | "all"]
}}"""

        response = await self.llm_provider.complete(
            prompt=prompt,
            max_tokens=500,
            temperature=0.4,
        )

        # Parse JSON response
        try:
            # Extract JSON from response (handle markdown code blocks)
            response_text = response.strip()
            if response_text.startswith("```"):
                # Remove markdown code block markers
                lines = response_text.split("\n")
                response_text = "\n".join(lines[1:-1]) if len(lines) > 2 else response_text

            bet_data = json.loads(response_text)

            # Validate and convert segments
            valid_segments = {"enterprise", "smb", "individual", "all"}
            segments = [
                Segment(seg) for seg in bet_data.get("affected_segments", [])
                if seg in valid_segments
            ]

            return {
                "title": bet_data.get("title", "")[:200],
                "problem_statement": bet_data.get("problem_statement", ""),
                "why_now": bet_data.get("why_now", ""),
                "affected_segments": segments,
            }
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to parse LLM response for theme {theme.id}: {e}")
            logger.debug(f"Raw response: {response}")
            return {}

    def calculate_affected_segments(self, feedback_items: List[Feedback]) -> List[Segment]:
        """Analyze feedback to determine affected customer segments.

        Args:
            feedback_items: Feedback items in theme

        Returns:
            List of affected segments based on customer data
        """
        # TODO: Implement segment analysis based on customer attributes
        # For now, return placeholder based on customer count
        # In production, join with customer table and analyze company size, plan tier, etc.

        if len(feedback_items) > 50:
            return [Segment.ALL]
        elif len(feedback_items) > 20:
            return [Segment.ENTERPRISE, Segment.SMB]
        else:
            return [Segment.ENTERPRISE]

    def estimate_customer_impact(self, theme: Theme) -> int:
        """Estimate number of customers affected by this theme.

        Args:
            theme: Theme to estimate impact for

        Returns:
            Estimated customer count
        """
        # Use theme metadata directly
        return theme.customer_count

    async def generate_bets_from_top_themes(
        self,
        limit: int = 5,
        min_customers: int = 3,
    ) -> Dict:
        """Generate product bets from top themes by vote weight.

        Args:
            limit: Maximum number of bets to generate
            min_customers: Minimum customer count threshold

        Returns:
            Summary dict with created bet IDs
        """
        # Get top themes
        top_themes = await self.theme_repo.get_top_themes(limit=limit)

        if not top_themes:
            logger.warning("No themes found for bet generation")
            return {"status": "skipped", "reason": "no_themes"}

        bets_created = []

        for theme in top_themes:
            # Skip themes with low customer impact
            if theme.customer_count < min_customers:
                logger.info(f"Skipping theme {theme.id}: only {theme.customer_count} customers")
                continue

            # Generate bet using LLM
            bet_data = await self.generate_bet_from_theme(theme)

            if not bet_data or not bet_data.get("title"):
                logger.warning(f"Failed to generate bet for theme {theme.id}")
                continue

            # Estimate customer impact
            est_customer_count = self.estimate_customer_impact(theme)

            # Create bet
            bet = await self.bet_repo.create(
                title=bet_data["title"],
                problem_statement=bet_data.get("problem_statement"),
                theme_id=str(theme.id),
                affected_segments=bet_data.get("affected_segments", []),
                est_customer_count=est_customer_count,
                why_now=bet_data.get("why_now"),
            )

            # Link evidence (feedback items from theme)
            feedback_items = await self.get_theme_feedback(str(theme.id), limit=100)
            feedback_ids = [str(f.id) for f in feedback_items]

            if feedback_ids:
                await self.bet_repo.add_evidence(
                    bet_id=str(bet.id),
                    feedback_ids=feedback_ids,
                )

            bets_created.append(str(bet.id))
            logger.info(
                f"Created bet {bet.id}: {bet.title} "
                f"(theme={theme.id}, evidence={len(feedback_ids)})"
            )

        # Commit all changes
        await self.session.commit()

        logger.info(f"Generated {len(bets_created)} bets from {len(top_themes)} themes")

        return {
            "status": "completed",
            "themes_analyzed": len(top_themes),
            "bets_created": len(bets_created),
            "bet_ids": bets_created,
        }

    async def regenerate_bet(self, bet_id: str) -> ProductBet:
        """Regenerate bet content using LLM (preserves status and ownership).

        Args:
            bet_id: Bet ID to regenerate

        Returns:
            Updated bet
        """
        bet = await self.bet_repo.get_by_id(bet_id)
        if not bet:
            raise ValueError(f"Bet {bet_id} not found")

        if not bet.theme_id:
            raise ValueError(f"Bet {bet_id} has no associated theme")

        # Get theme
        theme = await self.theme_repo.get_by_id(str(bet.theme_id))
        if not theme:
            raise ValueError(f"Theme {bet.theme_id} not found")

        # Generate new bet data
        bet_data = await self.generate_bet_from_theme(theme)

        if not bet_data or not bet_data.get("title"):
            raise ValueError(f"Failed to regenerate bet for theme {theme.id}")

        # Update bet (preserve status, owner_pm, declined_reason)
        bet.title = bet_data["title"]
        bet.problem_statement = bet_data.get("problem_statement")
        bet.why_now = bet_data.get("why_now")
        bet.affected_segments = bet_data.get("affected_segments", [])
        bet.est_customer_count = self.estimate_customer_impact(theme)

        await self.session.flush()
        await self.session.commit()

        logger.info(f"Regenerated bet {bet_id}: {bet.title}")
        return bet
