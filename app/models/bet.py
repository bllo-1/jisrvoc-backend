"""Product bet model for AI-generated product opportunities."""
from sqlalchemy import Column, String, Integer, Text, DateTime, Enum as SQLEnum, UUID, ARRAY
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy import ForeignKey
import enum
from datetime import datetime
import uuid

from app.db.base import Base


class BetStatus(str, enum.Enum):
    """Product bet status matching database type."""
    DRAFT = "draft"
    IN_BACKLOG = "in_backlog"
    IN_DISCOVERY = "in_discovery"
    IN_BUILD = "in_build"
    SHIPPED = "shipped"
    DECLINED = "declined"


class Segment(str, enum.Enum):
    """Customer segment enum."""
    SMB = "smb"
    MID_MARKET = "mid_market"
    ENTERPRISE = "enterprise"
    GOVERNMENT = "government"


class ProductBet(Base):
    """Product bet generated from high-impact themes.

    Bets are AI-drafted product opportunities with supporting evidence.
    PMs can accept, modify status, or decline with reasoning.
    """
    __tablename__ = "product_bet"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    theme_id = Column(UUID(as_uuid=True), ForeignKey("theme.id"), nullable=True)

    # Bet content (AI-generated)
    title = Column(String, nullable=False)
    problem_statement = Column(Text, nullable=True)
    affected_segments = Column(ARRAY(SQLEnum(Segment, name="segment")), nullable=False, default=[])
    est_customer_count = Column(Integer, nullable=True)
    why_now = Column(Text, nullable=True)

    # Status tracking
    status = Column(SQLEnum(BetStatus, name="bet_status"), nullable=False, default=BetStatus.DRAFT)
    declined_reason = Column(Text, nullable=True)
    owner_pm = Column(String, nullable=True)  # app_user.id

    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, default=func.now(), onupdate=func.now())

    # Relationships
    theme = relationship("Theme", back_populates="bets")
    evidence = relationship("BetEvidence", back_populates="bet", cascade="all, delete-orphan")
    writeback_logs = relationship("WritebackLog", back_populates="bet")

    def __repr__(self):
        return f"<ProductBet {self.id}: {self.title} ({self.status})>"


class BetEvidence(Base):
    """Links feedback items to product bets as supporting evidence."""
    __tablename__ = "bet_evidence"

    bet_id = Column(UUID(as_uuid=True), ForeignKey("product_bet.id", ondelete="CASCADE"), primary_key=True)
    feedback_id = Column(UUID(as_uuid=True), ForeignKey("feedback.id", ondelete="CASCADE"), primary_key=True)

    # Relationships
    bet = relationship("ProductBet", back_populates="evidence")
    feedback = relationship("Feedback")

    def __repr__(self):
        return f"<BetEvidence bet={self.bet_id} feedback={self.feedback_id}>"


class WritebackLog(Base):
    """Immutable log of HubSpot write-backs for audit trail."""
    __tablename__ = "writeback_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    bet_id = Column(UUID(as_uuid=True), ForeignKey("product_bet.id"), nullable=False)
    hubspot_ticket_id = Column(String, nullable=False)
    action = Column(String, nullable=False)  # 'note' | 'property_update'
    status_value = Column(SQLEnum(BetStatus, name="bet_status"), nullable=False)
    pm_id = Column(String, nullable=False)
    performed_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    result = Column(String, nullable=False)  # 'success' | 'failed:<reason>'

    # Relationships
    bet = relationship("ProductBet", back_populates="writeback_logs")

    def __repr__(self):
        return f"<WritebackLog {self.id}: {self.action} -> {self.result}>"
