"""Feedback item model - decomposed, enriched unit."""
from datetime import datetime
from typing import TYPE_CHECKING
import uuid

from sqlalchemy import Column, String, Text, DateTime, ForeignKey, UUID, Boolean, Index, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
import sqlalchemy as sa
import enum

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.raw_ticket import RawTicket
    from app.models.customer import Customer
    from app.models.enrichment import Enrichment
    from app.models.embedding import Embedding
    from app.models.vote import Vote


class FeedbackCategory(str, enum.Enum):
    """Feedback category enum matching database schema."""
    PAIN_POINT = "pain_point"
    FEATURE_REQUEST = "feature_request"
    BUG_REPORT = "bug_report"
    HOW_TO_QUESTION = "how_to_question"
    PRAISE = "praise"


class ProductArea(str, enum.Enum):
    """Product area enum matching database schema."""
    CORE_HR = "core_hr"
    PAYROLL = "payroll"
    JISRPAY = "jisrpay"
    ONBOARDING = "onboarding"
    OFFBOARDING = "offboarding"
    CONTRACTS = "contracts"
    MOBILE = "mobile"
    INTEGRATIONS = "integrations"
    OTHER = "other"


class Sentiment(str, enum.Enum):
    """Sentiment enum matching database schema."""
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    MIXED = "mixed"


class Urgency(str, enum.Enum):
    """Urgency enum matching database schema."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Language(str, enum.Enum):
    """Language enum matching database schema."""
    AR = "ar"
    EN = "en"
    MIXED = "mixed"


class Segment(str, enum.Enum):
    """Customer segment enum matching database schema."""
    SMB = "smb"
    MID_MARKET = "mid_market"
    ENTERPRISE = "enterprise"
    GOVERNMENT = "government"


class FeedbackItem(Base):
    """
    Decomposed, enriched feedback unit.

    Core analytical entity. Can be 1:1 with raw_ticket or decomposed from
    multi-point feedback. All AI enrichment attaches here.
    """
    __tablename__ = "feedback_item"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Parent relationship
    parent_ticket_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("raw_ticket.id"), nullable=False)
    is_split: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # AI-enriched fields
    summary_en: Mapped[str | None] = mapped_column(Text)  # AI summary, always English
    category: Mapped[FeedbackCategory | None] = mapped_column(SQLEnum(FeedbackCategory, name="feedback_category", native_enum=True, values_callable=lambda x: [e.value for e in x]))
    area: Mapped[ProductArea | None] = mapped_column(SQLEnum(ProductArea, name="product_area", native_enum=True, values_callable=lambda x: [e.value for e in x]))
    sentiment: Mapped[Sentiment | None] = mapped_column(SQLEnum(Sentiment, name="sentiment", native_enum=True, values_callable=lambda x: [e.value for e in x]))
    urgency: Mapped[Urgency | None] = mapped_column(SQLEnum(Urgency, name="urgency", native_enum=True, values_callable=lambda x: [e.value for e in x]))
    language: Mapped[Language | None] = mapped_column(SQLEnum(Language, name="lang", native_enum=True, values_callable=lambda x: [e.value for e in x]))

    # Denormalized from customer at enrich time
    segment: Mapped[Segment | None] = mapped_column(SQLEnum(Segment, name="segment", native_enum=True, values_callable=lambda x: [e.value for e in x]))
    customer_id: Mapped[str | None] = mapped_column(String(255), ForeignKey("customer.id"))

    # Chargebee enrichment fields (Phase 5)
    customer_mrr: Mapped[float | None] = mapped_column(sa.Numeric(10, 2))
    customer_ltv: Mapped[float | None] = mapped_column(sa.Numeric(10, 2))
    churn_risk_score: Mapped[int | None] = mapped_column(sa.Integer)
    subscription_plan: Mapped[str | None] = mapped_column(String(100))
    enriched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Timestamps
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    # Relationships
    parent_ticket: Mapped["RawTicket"] = relationship("RawTicket", back_populates="feedback_items")
    customer: Mapped["Customer | None"] = relationship("Customer")
    enrichment: Mapped["Enrichment | None"] = relationship("Enrichment", back_populates="feedback_item", uselist=False)
    embedding: Mapped["Embedding | None"] = relationship("Embedding", back_populates="feedback_item", uselist=False)
    votes: Mapped[list["Vote"]] = relationship("Vote", back_populates="feedback_item")

    __table_args__ = (
        Index("idx_fi_parent", "parent_ticket_id"),
        Index("idx_fi_customer", "customer_id"),
        Index("idx_fi_area", "area"),
        Index("idx_fi_category", "category"),
        Index("idx_fi_urgency", "urgency"),
        Index("idx_fi_occurred", "occurred_at", postgresql_ops={"occurred_at": "DESC"}),
        # Full-text search index (PostgreSQL-specific)
        Index("idx_fi_summary_fts", "summary_en", postgresql_using="gin",
              postgresql_ops={"summary_en": "gin_trgm_ops"}),
    )

    def __repr__(self) -> str:
        return f"<FeedbackItem(id={self.id}, category={self.category}, area={self.area})>"
