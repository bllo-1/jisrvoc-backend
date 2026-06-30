"""Customer model - represents individual users/contacts."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import String, Integer, ForeignKey, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.company import Company
    from app.models.feedback import Feedback


class Customer(Base):
    """
    Customer/Contact entity identified by email.

    Linked to Company via email domain matching.
    """
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Identity
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    name: Mapped[str | None] = mapped_column(String(255))

    # Company relationship (via email domain)
    company_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("companies.id", ondelete="SET NULL")
    )

    # External IDs from connectors
    hubspot_contact_id: Mapped[str | None] = mapped_column(String(100))
    zendesk_user_id: Mapped[str | None] = mapped_column(String(100))

    # Customer metadata
    role: Mapped[str | None] = mapped_column(String(50))  # end-user, admin, etc.
    tier: Mapped[str | None] = mapped_column(String(50))  # inherited from company if null

    # Timestamps
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    company: Mapped["Company | None"] = relationship("Company", back_populates="customers")
    feedback: Mapped[list["Feedback"]] = relationship("Feedback", back_populates="customer")

    __table_args__ = (
        Index("ix_customers_hubspot_id", "hubspot_contact_id"),
        Index("ix_customers_zendesk_id", "zendesk_user_id"),
        Index("ix_customers_company_id", "company_id"),
    )

    def __repr__(self) -> str:
        return f"<Customer(id={self.id}, email='{self.email}', name='{self.name}')>"
