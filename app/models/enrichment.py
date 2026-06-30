"""Enrichment model - AI output and human corrections audit trail."""
from datetime import datetime
from typing import TYPE_CHECKING
import uuid

from sqlalchemy import Column, String, Text, DateTime, ForeignKey, UUID, Boolean, JSON, Float, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.feedback_item import FeedbackItem


class Enrichment(Base):
    """
    Audit trail for AI enrichment with human correction tracking.

    Stores raw AI output, confidence scores, and tracks when PMs correct
    the AI tags for continuous improvement.
    """
    __tablename__ = "enrichment"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Feedback relationship
    feedback_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("feedback_item.id", ondelete="CASCADE"),
        nullable=False
    )

    # Model information
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    model_version: Mapped[str] = mapped_column(String(50), nullable=False)
    raw_output: Mapped[dict] = mapped_column(JSON, nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float)

    # Human correction tracking
    pm_corrected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    corrected_by: Mapped[str | None] = mapped_column(String(255))  # app_user.id

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    # Relationships
    feedback_item: Mapped["FeedbackItem"] = relationship("FeedbackItem", back_populates="enrichment")

    __table_args__ = (
        Index("idx_enrich_item", "feedback_item_id"),
    )

    def __repr__(self) -> str:
        return f"<Enrichment(id={self.id}, model={self.model}, corrected={self.pm_corrected})>"
