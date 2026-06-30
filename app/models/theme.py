"""Theme model for clustering results with stable identity."""
from sqlalchemy import Column, String, Integer, Boolean, DateTime, Enum as SQLEnum, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector
import enum
from datetime import datetime
import uuid

from app.db.base import Base


class ThemeTrend(str, enum.Enum):
    """Theme trend enum matching database type."""
    NEW = "new"
    RISING = "rising"
    STABLE = "stable"
    DECLINING = "declining"


class Theme(Base):
    """Theme represents a cluster of similar feedback with stable identity.

    Themes persist across weekly clustering runs to maintain continuity.
    New clusters are matched to existing themes by centroid similarity.
    """
    __tablename__ = "theme"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name_en = Column(String, nullable=False)
    description_en = Column(String, nullable=True)
    trend = Column(SQLEnum(ThemeTrend, name="theme_trend"), nullable=False, default=ThemeTrend.NEW)

    # Centroid for stable identity matching (1536 for text-embedding-3-small)
    centroid = Column(Vector(1536), nullable=True)

    # Metadata
    item_count = Column(Integer, nullable=False, default=0)
    customer_count = Column(Integer, nullable=False, default=0)
    vote_weight = Column(Integer, nullable=False, default=0)

    # Tracking
    first_seen_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    last_run_id = Column(UUID(as_uuid=True), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)

    # Relationships
    bets = relationship("ProductBet", back_populates="theme")
    memberships = relationship("ThemeMembership", back_populates="theme", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Theme {self.id}: {self.name_en} ({self.trend})>"
