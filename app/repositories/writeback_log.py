"""Writeback log repository for immutable audit trail operations."""

import logging
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid

from app.models.bet import WritebackLog, BetStatus

logger = logging.getLogger(__name__)


class WritebackLogRepository:
    """Repository for writeback log operations (append-only, immutable)."""

    def __init__(self, session: AsyncSession):
        """Initialize writeback log repository.

        Args:
            session: Database session
        """
        self.session = session

    async def create_log_entry(
        self,
        bet_id: str,
        hubspot_ticket_id: str,
        action: str,
        status_value: BetStatus,
        pm_id: str,
        result: str,
    ) -> WritebackLog:
        """Create immutable log entry for a write-back action.

        Args:
            bet_id: Product bet ID
            hubspot_ticket_id: HubSpot ticket ID that was updated
            action: Action type ('note' or 'property_update')
            status_value: Bet status value at time of write-back
            pm_id: PM who performed the action (email)
            result: Result of write-back ('success' or 'failed:<reason>')

        Returns:
            Created log entry
        """
        log = WritebackLog(
            bet_id=uuid.UUID(bet_id),
            hubspot_ticket_id=hubspot_ticket_id,
            action=action,
            status_value=status_value,
            pm_id=pm_id,
            result=result,
        )
        self.session.add(log)
        await self.session.flush()
        logger.info(f"Created writeback log {log.id} for bet {bet_id}")
        return log

    async def get_logs_for_bet(self, bet_id: str) -> List[WritebackLog]:
        """Get all writeback logs for a bet (chronological order).

        Args:
            bet_id: Product bet ID

        Returns:
            List of writeback logs ordered by performed_at ascending
        """
        result = await self.session.execute(
            select(WritebackLog)
            .where(WritebackLog.bet_id == uuid.UUID(bet_id))
            .order_by(WritebackLog.performed_at.asc())
        )
        return list(result.scalars().all())

    async def get_logs_by_ticket(self, hubspot_ticket_id: str) -> List[WritebackLog]:
        """Get all writeback logs for a specific HubSpot ticket.

        Args:
            hubspot_ticket_id: HubSpot ticket ID

        Returns:
            List of writeback logs ordered by performed_at descending
        """
        result = await self.session.execute(
            select(WritebackLog)
            .where(WritebackLog.hubspot_ticket_id == hubspot_ticket_id)
            .order_by(WritebackLog.performed_at.desc())
        )
        return list(result.scalars().all())

    async def commit(self):
        """Commit the current transaction."""
        await self.session.commit()

    async def rollback(self):
        """Rollback the current transaction."""
        await self.session.rollback()

    # NO UPDATE OR DELETE METHODS - This is an immutable audit trail
