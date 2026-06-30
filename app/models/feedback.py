"""Feedback model - core entity for customer feedback items."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import String, Integer, Text, DateTime, ForeignKey, Index, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.customer import LegacyCustomer
    from app.models.company import Company
    from app.models.classification import Classification


class Feedback(Base):
    """
    Feedback item from any source (HubSpot ticket, Zendesk ticket, etc).

    Core entity that gets classified and enriched with AI.
    """
    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Source metadata
    source: Mapped[str] = mapped_column(String(50), nullable=False)  # hubspot, zendesk, canny
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    source_channel: Mapped[str | None] = mapped_column(String(50))  # email, chat, web, phone

    # Content
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Customer relationship
    customer_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("customers.id", ondelete="SET NULL")
    )
    customer_email: Mapped[str | None] = mapped_column(String(255), index=True)

    # Company relationship (denormalized for performance)
    company_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("companies.id", ondelete="SET NULL")
    )

    # Status and priority
    status: Mapped[str | None] = mapped_column(String(50))  # open, pending, solved, closed
    priority: Mapped[str | None] = mapped_column(String(50))  # low, normal, high, urgent

    # Satisfaction (if available from source)
    satisfaction_score: Mapped[str | None] = mapped_column(String(20))  # good, bad, null

    # AI-generated embedding for semantic search
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536))  # OpenAI text-embedding-3-small

    # Original metadata from source (JSON)
    source_metadata: Mapped[dict | None] = mapped_column("metadata", JSON)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    customer: Mapped["LegacyCustomer | None"] = relationship("LegacyCustomer", back_populates="feedback")
    company: Mapped["Company | None"] = relationship("Company", back_populates="feedback")
    classification: Mapped["Classification | None"] = relationship(
        "Classification", back_populates="feedback", uselist=False
    )

    __table_args__ = (
        Index("ix_feedback_source_external_id", "source", "external_id", unique=True),
        Index("ix_feedback_customer_id", "customer_id"),
        Index("ix_feedback_company_id", "company_id"),
        Index("ix_feedback_created_at", "created_at"),
        Index("ix_feedback_source", "source"),
    )

    def __repr__(self) -> str:
        return f"<Feedback(id={self.id}, source='{self.source}', title='{self.title[:50]}...')>"
