"""Database models for JisrVoC."""

# Phase 3 models (new schema)
from .raw_ticket import RawTicket, SourceType
from .feedback_item import FeedbackItem, FeedbackCategory, ProductArea, Sentiment, Urgency, Language, Segment
from .enrichment import Enrichment
from .embedding import Embedding
from .vote import Vote
from .customer import Customer
from .source_connector import SourceConnector, ConnectorStatus
from .theme import Theme, ThemeTrend
from .bet import ProductBet, BetStatus, BetEvidence, WritebackLog
from .clustering import ClusteringRun, ThemeMembership

# Legacy models (Phase 1/2 - deprecated)
from .feedback import Feedback
from .classification import Classification
from .company import Company

__all__ = [
    # Phase 3 models
    "RawTicket",
    "SourceType",
    "FeedbackItem",
    "FeedbackCategory",
    "ProductArea",
    "Sentiment",
    "Urgency",
    "Language",
    "Segment",
    "Enrichment",
    "Embedding",
    "Vote",
    "Customer",
    "SourceConnector",
    "ConnectorStatus",
    "Theme",
    "ThemeTrend",
    "ProductBet",
    "BetStatus",
    "BetEvidence",
    "WritebackLog",
    "ClusteringRun",
    "ThemeMembership",
    # Legacy models
    "Feedback",
    "Classification",
    "Company",
]
