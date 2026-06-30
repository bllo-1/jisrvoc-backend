"""Vote model - Canny/Jira upvotes for theme weighting."""
from datetime import datetime
from typing import TYPE_CHECKING
import uuid

from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, UUID, Index, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.feedback_item import FeedbackItem


class SourceType(str, enum.Enum):
    """Source type enum for votes."""
    HUBSPOT = "hubspot"
    ZENDESK = "zendesk"
    CANNY = "canny"
    JIRA = "jira"


class Vote(Base):
    """
    Vote counts from Canny/Jira to weight themes by customer demand.

    Tracks upvotes, likes, or similar engagement metrics from source systems.
    """
    __tablename__ = "vote"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Feedback relationship
    feedback_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("feedback_item.id", ondelete="CASCADE"),
        nullable=False
    )

    # Vote metadata
    source: Mapped[SourceType] = mapped_column(SQLEnum(SourceType, name="source_type"), nullable=False)
    vote_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Timestamp
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    # Relationships
    feedback_item: Mapped["FeedbackItem"] = relationship("FeedbackItem", back_populates="votes")

    __table_args__ = (
        Index("idx_vote_item", "feedback_item_id"),
    )

    def __repr__(self) -> str:
        return f"<Vote(id={self.id}, feedback_item_id={self.feedback_item_id}, count={self.vote_count})>"
