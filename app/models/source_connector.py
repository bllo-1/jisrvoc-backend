"""Source connector model - configuration for data source integrations."""
from datetime import datetime
from typing import TYPE_CHECKING
import uuid
import enum

from sqlalchemy import Column, String, DateTime, UUID, JSON, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.raw_ticket import RawTicket


class SourceType(str, enum.Enum):
    """Source system type."""
    HUBSPOT = "hubspot"
    ZENDESK = "zendesk"
    CANNY = "canny"
    JIRA = "jira"


class ConnectorStatus(str, enum.Enum):
    """Connector health status."""
    CONNECTED = "connected"
    DEGRADED = "degraded"
    DISCONNECTED = "disconnected"


class SourceConnector(Base):
    """
    Configuration and status for source system integrations.

    Stores credentials reference (not actual credentials), field mappings,
    and sync health for Admin view.
    """
    __tablename__ = "source_connector"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Connector metadata
    type: Mapped[SourceType] = mapped_column(SQLEnum(SourceType, name="source_type", native_enum=True, values_callable=lambda x: [e.value for e in x]), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[ConnectorStatus] = mapped_column(
        SQLEnum(ConnectorStatus, name="connector_status", native_enum=True, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=ConnectorStatus.DISCONNECTED
    )

    # Security - store only secrets-manager reference, NEVER actual credentials
    credentials_ref: Mapped[str | None] = mapped_column(String(500))

    # Field mapping configuration (JSON)
    field_mapping: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    # Sync tracking
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    # Relationships
    raw_tickets: Mapped[list["RawTicket"]] = relationship("RawTicket")

    def __repr__(self) -> str:
        return f"<SourceConnector(id={self.id}, type={self.type}, status={self.status})>"
