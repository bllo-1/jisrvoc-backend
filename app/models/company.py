"""Company model - represents customer organizations."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import String, Integer, Text, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.customer import LegacyCustomer
    from app.models.feedback import Feedback


class Company(Base):
    """
    Company/Organization entity identified by email domain.

    Aggregates customers and feedback from the same organization.
    """
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Identity
    domain: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    company_name: Mapped[str | None] = mapped_column(String(255))

    # External IDs from connectors
    hubspot_company_id: Mapped[str | None] = mapped_column(String(100), index=True)
    zendesk_org_id: Mapped[str | None] = mapped_column(String(100), index=True)

    # Company metadata
    industry: Mapped[str | None] = mapped_column(String(100))
    arr: Mapped[int | None] = mapped_column(Integer)  # Annual Recurring Revenue
    decision_maker_count: Mapped[int | None] = mapped_column(Integer)
    tier: Mapped[str | None] = mapped_column(String(50))  # enterprise, mid-market, smb

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    customers: Mapped[list["LegacyCustomer"]] = relationship("LegacyCustomer", back_populates="company")
    feedback: Mapped[list["Feedback"]] = relationship("Feedback", back_populates="company")

    __table_args__ = (
        Index("ix_companies_hubspot_id", "hubspot_company_id"),
        Index("ix_companies_zendesk_id", "zendesk_org_id"),
    )

    def __repr__(self) -> str:
        return f"<Company(id={self.id}, domain='{self.domain}', name='{self.company_name}')>"
