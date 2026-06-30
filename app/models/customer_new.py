"""Customer model - projection of HubSpot company identity."""
from datetime import datetime
from typing import TYPE_CHECKING
import enum

from sqlalchemy import Column, String, Text, Integer, Boolean, DateTime, Enum as SQLEnum, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.feedback_item import FeedbackItem
    from app.models.raw_ticket import RawTicket


class Segment(str, enum.Enum):
    """Customer segment enum matching database schema."""
    SMB = "smb"
    MID_MARKET = "mid_market"
    ENTERPRISE = "enterprise"
    GOVERNMENT = "government"


class Customer(Base):
    """
    Customer entity (company-level, not contact-level).

    Projection of HubSpot company identity. Never authoritative - always
    refreshed from HubSpot. ID is the HubSpot company ID (TEXT).
    """
    __tablename__ = "customer"

    # HubSpot company id as primary key (TEXT)
    id: Mapped[str] = mapped_column(String(255), primary_key=True)

    # Company metadata
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    domain: Mapped[str | None] = mapped_column(String(255))
    segment: Mapped[Segment | None] = mapped_column(SQLEnum(Segment, name="segment", native_enum=True, values_callable=lambda x: [e.value for e in x]))
    lifecycle_stage: Mapped[str | None] = mapped_column(String(100))
    industry: Mapped[str | None] = mapped_column(String(255))
    account_size: Mapped[int | None] = mapped_column(Integer)

    # PRD open Q7: track prospects (pre-close customers)
    is_prospect: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Timestamp
    refreshed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    # Relationships
    feedback_items: Mapped[list["FeedbackItem"]] = relationship("FeedbackItem", back_populates="customer")
    raw_tickets: Mapped[list["RawTicket"]] = relationship("RawTicket", back_populates="customer")

    __table_args__ = (
        Index("idx_customer_domain", "domain"),
        Index("idx_customer_segment", "segment"),
    )

    def __repr__(self) -> str:
        return f"<Customer(id='{self.id}', name='{self.name}', segment={self.segment})>"
