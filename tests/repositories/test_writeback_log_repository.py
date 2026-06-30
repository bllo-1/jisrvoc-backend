"""Tests for writeback log repository."""

import pytest
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import Column, String, Text, DateTime, Enum as SQLEnum, UUID as SQLUUID
from sqlalchemy.sql import func
import uuid
import enum

from app.repositories.writeback_log import WritebackLogRepository
from app.models.bet import WritebackLog, BetStatus
from app.db.base import Base


# Test database URL (in-memory SQLite)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


# Minimal ProductBet model for testing (without ARRAY types)
class TestProductBet(Base):
    """Minimal bet model for testing without PostgreSQL-specific types."""
    __tablename__ = "product_bet"
    __table_args__ = {'extend_existing': True}

    id = Column(SQLUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String, nullable=False)
    problem_statement = Column(Text, nullable=True)
    status = Column(SQLEnum(BetStatus, name="bet_status"), nullable=False, default=BetStatus.DRAFT)
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, default=func.now(), onupdate=func.now())


@pytest.fixture
async def db_session():
    """Create test database session."""
    # Create async engine
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)

    # Create only the tables needed for testing
    async with engine.begin() as conn:
        await conn.run_sync(TestProductBet.metadata.create_all)
        await conn.run_sync(WritebackLog.metadata.create_all)

    # Create session
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        yield session

    # Drop tables
    async with engine.begin() as conn:
        await conn.run_sync(TestProductBet.metadata.drop_all)
        await conn.run_sync(WritebackLog.metadata.drop_all)

    await engine.dispose()


@pytest.fixture
def writeback_log_repo(db_session):
    """Create writeback log repository."""
    return WritebackLogRepository(db_session)


@pytest.fixture
async def test_bet(db_session):
    """Create a test bet for use in tests."""
    bet = TestProductBet(
        title="Test Bet",
        problem_statement="Test problem",
    )
    db_session.add(bet)
    await db_session.flush()
    await db_session.commit()
    return bet


@pytest.mark.asyncio
async def test_create_log_entry(writeback_log_repo, test_bet, db_session):
    """Test creating a writeback log entry."""
    # Create log entry
    log = await writeback_log_repo.create_log_entry(
        bet_id=str(test_bet.id),
        hubspot_ticket_id="HS-123",
        action="property_update",
        status_value=BetStatus.SHIPPED,
        pm_id="pm@example.com",
        result="success",
    )

    assert log.id is not None
    assert log.bet_id == test_bet.id
    assert log.hubspot_ticket_id == "HS-123"
    assert log.action == "property_update"
    assert log.status_value == BetStatus.SHIPPED
    assert log.pm_id == "pm@example.com"
    assert log.result == "success"
    assert log.performed_at is not None


@pytest.mark.asyncio
async def test_get_logs_for_bet(writeback_log_repo, test_bet, db_session):
    """Test getting all logs for a bet."""
    # Create multiple log entries
    await writeback_log_repo.create_log_entry(
        bet_id=str(test_bet.id),
        hubspot_ticket_id="HS-123",
        action="property_update",
        status_value=BetStatus.DRAFT,
        pm_id="pm@example.com",
        result="success",
    )
    await writeback_log_repo.create_log_entry(
        bet_id=str(test_bet.id),
        hubspot_ticket_id="HS-123",
        action="property_update",
        status_value=BetStatus.SHIPPED,
        pm_id="pm@example.com",
        result="success",
    )
    await writeback_log_repo.commit()

    # Get logs for bet
    logs = await writeback_log_repo.get_logs_for_bet(str(test_bet.id))

    assert len(logs) == 2
    assert all(log.bet_id == test_bet.id for log in logs)


@pytest.mark.asyncio
async def test_get_logs_by_ticket(writeback_log_repo, test_bet, db_session):
    """Test getting logs by HubSpot ticket ID."""
    # Create log entry
    await writeback_log_repo.create_log_entry(
        bet_id=str(test_bet.id),
        hubspot_ticket_id="HS-999",
        action="property_update",
        status_value=BetStatus.SHIPPED,
        pm_id="pm@example.com",
        result="success",
    )
    await writeback_log_repo.commit()

    # Get logs by ticket
    logs = await writeback_log_repo.get_logs_by_ticket("HS-999")

    assert len(logs) == 1
    assert logs[0].hubspot_ticket_id == "HS-999"


@pytest.mark.asyncio
async def test_log_entry_is_immutable(writeback_log_repo, test_bet, db_session):
    """Test that log entries cannot be updated (immutable audit trail)."""
    # Create log entry
    log = await writeback_log_repo.create_log_entry(
        bet_id=str(test_bet.id),
        hubspot_ticket_id="HS-123",
        action="property_update",
        status_value=BetStatus.SHIPPED,
        pm_id="pm@example.com",
        result="success",
    )
    await writeback_log_repo.commit()

    # Verify repository has no update method
    assert not hasattr(writeback_log_repo, 'update')
    assert not hasattr(writeback_log_repo, 'delete')


@pytest.mark.asyncio
async def test_failed_writeback_log(writeback_log_repo, test_bet, db_session):
    """Test logging a failed writeback."""
    # Create failed log entry
    log = await writeback_log_repo.create_log_entry(
        bet_id=str(test_bet.id),
        hubspot_ticket_id="HS-123",
        action="property_update",
        status_value=BetStatus.SHIPPED,
        pm_id="pm@example.com",
        result="failed:HubSpot API rate limit exceeded",
    )

    assert log.result.startswith("failed:")
    assert "rate limit" in log.result
