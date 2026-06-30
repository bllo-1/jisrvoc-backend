"""Feedback item repository for database operations and aggregations."""

from typing import Optional, List, Tuple, Dict
from datetime import datetime, timedelta
from uuid import UUID
from sqlalchemy import select, and_, func, or_, desc, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.feedback_item import (
    FeedbackItem,
    FeedbackCategory,
    ProductArea,
    Sentiment,
    Urgency,
    Language,
    Segment
)
from app.repositories.base import BaseRepository


class FeedbackItemRepository(BaseRepository[FeedbackItem]):
    """Repository for FeedbackItem model operations and aggregations."""

    def __init__(self, session: AsyncSession):
        """Initialize feedback item repository."""
        super().__init__(FeedbackItem, session)

    # ==================== Basic CRUD ====================

    async def get_by_parent_ticket(self, parent_ticket_id: UUID) -> List[FeedbackItem]:
        """Get all feedback items from a parent ticket.

        Args:
            parent_ticket_id: Parent raw_ticket ID

        Returns:
            List of feedback items
        """
        result = await self.session.execute(
            select(FeedbackItem)
            .where(FeedbackItem.parent_ticket_id == parent_ticket_id)
            .order_by(FeedbackItem.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_by_customer(
        self, customer_id: str, limit: int = 100
    ) -> List[FeedbackItem]:
        """Get all feedback for a customer.

        Args:
            customer_id: Customer ID (HubSpot company ID)
            limit: Maximum number of results

        Returns:
            List of feedback items
        """
        result = await self.session.execute(
            select(FeedbackItem)
            .where(FeedbackItem.customer_id == customer_id)
            .order_by(FeedbackItem.occurred_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_unenriched(self, limit: int = 100) -> List[FeedbackItem]:
        """Get feedback items without enrichment.

        Args:
            limit: Maximum number of results

        Returns:
            List of unenriched feedback items
        """
        result = await self.session.execute(
            select(FeedbackItem)
            .where(FeedbackItem.category.is_(None))  # No category = not enriched
            .order_by(FeedbackItem.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    # ==================== Aggregations for Overview ====================

    async def get_total_count(self) -> int:
        """Get total count of feedback items.

        Returns:
            Total count
        """
        result = await self.session.execute(
            select(func.count()).select_from(FeedbackItem)
        )
        return result.scalar_one()

    async def get_high_urgency_count(self) -> int:
        """Get count of high urgency feedback items.

        Returns:
            Count of high urgency items
        """
        result = await self.session.execute(
            select(func.count())
            .select_from(FeedbackItem)
            .where(FeedbackItem.urgency == Urgency.HIGH)
        )
        return result.scalar_one()

    async def get_urgency_distribution(self) -> Dict[str, int]:
        """Get distribution of feedback by urgency level.

        Returns:
            Dictionary mapping urgency level to count
        """
        result = await self.session.execute(
            select(
                FeedbackItem.urgency,
                func.count().label('count')
            )
            .where(FeedbackItem.urgency.is_not(None))
            .group_by(FeedbackItem.urgency)
        )

        distribution = {"low": 0, "medium": 0, "high": 0}
        for row in result:
            if row.urgency:
                distribution[row.urgency.value] = row.count

        return distribution

    async def get_volume_trend(self, weeks: int = 12) -> List[Dict]:
        """Get weekly volume trend for the specified number of weeks.

        Args:
            weeks: Number of weeks to look back

        Returns:
            List of dicts with week_start and count
        """
        cutoff_date = datetime.utcnow() - timedelta(weeks=weeks)

        result = await self.session.execute(
            select(
                func.date_trunc('week', FeedbackItem.occurred_at).label('week_start'),
                func.count().label('count')
            )
            .where(
                and_(
                    FeedbackItem.occurred_at.is_not(None),
                    FeedbackItem.occurred_at >= cutoff_date
                )
            )
            .group_by(text('week_start'))
            .order_by(text('week_start'))
        )

        return [
            {"week_start": row.week_start.date() if row.week_start else None, "count": row.count}
            for row in result
        ]

    async def get_by_source_distribution(self) -> List[Dict]:
        """Get distribution of feedback by source type.

        Returns:
            List of dicts with key (source) and count
        """
        # Join with raw_ticket to get source_type
        from app.models.raw_ticket import RawTicket

        result = await self.session.execute(
            select(
                RawTicket.source_type.label('key'),
                func.count().label('count')
            )
            .select_from(FeedbackItem)
            .join(RawTicket, FeedbackItem.parent_ticket_id == RawTicket.id)
            .group_by(RawTicket.source_type)
            .order_by(desc('count'))
        )

        return [
            {"key": row.key.value if row.key else "unknown", "count": row.count}
            for row in result
        ]

    async def get_by_area_distribution(self) -> List[Dict]:
        """Get distribution of feedback by product area.

        Returns:
            List of dicts with key (area) and count
        """
        result = await self.session.execute(
            select(
                FeedbackItem.area.label('key'),
                func.count().label('count')
            )
            .where(FeedbackItem.area.is_not(None))
            .group_by(FeedbackItem.area)
            .order_by(desc('count'))
        )

        return [
            {"key": row.key.value if row.key else "unknown", "count": row.count}
            for row in result
        ]

    # ==================== Complex Filtering ====================

    async def list_with_filters(
        self,
        source: Optional[str] = None,
        area: Optional[ProductArea] = None,
        category: Optional[FeedbackCategory] = None,
        sentiment: Optional[Sentiment] = None,
        urgency: Optional[Urgency] = None,
        language: Optional[Language] = None,
        segment: Optional[Segment] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        search_query: Optional[str] = None,
        cursor: Optional[str] = None,
        limit: int = 50
    ) -> Tuple[List[FeedbackItem], Optional[str], int]:
        """List feedback with complex filtering and cursor pagination.

        Args:
            source: Filter by source type
            area: Filter by product area
            category: Filter by category
            sentiment: Filter by sentiment
            urgency: Filter by urgency
            language: Filter by language
            segment: Filter by segment
            date_from: Filter by start date
            date_to: Filter by end date
            search_query: Full-text search in summary_en
            cursor: Cursor for pagination (ISO timestamp)
            limit: Max results per page

        Returns:
            Tuple of (items, next_cursor, total_count)
        """
        from app.models.raw_ticket import RawTicket

        # Build base query
        query = select(FeedbackItem).options(
            joinedload(FeedbackItem.parent_ticket)
        )

        # Apply filters
        filters = []

        if source:
            # Join with raw_ticket for source filter
            query = query.join(RawTicket, FeedbackItem.parent_ticket_id == RawTicket.id)
            filters.append(RawTicket.source_type == source)

        if area:
            filters.append(FeedbackItem.area == area)

        if category:
            filters.append(FeedbackItem.category == category)

        if sentiment:
            filters.append(FeedbackItem.sentiment == sentiment)

        if urgency:
            filters.append(FeedbackItem.urgency == urgency)

        if language:
            filters.append(FeedbackItem.language == language)

        if segment:
            filters.append(FeedbackItem.segment == segment)

        if date_from:
            filters.append(FeedbackItem.occurred_at >= date_from)

        if date_to:
            filters.append(FeedbackItem.occurred_at <= date_to)

        if search_query:
            # Full-text search on summary_en
            filters.append(
                func.to_tsvector('english', FeedbackItem.summary_en).op('@@')(
                    func.plainto_tsquery('english', search_query)
                )
            )

        if cursor:
            # Cursor pagination: occurred_at < cursor
            cursor_dt = datetime.fromisoformat(cursor)
            filters.append(FeedbackItem.occurred_at < cursor_dt)

        if filters:
            query = query.where(and_(*filters))

        # Get total count (without pagination)
        count_query = select(func.count()).select_from(FeedbackItem)
        if filters:
            count_query = count_query.where(and_(*filters))

        total_result = await self.session.execute(count_query)
        total_count = total_result.scalar_one()

        # Apply ordering and limit
        query = query.order_by(FeedbackItem.occurred_at.desc()).limit(limit)

        # Execute query
        result = await self.session.execute(query)
        items = list(result.scalars().all())

        # Generate next cursor
        next_cursor = None
        if items and len(items) == limit:
            # More results may exist
            last_item = items[-1]
            if last_item.occurred_at:
                next_cursor = last_item.occurred_at.isoformat()

        return items, next_cursor, total_count
