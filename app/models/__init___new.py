"""Database models for JisrVoC - aligned with schema.sql."""

# Source and ingestion
from .source_connector import SourceConnector, SourceType as ConnectorSourceType, ConnectorStatus
from .raw_ticket import RawTicket, SourceType as TicketSourceType, Language as RawLanguage

# Feedback items and enrichment
from .feedback_item import (
    FeedbackItem,
    FeedbackCategory,
    ProductArea,
    Sentiment,
    Urgency,
    Language,
    Segment as FeedbackSegment
)
from .enrichment import Enrichment
from .embedding import Embedding
from .vote import Vote, SourceType as VoteSourceType

# Customer (company-level)
from .customer_new import Customer, Segment as CustomerSegment

# Themes and clustering
from .theme import Theme, ThemeTrend
from .clustering import ClusteringRun, ThemeMembership

# Product bets
from .bet import ProductBet, BetStatus, BetEvidence, WritebackLog, Segment as BetSegment

# Legacy models (to be migrated)
from .feedback import Feedback as LegacyFeedback
from .customer import Customer as LegacyCustomer
from .classification import Classification
from .company import Company

__all__ = [
    # Source and ingestion
    "SourceConnector",
    "ConnectorSourceType",
    "ConnectorStatus",
    "RawTicket",
    "TicketSourceType",
    "RawLanguage",

    # Feedback items and enrichment
    "FeedbackItem",
    "FeedbackCategory",
    "ProductArea",
    "Sentiment",
    "Urgency",
    "Language",
    "FeedbackSegment",
    "Enrichment",
    "Embedding",
    "Vote",
    "VoteSourceType",

    # Customer
    "Customer",
    "CustomerSegment",

    # Themes and clustering
    "Theme",
    "ThemeTrend",
    "ClusteringRun",
    "ThemeMembership",

    # Product bets
    "ProductBet",
    "BetStatus",
    "BetEvidence",
    "WritebackLog",
    "BetSegment",

    # Legacy (to be removed after migration)
    "LegacyFeedback",
    "LegacyCustomer",
    "Classification",
    "Company",
]
