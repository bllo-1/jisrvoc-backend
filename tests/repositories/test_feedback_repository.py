"""Tests for feedback repository."""

import pytest
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.repositories.feedback import FeedbackRepository
from app.models.feedback import Feedback
from app.db.base import Base


# Test database URL (in-memory SQLite)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def db_session():
    """Create test database session."""
    # Create async engine
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create session
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        yield session

    # Drop tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest.fixture
def feedback_repo(db_session):
    """Create feedback repository."""
    return FeedbackRepository(db_session)


@pytest.mark.asyncio
async def test_create_feedback(feedback_repo, db_session):
    """Test creating feedback."""
    feedback = await feedback_repo.create(
        source="hubspot",
        external_id="12345",
        title="Test Feedback",
        content="This is a test feedback item",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )

    assert feedback.id is not None
    assert feedback.source == "hubspot"
    assert feedback.external_id == "12345"
    assert feedback.title == "Test Feedback"


@pytest.mark.asyncio
async def test_get_by_id(feedback_repo, db_session):
    """Test getting feedback by ID."""
    # Create feedback
    created = await feedback_repo.create(
        source="hubspot",
        external_id="12345",
        title="Test Feedback",
        content="Test content",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    await feedback_repo.commit()

    # Get by ID
    found = await feedback_repo.get_by_id(created.id)

    assert found is not None
    assert found.id == created.id
    assert found.title == "Test Feedback"


@pytest.mark.asyncio
async def test_get_by_source_and_external_id(feedback_repo, db_session):
    """Test getting feedback by source and external ID."""
    # Create feedback
    await feedback_repo.create(
        source="hubspot",
        external_id="12345",
        title="Test Feedback",
        content="Test content",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    await feedback_repo.commit()

    # Get by source and external ID
    found = await feedback_repo.get_by_source_and_external_id("hubspot", "12345")

    assert found is not None
    assert found.source == "hubspot"
    assert found.external_id == "12345"


@pytest.mark.asyncio
async def test_get_unclassified(feedback_repo, db_session):
    """Test getting unclassified feedback."""
    # Create unclassified feedback
    await feedback_repo.create(
        source="hubspot",
        external_id="12345",
        title="Unclassified Feedback",
        content="No classification yet",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    await feedback_repo.commit()

    # Get unclassified
    unclassified = await feedback_repo.get_unclassified(limit=10)

    assert len(unclassified) == 1
    assert unclassified[0].title == "Unclassified Feedback"
