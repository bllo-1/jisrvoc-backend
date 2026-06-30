"""Feedback repository for database operations."""

from typing import Optional, List
from datetime import datetime
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.feedback import Feedback
from app.repositories.base import BaseRepository


class FeedbackRepository(BaseRepository[Feedback]):
    """Repository for Feedback model operations."""

    def __init__(self, session: AsyncSession):
        """Initialize feedback repository."""
        super().__init__(Feedback, session)

    async def get_by_source_and_external_id(
        self, source: str, external_id: str
    ) -> Optional[Feedback]:
        """Get feedback by source and external ID.

        Args:
            source: Source system (hubspot, zendesk, etc)
            external_id: External ID from source system

        Returns:
            Feedback instance or None if not found
        """
        result = await self.session.execute(
            select(Feedback).where(
                and_(
                    Feedback.source == source,
                    Feedback.external_id == external_id
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_by_customer(
        self, customer_id: int, limit: int = 100
    ) -> List[Feedback]:
        """Get all feedback for a customer.

        Args:
            customer_id: Customer ID
            limit: Maximum number of results

        Returns:
            List of feedback items
        """
        result = await self.session.execute(
            select(Feedback)
            .where(Feedback.customer_id == customer_id)
            .order_by(Feedback.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_company(
        self, company_id: int, limit: int = 100
    ) -> List[Feedback]:
        """Get all feedback for a company.

        Args:
            company_id: Company ID
            limit: Maximum number of results

        Returns:
            List of feedback items
        """
        result = await self.session.execute(
            select(Feedback)
            .where(Feedback.company_id == company_id)
            .order_by(Feedback.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_unclassified(self, limit: int = 100) -> List[Feedback]:
        """Get feedback items without classification.

        Args:
            limit: Maximum number of results

        Returns:
            List of unclassified feedback items
        """
        from app.models.classification import Classification

        # Use NOT EXISTS subquery to find feedback without classifications
        subquery = select(1).where(Classification.feedback_id == Feedback.id).exists()

        result = await self.session.execute(
            select(Feedback)
            .where(~subquery)
            .order_by(Feedback.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_date_range(
        self,
        start_date: datetime,
        end_date: datetime,
        limit: int = 1000
    ) -> List[Feedback]:
        """Get feedback within a date range.

        Args:
            start_date: Start date
            end_date: End date
            limit: Maximum number of results

        Returns:
            List of feedback items
        """
        result = await self.session.execute(
            select(Feedback)
            .where(
                and_(
                    Feedback.created_at >= start_date,
                    Feedback.created_at <= end_date
                )
            )
            .order_by(Feedback.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
