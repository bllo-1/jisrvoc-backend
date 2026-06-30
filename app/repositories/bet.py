"""Product bet repository for CRUD operations."""
import logging
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
import uuid

from app.models.bet import ProductBet, BetStatus, BetEvidence, Segment

logger = logging.getLogger(__name__)


class BetRepository:
    """Repository for product bet CRUD operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        title: str,
        problem_statement: Optional[str] = None,
        theme_id: Optional[str] = None,
        affected_segments: Optional[List[Segment]] = None,
        est_customer_count: Optional[int] = None,
        why_now: Optional[str] = None,
    ) -> ProductBet:
        """Create a new product bet.

        Args:
            title: Bet title
            problem_statement: Problem description
            theme_id: Associated theme ID
            affected_segments: List of affected customer segments
            est_customer_count: Estimated number of affected customers
            why_now: Why this bet is important now

        Returns:
            Created bet instance
        """
        bet = ProductBet(
            title=title,
            problem_statement=problem_statement,
            theme_id=uuid.UUID(theme_id) if theme_id else None,
            affected_segments=affected_segments or [],
            est_customer_count=est_customer_count,
            why_now=why_now,
            status=BetStatus.DRAFT,
        )
        self.session.add(bet)
        await self.session.flush()
        logger.info(f"Created bet {bet.id}: {title}")
        return bet

    async def get_by_id(self, bet_id: str) -> Optional[ProductBet]:
        """Get bet by ID."""
        result = await self.session.execute(
            select(ProductBet).where(ProductBet.id == bet_id)
        )
        return result.scalars().first()

    async def get_by_status(self, status: BetStatus) -> List[ProductBet]:
        """Get all bets with given status."""
        result = await self.session.execute(
            select(ProductBet)
            .where(ProductBet.status == status)
            .order_by(ProductBet.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_by_theme(self, theme_id: str) -> List[ProductBet]:
        """Get all bets for a theme."""
        result = await self.session.execute(
            select(ProductBet)
            .where(ProductBet.theme_id == theme_id)
            .order_by(ProductBet.created_at.desc())
        )
        return list(result.scalars().all())

    async def update_status(
        self,
        bet_id: str,
        status: BetStatus,
        owner_pm: Optional[str] = None,
        declined_reason: Optional[str] = None,
    ) -> ProductBet:
        """Update bet status.

        Args:
            bet_id: Bet ID
            status: New status
            owner_pm: PM who owns this bet
            declined_reason: Reason for decline (if status=DECLINED)

        Returns:
            Updated bet
        """
        bet = await self.get_by_id(bet_id)
        if not bet:
            raise ValueError(f"Bet {bet_id} not found")

        bet.status = status
        if owner_pm:
            bet.owner_pm = owner_pm
        if declined_reason:
            bet.declined_reason = declined_reason

        await self.session.flush()
        logger.info(f"Updated bet {bet_id} status to {status}")
        return bet

    async def add_evidence(
        self,
        bet_id: str,
        feedback_ids: List[str],
    ) -> int:
        """Link feedback items as evidence for this bet.

        Args:
            bet_id: Bet ID
            feedback_ids: List of feedback IDs to link

        Returns:
            Number of evidence links created
        """
        bet = await self.get_by_id(bet_id)
        if not bet:
            raise ValueError(f"Bet {bet_id} not found")

        evidence_count = 0
        for feedback_id in feedback_ids:
            evidence = BetEvidence(
                bet_id=uuid.UUID(bet_id),
                feedback_id=uuid.UUID(feedback_id),
            )
            self.session.add(evidence)
            evidence_count += 1

        await self.session.flush()
        logger.info(f"Added {evidence_count} evidence items to bet {bet_id}")
        return evidence_count

    async def get_hubspot_ticket_ids(self, bet_id: str) -> List[str]:
        """Get HubSpot ticket IDs from bet evidence.

        Traverses: Bet → Evidence → Feedback → RawTicket → external_id (where source=hubspot)

        Args:
            bet_id: Bet ID

        Returns:
            List of HubSpot ticket IDs (external_id from raw_ticket)
        """
        from app.models.feedback_item import FeedbackItem
        from app.models.raw_ticket import RawTicket, SourceType

        result = await self.session.execute(
            select(RawTicket.external_id)
            .select_from(ProductBet)
            .join(BetEvidence, BetEvidence.bet_id == ProductBet.id)
            .join(FeedbackItem, FeedbackItem.id == BetEvidence.feedback_id)
            .join(RawTicket, RawTicket.id == FeedbackItem.parent_ticket_id)
            .where(
                and_(
                    ProductBet.id == bet_id,
                    RawTicket.source_type == SourceType.HUBSPOT
                )
            )
            .distinct()
        )
        ticket_ids = [row[0] for row in result.fetchall()]
        logger.info(f"Found {len(ticket_ids)} HubSpot ticket IDs for bet {bet_id}")
        return ticket_ids

    async def count_in_flight(self) -> int:
        """Count bets that are actively in flight (not shipped or declined).

        In-flight statuses: draft, in_backlog, in_discovery, in_build

        Returns:
            Count of in-flight bets
        """
        result = await self.session.execute(
            select(func.count())
            .select_from(ProductBet)
            .where(
                ProductBet.status.in_([
                    BetStatus.DRAFT,
                    BetStatus.IN_BACKLOG,
                    BetStatus.IN_DISCOVERY,
                    BetStatus.IN_BUILD
                ])
            )
        )
        return result.scalar_one()

    async def commit(self):
        """Commit the current transaction."""
        await self.session.commit()

    async def rollback(self):
        """Rollback the current transaction."""
        await self.session.rollback()
