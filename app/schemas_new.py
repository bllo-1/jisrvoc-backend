"""
Pydantic models matching the frontend TypeScript contract exactly.
All models use camelCase JSON serialization via Field aliases.
Enums use PascalCase values to match frontend ("HubSpot", "Pain Point", etc.).
"""
from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict


def to_camel(string: str) -> str:
    """Convert snake_case to camelCase."""
    components = string.split('_')
    return components[0] + ''.join(x.title() for x in components[1:])


class CamelModel(BaseModel):
    """Base model with camelCase alias generation."""
    model_config = ConfigDict(
        populate_by_name=True,
        alias_generator=to_camel,
    )


# ============================================================================
# ENUMS (PascalCase values matching frontend)
# ============================================================================

class Source(str, Enum):
    hubspot = "HubSpot"
    zendesk = "Zendesk"
    canny = "Canny"
    jira = "Jira"


class Category(str, Enum):
    pain_point = "Pain Point"
    feature_request = "Feature Request"
    bug_report = "Bug Report"
    how_to_question = "How-To Question"
    praise = "Praise"


class ProductArea(str, Enum):
    core_hr = "Core HR"
    payroll = "Payroll"
    jisrpay = "JisrPay"
    onboarding = "Onboarding"
    offboarding = "Offboarding"
    contracts = "Contracts"
    mobile = "Mobile"
    integrations = "Integrations"
    other = "Other"


class Sentiment(str, Enum):
    positive = "Positive"
    neutral = "Neutral"
    negative = "Negative"
    mixed = "Mixed"


class Urgency(str, Enum):
    low = "Low"
    medium = "Medium"
    high = "High"


class Language(str, Enum):
    ar = "AR"
    en = "EN"
    mixed = "Mixed"


class Segment(str, Enum):
    smb = "SMB"
    mid_market = "Mid-Market"
    enterprise = "Enterprise"
    government = "Government"


class Trend(str, Enum):
    new = "New"
    rising = "Rising"
    stable = "Stable"
    declining = "Declining"


class BetStatus(str, Enum):
    draft = "Draft"
    in_backlog = "In Backlog"
    in_discovery = "In Discovery"
    in_build = "In Build"
    shipped = "Shipped"
    declined = "Declined"


class Health(str, Enum):
    healthy = "Healthy"
    at_risk = "At Risk"
    critical = "Critical"


# ============================================================================
# CORE DOMAIN MODELS
# ============================================================================

class FeedbackItem(CamelModel):
    """Matches frontend FeedbackItem interface exactly."""
    id: str
    summary: str
    raw_text: str
    source: Source
    source_ref: str
    category: Category
    product_area: ProductArea
    sentiment: Sentiment
    urgency: Urgency
    language: Language
    customer: str
    customer_id: str
    segment: Segment
    date: str  # ISO date string
    theme_id: Optional[str] = None
    split_from: Optional[str] = None
    tags: List[str] = Field(default_factory=list)


class Theme(CamelModel):
    """Matches frontend Theme interface."""
    id: str
    name: str
    description: str
    item_count: int
    customer_count: int
    vote_weight: int
    trend: Trend
    segments: List[Segment]
    product_area: ProductArea
    bet_id: Optional[str] = None


class ProductBet(CamelModel):
    """Matches frontend ProductBet interface."""
    id: str
    title: str
    problem_statement: str
    problem_detail: str
    status: BetStatus
    segments: List[Segment]
    customer_count: int
    urgency: Urgency
    trend: Trend
    vote_weight: int
    evidence_ids: List[str]
    theme_id: Optional[str] = None
    owner: str


class Customer(CamelModel):
    """Matches frontend Customer interface."""
    id: str
    name: str
    segment: Segment
    industry: str
    employees: int
    arr: str
    health: Health
    renewal_date: str  # ISO date string


class EnrichmentMeta(CamelModel):
    """AI enrichment metadata."""
    model: str
    model_version: str
    confidence: float
    pm_corrected: bool = False
    corrected_at: Optional[str] = None
    corrected_by: Optional[str] = None


class WritebackEntry(CamelModel):
    """Write-back log entry."""
    id: str
    bet_id: str
    feedback_id: str
    source_ref: str
    source: Source
    status: BetStatus
    performed_at: str  # ISO timestamp
    performed_by: str
    result: str  # "Success" | "Failed"


class VoteTrendPoint(CamelModel):
    """Weekly vote series point."""
    week: str  # ISO date
    votes: int


class SourceConnection(CamelModel):
    """Source connector status."""
    source: Source
    status: str  # "Connected" | "Degraded" | "Disconnected"
    last_sync: Optional[str] = None  # ISO timestamp
    items_synced: int = 0


class SyncRun(CamelModel):
    """Sync run record."""
    id: str
    source: Source
    started_at: str
    finished_at: Optional[str] = None
    items_ingested: int = 0
    status: str  # "Running" | "Success" | "Failed"
    error: Optional[str] = None


class SuggestedMatch(CamelModel):
    """Suggested customer match."""
    customer_id: str
    customer_name: str
    confidence: float


class UnmatchedItem(CamelModel):
    """Unmatched customer queue item."""
    id: str
    source: Source
    source_ref: str
    raw_customer_name: str
    raw_email: str
    raw_domain: str
    summary: str
    created_at: str  # ISO date string
    suggested_matches: List[SuggestedMatch] = Field(default_factory=list)


class PmRoutingRule(CamelModel):
    """PM routing by product area."""
    product_area: ProductArea
    pm_user_id: str
    pm_name: str


class EvalMetric(CamelModel):
    """Eval scorecard metric."""
    tag: str  # e.g., "category", "sentiment"
    language: Language
    f1_score: float
    precision: float
    recall: float
    sample_size: int


class EvalScorecard(CamelModel):
    """Full eval scorecard."""
    last_run: str  # ISO timestamp
    metrics: List[EvalMetric]


class DigestPreview(CamelModel):
    """Weekly digest preview."""
    scheduled_for: str
    recipient_channel: str
    top_themes: List[dict]  # {themeId, name, delta}
    new_bets: List[dict]  # {betId, title}
    high_urgency_count: int


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class Paginated(CamelModel):
    """Generic paginated response."""
    items: List
    next_cursor: Optional[str] = None
    total: int


class FeedbackPage(CamelModel):
    """Paginated feedback response."""
    items: List[FeedbackItem]
    next_cursor: Optional[str] = None
    total: int


class UrgencyDistribution(CamelModel):
    """Urgency breakdown."""
    low: int = Field(alias="Low")  # Frontend uses capital letters
    medium: int = Field(alias="Medium")
    high: int = Field(alias="High")

    model_config = ConfigDict(populate_by_name=True)


class OverviewMetrics(CamelModel):
    """Overview dashboard metrics."""
    total_feedback: int
    active_themes: int
    high_urgency_open: int
    bets_in_flight: int
    weekly_volume: List[dict]  # {week, count}
    source_breakdown: List[dict]  # {source, count}
    product_area_breakdown: List[dict]  # {area, count}
    urgency_distribution: UrgencyDistribution


class FeedbackTagEdit(CamelModel):
    """Request to edit feedback tags."""
    category: Optional[Category] = None
    product_area: Optional[ProductArea] = None
    sentiment: Optional[Sentiment] = None
    urgency: Optional[Urgency] = None


class BetStatusChangeRequest(CamelModel):
    """Request to change bet status."""
    status: BetStatus
    declined_reason: Optional[str] = None


class BetStatusChangeResponse(CamelModel):
    """Response after bet status change."""
    bet_id: str
    new_status: BetStatus
    writebacks_triggered: int
    writebacks_succeeded: int
    writebacks_failed: int


class ThemeMergeRequest(CamelModel):
    """Request to merge themes."""
    source_id: str
    target_id: str


class ThemeMergeResponse(CamelModel):
    """Response after theme merge."""
    merged_into: str
    released_items: int
    source_id: str


class ThemeRenameRequest(CamelModel):
    """Request to rename theme."""
    name: Optional[str] = None
    description: Optional[str] = None


class UnmatchedResolveRequest(CamelModel):
    """Request to resolve unmatched item."""
    customer_id: str


class ResyncResponse(CamelModel):
    """Response after triggering resync."""
    source: Source
    enqueued: bool
    run_id: str


class EvalRunResponse(CamelModel):
    """Response after triggering eval."""
    enqueued: bool
    eta_minutes: int


class DigestSendResponse(CamelModel):
    """Response after sending test digest."""
    sent: bool
    channel: str
