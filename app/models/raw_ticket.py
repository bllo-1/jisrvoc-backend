"""Raw ticket model - immutable source records."""
from datetime import datetime
from typing import TYPE_CHECKING
import uuid

from sqlalchemy import Column, String, Text, DateTime, ForeignKey, UUID, JSON, Index, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.feedback_item import FeedbackItem
    from app.models.customer_new import Customer


class SourceType(str, enum.Enum):
    """Source type enum matching database schema."""
    HUBSPOT = "hubspot"
    ZENDESK = "zendesk"
    CANNY = "canny"
    JIRA = "jira"


class Language(str, enum.Enum):
    """Language enum matching database schema."""
    AR = "ar"
    EN = "en"
    MIXED = "mixed"


class RawTicket(Base):
    """
    Immutable original source record (parent of feedback items).

    Preserves raw source text verbatim for audit trail and compliance.
    Each raw ticket can decompose into one or more feedback_items.
    """
    __tablename__ = "raw_ticket"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Source metadata
    source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("source_connector.id"), nullable=False)
    source_type: Mapped[SourceType] = mapped_column(SQLEnum(SourceType, name="source_type", native_enum=True, values_callable=lambda x: [e.value for e in x]), nullable=False)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)

    # Original content
    subject: Mapped[str | None] = mapped_column(String(500))
    body: Mapped[str | None] = mapped_column(Text)
    raw_payload: Mapped[dict | None] = mapped_column(JSON)
    language_raw: Mapped[Language | None] = mapped_column(SQLEnum(Language, name="lang", native_enum=True, values_callable=lambda x: [e.value for e in x]))

    # Customer relationship
    customer_id: Mapped[str | None] = mapped_column(String(255), ForeignKey("customer.id"))

    # Timestamps
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    # Relationships
    feedback_items: Mapped[list["FeedbackItem"]] = relationship("FeedbackItem", back_populates="parent_ticket")
    customer: Mapped["Customer | None"] = relationship("Customer")

    __table_args__ = (
        Index("idx_raw_ticket_customer", "customer_id"),
        # Unique constraint for idempotent ingestion
        Index("uq_raw_ticket_source", "source_type", "external_id", unique=True),
    )

    def __repr__(self) -> str:
        return f"<RawTicket(id={self.id}, source={self.source_type}, external_id='{self.external_id}')>"
