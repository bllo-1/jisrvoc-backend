"""In-memory mock data so the frontend can integrate against real shapes before
the DB-backed implementation lands. Toggle with USE_MOCK_DATA. Replace each
function with a repository call in Phase 1+."""
from datetime import date, datetime, timedelta
from . import schemas as s

_now = datetime(2026, 6, 28, 9, 0, 0)


def overview_metrics() -> s.OverviewMetrics:
    return s.OverviewMetrics(
        total_items=1284, active_themes=37, high_urgency_open=9, bets_in_flight=12,
        urgency_distribution=s.UrgencyDistribution(low=712, medium=421, high=151),
    )


def volume_trend(weeks: int = 12) -> list[s.TrendPoint]:
    base = date(2026, 4, 6)
    counts = [78, 84, 91, 80, 96, 102, 110, 99, 118, 121, 130, 142]
    return [s.TrendPoint(week_start=base + timedelta(weeks=i), count=c)
            for i, c in enumerate(counts[:weeks])]


def by_source() -> list[s.CountBucket]:
    return [s.CountBucket(key="hubspot", count=512),
            s.CountBucket(key="zendesk", count=498),
            s.CountBucket(key="canny", count=274)]


def by_product_area() -> list[s.CountBucket]:
    return [s.CountBucket(key=k, count=v) for k, v in [
        ("payroll", 318), ("core_hr", 241), ("jisrpay", 198), ("mobile", 156),
        ("onboarding", 122), ("contracts", 98), ("offboarding", 61),
        ("integrations", 55), ("other", 35)]]


_THEMES = [
    s.ThemeSummary(id="t-001", name_en="Payroll run fails on GOSI recalculation",
                   description_en="Customers report payroll runs erroring out when GOSI contributions are recalculated mid-cycle.",
                   trend=s.Trend.rising, item_count=42, customer_count=28, vote_weight=210,
                   top_segments=[s.Segment.mid_market, s.Segment.enterprise]),
    s.ThemeSummary(id="t-002", name_en="Mobile app login loop after update",
                   description_en="Repeated login failures on the mobile app following the latest release.",
                   trend=s.Trend.new, item_count=31, customer_count=24, vote_weight=88,
                   top_segments=[s.Segment.smb, s.Segment.mid_market]),
    s.ThemeSummary(id="t-003", name_en="Leave balance miscalculation for partial months",
                   description_en="Leave balances computed incorrectly for employees joining mid-month.",
                   trend=s.Trend.stable, item_count=27, customer_count=19, vote_weight=64,
                   top_segments=[s.Segment.enterprise]),
    s.ThemeSummary(id="t-004", name_en="Bulk contract template export requested",
                   description_en="Frequent requests to export contract templates in bulk.",
                   trend=s.Trend.rising, item_count=22, customer_count=15, vote_weight=156,
                   top_segments=[s.Segment.mid_market]),
    s.ThemeSummary(id="t-005", name_en="JisrPay card activation delays",
                   description_en="Delays activating JisrPay cards for new employees.",
                   trend=s.Trend.declining, item_count=18, customer_count=12, vote_weight=43,
                   top_segments=[s.Segment.smb]),
]


def top_themes(limit: int = 5) -> list[s.ThemeSummary]:
    return _THEMES[:limit]


def themes(trend=None) -> list[s.ThemeSummary]:
    return [t for t in _THEMES if trend is None or t.trend == trend]


def theme_detail(theme_id: str) -> s.ThemeDetail | None:
    base = next((t for t in _THEMES if t.id == theme_id), None)
    if not base:
        return None
    return s.ThemeDetail(
        **base.model_dump(),
        segment_breakdown=[s.CountBucket(key="mid_market", count=18),
                           s.CountBucket(key="enterprise", count=14),
                           s.CountBucket(key="smb", count=10)],
        verbatims=[
            s.Verbatim(text="The payroll run keeps failing whenever GOSI is recalculated for new joiners.",
                       language=s.Language.en, customer_name="Acme Trading", source=s.SourceType.zendesk),
            s.Verbatim(text="عملية احتساب الرواتب تتوقف عند إعادة حساب التأمينات الاجتماعية (GOSI).",
                       language=s.Language.ar, customer_name="شركة الأفق", source=s.SourceType.hubspot),
            s.Verbatim(text="This is blocking our month-end close. We are considering alternatives.",
                       language=s.Language.en, customer_name="Naseej Co", source=s.SourceType.hubspot),
        ],
        linked_bet=_BETS[0],
    )


_BETS = [
    s.BetSummary(id="b-001", title="Fix GOSI mid-cycle recalculation in payroll engine",
                 status=s.BetStatus.in_discovery, problem_snippet="Payroll runs fail on GOSI recalculation...",
                 affected_segments=[s.Segment.mid_market, s.Segment.enterprise], est_customer_count=28,
                 why_now="Rising trend; 210 votes; 9 high-urgency tickets", evidence_count=42, theme_id="t-001"),
    s.BetSummary(id="b-002", title="Stabilize mobile login flow", status=s.BetStatus.in_backlog,
                 problem_snippet="Login loop after the latest mobile release...",
                 affected_segments=[s.Segment.smb], est_customer_count=24,
                 why_now="New theme spiking this week", evidence_count=31, theme_id="t-002"),
    s.BetSummary(id="b-003", title="Bulk contract template export", status=s.BetStatus.draft,
                 problem_snippet="Customers want to export contract templates in bulk...",
                 affected_segments=[s.Segment.mid_market], est_customer_count=15,
                 why_now="156 votes on Canny", evidence_count=22, theme_id="t-004"),
    s.BetSummary(id="b-004", title="Partial-month leave accrual fix", status=s.BetStatus.in_build,
                 problem_snippet="Leave balances wrong for mid-month joiners...",
                 affected_segments=[s.Segment.enterprise], est_customer_count=19,
                 why_now="Stable but high-value enterprise impact", evidence_count=27, theme_id="t-003"),
]


def bets(status=None) -> list[s.BetSummary]:
    return [b for b in _BETS if status is None or b.status == status]


def bet_detail(bet_id: str) -> s.BetDetail | None:
    base = next((b for b in _BETS if b.id == bet_id), None)
    if not base:
        return None
    return s.BetDetail(**base.model_dump(),
                       problem_statement="Detailed structured problem statement goes here.",
                       owner_pm="mohamed", evidence=_feedback_items()[:3])


_CUSTOMERS = [
    s.Customer(id="hs-1001", name="Acme Trading", domain="acme.sa", segment=s.Segment.mid_market,
               lifecycle_stage="customer", industry="Retail", is_prospect=False),
    s.Customer(id="hs-1002", name="Naseej Co", domain="naseej.com", segment=s.Segment.enterprise,
               lifecycle_stage="customer", industry="Manufacturing", is_prospect=False),
]


def customers(q: str | None = None) -> list[s.Customer]:
    if not q:
        return _CUSTOMERS
    return [c for c in _CUSTOMERS if q.lower() in c.name.lower()]


def _feedback_items() -> list[s.FeedbackItem]:
    return [
        s.FeedbackItem(id="f-0001", summary_en="Payroll run fails when GOSI is recalculated for new joiners",
                       source=s.SourceType.zendesk, category=s.Category.bug_report, area=s.ProductArea.payroll,
                       sentiment=s.Sentiment.negative, urgency=s.Urgency.high, language=s.Language.en,
                       segment=s.Segment.mid_market, customer_id="hs-1001", customer_name="Acme Trading",
                       is_split=False, parent_ticket_id="rt-9001", occurred_at=_now),
        s.FeedbackItem(id="f-0002", summary_en="Mobile app stuck in a login loop after update",
                       source=s.SourceType.hubspot, category=s.Category.bug_report, area=s.ProductArea.mobile,
                       sentiment=s.Sentiment.negative, urgency=s.Urgency.medium, language=s.Language.ar,
                       segment=s.Segment.smb, customer_id="hs-1002", customer_name="Naseej Co",
                       is_split=True, parent_ticket_id="rt-9002", occurred_at=_now),
        s.FeedbackItem(id="f-0003", summary_en="Request: export contract templates in bulk",
                       source=s.SourceType.canny, category=s.Category.feature_request, area=s.ProductArea.contracts,
                       sentiment=s.Sentiment.neutral, urgency=s.Urgency.low, language=s.Language.en,
                       segment=s.Segment.mid_market, customer_id="hs-1001", customer_name="Acme Trading",
                       is_split=False, parent_ticket_id="rt-9003", occurred_at=_now),
    ]


def feedback_page(limit: int = 50, **filters) -> s.FeedbackPage:
    items = _feedback_items()
    return s.FeedbackPage(items=items[:limit], next_cursor=None, total=len(items))


def feedback_detail(item_id: str) -> s.FeedbackDetail | None:
    item = next((i for i in _feedback_items() if i.id == item_id), None)
    if not item:
        return None
    return s.FeedbackDetail(**item.model_dump(),
                            raw_text="عملية احتساب الرواتب تتوقف عند إعادة حساب التأمينات." if item.language == s.Language.ar
                            else "The payroll run keeps failing when GOSI is recalculated.",
                            raw_language=item.language, enrichment_model="gemini-1.5",
                            enrichment_confidence=0.92, pm_corrected=False)


def connectors() -> list[s.Connector]:
    return [
        s.Connector(id="c-1", type=s.SourceType.hubspot, display_name="HubSpot", status="connected", last_sync_at=_now),
        s.Connector(id="c-2", type=s.SourceType.zendesk, display_name="Zendesk", status="connected", last_sync_at=_now),
        s.Connector(id="c-3", type=s.SourceType.canny, display_name="Canny", status="degraded", last_sync_at=_now),
    ]


def routing_rules() -> list[s.RoutingRule]:
    return [
        s.RoutingRule(area=s.ProductArea.payroll, pm_user_id="mohamed", pm_name="Mohamed"),
        s.RoutingRule(area=s.ProductArea.mobile, pm_user_id="kshitij", pm_name="Kshitij"),
        s.RoutingRule(area=s.ProductArea.core_hr, pm_user_id="igor", pm_name="Igor"),
        s.RoutingRule(area=s.ProductArea.jisrpay, pm_user_id="ashutosh", pm_name="Ashutosh"),
    ]
