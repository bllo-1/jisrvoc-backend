"""Embedding model - multilingual vector embeddings for clustering."""
from datetime import datetime
from typing import TYPE_CHECKING
import uuid

from sqlalchemy import Column, String, DateTime, ForeignKey, UUID, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.feedback_item import FeedbackItem


class Embedding(Base):
    """
    Multilingual vector embeddings for cross-language clustering.

    Uses multilingual-e5-large (1024 dim) or similar model to enable
    Arabic-English feedback clustering without language barriers.
    """
    __tablename__ = "embedding"

    # Primary key is the feedback_item_id (1:1 relationship)
    feedback_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("feedback_item.id", ondelete="CASCADE"),
        primary_key=True
    )

    # Vector embedding (1024 dimensions for multilingual-e5-large)
    vector: Mapped[list[float]] = mapped_column(Vector(1024), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    # Relationships
    feedback_item: Mapped["FeedbackItem"] = relationship("FeedbackItem", back_populates="embedding")

    __table_args__ = (
        # HNSW index for fast similarity search
        Index("idx_embedding_hnsw", "vector", postgresql_using="hnsw",
              postgresql_with={"m": 16, "ef_construction": 64},
              postgresql_ops={"vector": "vector_cosine_ops"}),
    )

    def __repr__(self) -> str:
        return f"<Embedding(feedback_item_id={self.feedback_item_id}, model={self.model})>"
