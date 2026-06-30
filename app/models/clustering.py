"""Clustering run tracking and theme membership models."""
from sqlalchemy import Column, String, Integer, DateTime, Float, UUID, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
import uuid

from app.db.base import Base


class ClusteringRun(Base):
    """Tracks weekly clustering job executions."""
    __tablename__ = "clustering_run"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    started_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    finished_at = Column(DateTime(timezone=True), nullable=True)
    item_count = Column(Integer, nullable=True)
    status = Column(String, nullable=True)  # 'running', 'completed', 'failed'

    # Relationships
    memberships = relationship("ThemeMembership", back_populates="run")

    def __repr__(self):
        return f"<ClusteringRun {self.id}: {self.status} ({self.item_count} items)>"


class ThemeMembership(Base):
    """Links feedback items to themes for a specific clustering run.

    Tracks which feedback belongs to which theme per run, maintaining
    historical clustering results even as themes evolve.
    """
    __tablename__ = "theme_membership"

    theme_id = Column(UUID(as_uuid=True), ForeignKey("theme.id", ondelete="CASCADE"), primary_key=True)
    feedback_id = Column(UUID(as_uuid=True), ForeignKey("feedback.id", ondelete="CASCADE"), primary_key=True)
    run_id = Column(UUID(as_uuid=True), ForeignKey("clustering_run.id"), primary_key=True)
    similarity = Column(Float, nullable=True)  # Cosine similarity to theme centroid

    # Relationships
    theme = relationship("Theme", back_populates="memberships")
    feedback = relationship("Feedback")
    run = relationship("ClusteringRun", back_populates="memberships")

    def __repr__(self):
        return f"<ThemeMembership theme={self.theme_id} feedback={self.feedback_id} run={self.run_id}>"
