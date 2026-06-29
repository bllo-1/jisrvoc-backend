"""Pydantic models mirroring openapi.yaml. Keep these in sync with the contract."""
from __future__ import annotations
from datetime import datetime, date
from enum import Enum
from pydantic import BaseModel


class SourceType(str, Enum):
    hubspot = "hubspot"; zendesk = "zendesk"; canny = "canny"; jira = "jira"


class Category(str, Enum):
    pain_point = "pain_point"; feature_request = "feature_request"
    bug_report = "bug_report"; how_to_question = "how_to_question"; praise = "praise"


class ProductArea(str, Enum):
    core_hr = "core_hr"; payroll = "payroll"; jisrpay = "jisrpay"
    onboarding = "onboarding"; offboarding = "offboarding"; contracts = "contracts"
    mobile = "mobile"; integrations = "integrations"; other = "other"


class Sentiment(str, Enum):
    positive = "positive"; neutral = "neutral"; negative = "negative"; mixed = "mixed"


class Urgency(str, Enum):
    low = "low"; medium = "medium"; high = "high"


class Language(str, Enum):
    ar = "ar"; en = "en"; mixed = "mixed"


class Segment(str, Enum):
    smb = "smb"; mid_market = "mid_market"; enterprise = "enterprise"; government = "government"


class Trend(str, Enum):
    new = "new"; rising = "rising"; stable = "stable"; declining = "declining"


class BetStatus(str, Enum):
    draft = "draft"; in_backlog = "in_backlog"; in_discovery = "in_discovery"
    in_build = "in_build"; shipped = "shipped"; declined = "declined"


class UrgencyDistribution(BaseModel):
    low: int = 0; medium: int = 0; high: int = 0


class OverviewMetrics(BaseModel):
    total_items: int
    active_themes: int
    high_urgency_open: int
    bets_in_flight: int
    urgency_distribution: UrgencyDistribution


class TrendPoint(BaseModel):
    week_start: date
    count: int


class CountBucket(BaseModel):
    key: str
    count: int


class FeedbackItem(BaseModel):
    id: str
    summary_en: str
    source: SourceType
    category: Category | None = None
    area: ProductArea | None = None
    sentiment: Sentiment | None = None
    urgency: Urgency | None = None
    language: Language
    segment: Segment | None = None
    customer_id: str | None = None
    customer_name: str | None = None
    is_split: bool = False
    parent_ticket_id: str | None = None
    occurred_at: datetime | None = None


class FeedbackDetail(FeedbackItem):
    raw_text: str | None = None
    raw_language: Language | None = None
    enrichment_model: str | None = None
    enrichment_confidence: float | None = None
    pm_corrected: bool = False


class FeedbackPage(BaseModel):
    items: list[FeedbackItem]
    next_cursor: str | None = None
    total: int


class TagCorrection(BaseModel):
    category: Category | None = None
    area: ProductArea | None = None
    sentiment: Sentiment | None = None
    urgency: Urgency | None = None


class Verbatim(BaseModel):
    text: str
    language: Language
    customer_name: str | None = None
    source: SourceType | None = None


class ThemeSummary(BaseModel):
    id: str
    name_en: str
    description_en: str | None = None
    trend: Trend
    item_count: int
    customer_count: int = 0
    vote_weight: int = 0
    top_segments: list[Segment] = []


class ThemeDetail(ThemeSummary):
    segment_breakdown: list[CountBucket] = []
    verbatims: list[Verbatim] = []
    linked_bet: "BetSummary | None" = None


class BetSummary(BaseModel):
    id: str
    title: str
    status: BetStatus
    problem_snippet: str | None = None
    affected_segments: list[Segment] = []
    est_customer_count: int | None = None
    why_now: str | None = None
    evidence_count: int = 0
    theme_id: str | None = None


class BetDetail(BetSummary):
    problem_statement: str | None = None
    owner_pm: str | None = None
    declined_reason: str | None = None
    evidence: list[FeedbackItem] = []


class BetCreate(BaseModel):
    title: str
    theme_id: str | None = None
    problem_statement: str | None = None
    affected_segments: list[Segment] = []
    est_customer_count: int | None = None


class BetUpdate(BaseModel):
    title: str | None = None
    problem_statement: str | None = None
    status: BetStatus | None = None
    declined_reason: str | None = None


class Writeback(BaseModel):
    tickets_updated: int
    action: str
    status_value: BetStatus


class BetUpdateResult(BetDetail):
    writeback: Writeback | None = None


class Customer(BaseModel):
    id: str
    name: str
    domain: str | None = None
    segment: Segment | None = None
    lifecycle_stage: str | None = None
    industry: str | None = None
    is_prospect: bool = False


class Connector(BaseModel):
    id: str
    type: SourceType
    display_name: str
    status: str
    last_sync_at: datetime | None = None


class RoutingRule(BaseModel):
    area: ProductArea
    pm_user_id: str
    pm_name: str | None = None
