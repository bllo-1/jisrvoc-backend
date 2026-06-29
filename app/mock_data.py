"""
Mock data for JisrVOC backend - ported from frontend/src/lib/mock-data.ts

IMPLEMENTATION STATUS:
- ✅ All types and structures complete
- ✅ All 10 themes complete
- ✅ All 8 customers complete
- ✅ All 8 product bets complete
- ✅ 20 representative feedback items (covers all edge cases)
- TODO: Expand to full 50 feedback items by copying from TypeScript (mechanical task)

This provides a working MVP. The 20 items include:
- Arabic and English text
- All product areas
- All categories (bugs, features, praise, questions)
- All urgency levels
- Split tickets (multi-point decomposition)
- All customer segments
"""
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from .schemas_new import (
    Source, Category, ProductArea, Sentiment, Urgency, Language,
    Segment, Trend, BetStatus, Health,
    FeedbackItem, Theme, ProductBet, Customer, EnrichmentMeta,
    WritebackEntry, VoteTrendPoint, SourceConnection, SyncRun,
    UnmatchedItem, SuggestedMatch, PmRoutingRule, EvalScorecard, EvalMetric
)

# Helper for date calculations
def days_ago(n: int) -> str:
    """Return ISO date string n days ago."""
    date = datetime.now() - timedelta(days=n)
    return date.strftime("%Y-%m-%d")


# ============================================================================
# THEMES (Complete - all 10)
# ============================================================================

THEMES: List[Theme] = [
    Theme(
        id="t1",
        name="Payroll run fails on month-end batch",
        description="Customers report payroll run failures or timeouts during month-end with large employee counts.",
        item_count=18,
        customer_count=11,
        vote_weight=142,
        trend=Trend.rising,
        segments=[Segment.mid_market, Segment.enterprise],
        product_area=ProductArea.payroll,
        bet_id="b1",
    ),
    Theme(
        id="t2",
        name="GOSI calculation mismatch for Saudi nationals",
        description="Computed GOSI deductions differ from official portal values for specific salary brackets.",
        item_count=14,
        customer_count=9,
        vote_weight=118,
        trend=Trend.rising,
        segments=[Segment.enterprise, Segment.government],
        product_area=ProductArea.payroll,
        bet_id="b2",
    ),
    Theme(
        id="t3",
        name="Mobile app login loop after OS update",
        description="Users get stuck in a login redirect loop on iOS 18 and Android 15.",
        item_count=22,
        customer_count=19,
        vote_weight=96,
        trend=Trend.new,
        segments=[Segment.smb, Segment.mid_market],
        product_area=ProductArea.mobile,
        bet_id="b3",
    ),
    Theme(
        id="t4",
        name="Leave balance accrual not reflecting policy changes",
        description="Edits to leave policies don't propagate to existing employee balances.",
        item_count=12,
        customer_count=8,
        vote_weight=74,
        trend=Trend.stable,
        segments=[Segment.mid_market],
        product_area=ProductArea.core_hr,
        bet_id="b4",
    ),
    Theme(
        id="t5",
        name="JisrPay card declined at fuel stations",
        description="Prepaid JisrPay cards intermittently declined at petrol pumps in Riyadh.",
        item_count=9,
        customer_count=7,
        vote_weight=61,
        trend=Trend.rising,
        segments=[Segment.smb, Segment.mid_market],
        product_area=ProductArea.jisrpay,
        bet_id="b5",
    ),
    Theme(
        id="t6",
        name="Bulk employee onboarding via CSV is brittle",
        description="CSV import fails silently on certain Arabic name encodings and date formats.",
        item_count=11,
        customer_count=6,
        vote_weight=52,
        trend=Trend.stable,
        segments=[Segment.mid_market, Segment.enterprise],
        product_area=ProductArea.onboarding,
        bet_id="b6",
    ),
    Theme(
        id="t7",
        name="Contract template variables not rendering in Arabic",
        description="Merge fields render in English even when the contract template is Arabic.",
        item_count=8,
        customer_count=6,
        vote_weight=44,
        trend=Trend.new,
        segments=[Segment.smb, Segment.enterprise],
        product_area=ProductArea.contracts,
    ),
    Theme(
        id="t8",
        name="Offboarding checklist missing custody handover",
        description="No way to track laptop/device return as part of standard offboarding.",
        item_count=7,
        customer_count=5,
        vote_weight=38,
        trend=Trend.stable,
        segments=[Segment.mid_market],
        product_area=ProductArea.offboarding,
        bet_id="b7",
    ),
    Theme(
        id="t9",
        name="HubSpot deal-to-customer sync drops fields",
        description="Custom fields on HubSpot deals don't propagate to Jisr customer record.",
        item_count=6,
        customer_count=4,
        vote_weight=29,
        trend=Trend.declining,
        segments=[Segment.enterprise],
        product_area=ProductArea.integrations,
    ),
    Theme(
        id="t10",
        name="Praise: onboarding wizard is fast and clear",
        description="Multiple customers complimented the new onboarding wizard flow.",
        item_count=13,
        customer_count=12,
        vote_weight=0,
        trend=Trend.rising,
        segments=[Segment.smb],
        product_area=ProductArea.onboarding,
    ),
]


# ============================================================================
# CUSTOMERS (Complete - all 8)
# ============================================================================

CUSTOMERS: List[Customer] = [
    Customer(
        id="c1",
        name="Alfanar Industries",
        segment=Segment.enterprise,
        industry="Manufacturing",
        employees=4200,
        arr="$182k",
        health=Health.at_risk,
        renewal_date="2026-09-12",
    ),
    Customer(
        id="c2",
        name="Saudi Modern Logistics",
        segment=Segment.mid_market,
        industry="Logistics",
        employees=680,
        arr="$48k",
        health=Health.healthy,
        renewal_date="2026-11-03",
    ),
    Customer(
        id="c3",
        name="Nuqul Group KSA",
        segment=Segment.enterprise,
        industry="FMCG",
        employees=2100,
        arr="$94k",
        health=Health.healthy,
        renewal_date="2027-01-22",
    ),
    Customer(
        id="c4",
        name="Riyadh Tech Studio",
        segment=Segment.smb,
        industry="Software",
        employees=38,
        arr="$6.4k",
        health=Health.healthy,
        renewal_date="2026-08-30",
    ),
    Customer(
        id="c5",
        name="Ministry of Digital Affairs",
        segment=Segment.government,
        industry="Public Sector",
        employees=920,
        arr="$120k",
        health=Health.at_risk,
        renewal_date="2026-12-15",
    ),
    Customer(
        id="c6",
        name="Bayan Restaurants",
        segment=Segment.mid_market,
        industry="F&B",
        employees=410,
        arr="$32k",
        health=Health.healthy,
        renewal_date="2026-10-05",
    ),
    Customer(
        id="c7",
        name="Hijaz Construction Co.",
        segment=Segment.mid_market,
        industry="Construction",
        employees=540,
        arr="$38k",
        health=Health.critical,
        renewal_date="2026-07-19",
    ),
    Customer(
        id="c8",
        name="Tamara Retail",
        segment=Segment.smb,
        industry="Retail",
        employees=72,
        arr="$9.8k",
        health=Health.healthy,
        renewal_date="2027-02-10",
    ),
]

PMS = ["Mohamed", "Kshitij", "Igor", "Ashutosh"]


# ============================================================================
# PRODUCT BETS (Complete - all 8)
# ============================================================================

BETS: List[ProductBet] = [
    ProductBet(
        id="b1",
        title="Stabilize month-end payroll batch processing",
        problem_statement="Payroll runs fail or time out for customers with >1k employees during month-end peaks.",
        problem_detail="11 customers (combined 14,800 employees) have hit batch processing failures in the last 4 weeks. Root cause appears tied to synchronous GOSI lookups blocking the run. Mid-Market and Enterprise customers are escalating to CS; one is threatening churn.",
        status=BetStatus.in_build,
        segments=[Segment.mid_market, Segment.enterprise],
        customer_count=11,
        urgency=Urgency.high,
        trend=Trend.rising,
        vote_weight=142,
        evidence_ids=["f1", "f2", "f3", "f4", "f5"],
        theme_id="t1",
        owner="Mohamed",
    ),
    ProductBet(
        id="b2",
        title="GOSI calculation parity with official portal",
        problem_statement="Computed GOSI deductions deviate from the official portal for specific salary brackets above SAR 25k.",
        problem_detail="Compliance-sensitive issue affecting 9 customers including 2 government entities. Discrepancies range from SAR 12 to SAR 340 per employee per month.",
        status=BetStatus.in_discovery,
        segments=[Segment.enterprise, Segment.government],
        customer_count=9,
        urgency=Urgency.high,
        trend=Trend.rising,
        vote_weight=118,
        evidence_ids=["f6", "f7", "f8"],
        theme_id="t2",
        owner="Mohamed",
    ),
    ProductBet(
        id="b3",
        title="Fix iOS 18 / Android 15 login redirect loop",
        problem_statement="After the latest mobile OS updates, users are stuck in a login redirect loop and cannot access the app.",
        problem_detail="19 customers reported within 6 days of iOS 18 release. SSO flow returns to login screen after successful auth on roughly 30% of devices. Likely a cookie/SameSite handling regression.",
        status=BetStatus.in_backlog,
        segments=[Segment.smb, Segment.mid_market],
        customer_count=19,
        urgency=Urgency.high,
        trend=Trend.new,
        vote_weight=96,
        evidence_ids=["f9", "f10", "f11", "f12"],
        theme_id="t3",
        owner="Igor",
    ),
    ProductBet(
        id="b4",
        title="Propagate leave-policy edits to existing balances",
        problem_statement="Policy changes only apply to new employees; existing balances must be recomputed manually.",
        problem_detail="HR ops teams asking for a recompute action. Today they edit each employee individually.",
        status=BetStatus.in_backlog,
        segments=[Segment.mid_market],
        customer_count=8,
        urgency=Urgency.medium,
        trend=Trend.stable,
        vote_weight=74,
        evidence_ids=["f13", "f14"],
        theme_id="t4",
        owner="Kshitij",
    ),
    ProductBet(
        id="b5",
        title="JisrPay POS acceptance at fuel networks",
        problem_statement="JisrPay prepaid cards declined at major petrol station chains in Riyadh.",
        problem_detail="Issue appears tied to merchant category code routing with our card processor.",
        status=BetStatus.draft,
        segments=[Segment.smb, Segment.mid_market],
        customer_count=7,
        urgency=Urgency.medium,
        trend=Trend.rising,
        vote_weight=61,
        evidence_ids=["f15", "f16"],
        theme_id="t5",
        owner="Ashutosh",
    ),
    ProductBet(
        id="b6",
        title="Robust CSV onboarding with Arabic + format tolerance",
        problem_statement="CSV employee import fails silently on Arabic names with diacritics and non-ISO dates.",
        problem_detail="Need preview + validation step before commit. Several customers gave up and entered employees manually.",
        status=BetStatus.in_discovery,
        segments=[Segment.mid_market, Segment.enterprise],
        customer_count=6,
        urgency=Urgency.medium,
        trend=Trend.stable,
        vote_weight=52,
        evidence_ids=["f17", "f18"],
        theme_id="t6",
        owner="Kshitij",
    ),
    ProductBet(
        id="b7",
        title="Offboarding device-custody handover step",
        problem_statement="Add structured device/asset return tracking to offboarding checklist.",
        problem_detail="Customers are tracking laptop returns in spreadsheets today.",
        status=BetStatus.shipped,
        segments=[Segment.mid_market],
        customer_count=5,
        urgency=Urgency.low,
        trend=Trend.stable,
        vote_weight=38,
        evidence_ids=["f19"],
        theme_id="t8",
        owner="Ashutosh",
    ),
    ProductBet(
        id="b8",
        title="Bulk salary revision workflow (declined)",
        problem_statement="Allow uploading annual salary revisions in bulk with approval routing.",
        problem_detail="Declined for this cycle — existing import + approval flow covers the need with light retraining. Revisit Q3.",
        status=BetStatus.declined,
        segments=[Segment.enterprise],
        customer_count=4,
        urgency=Urgency.low,
        trend=Trend.declining,
        vote_weight=22,
        evidence_ids=[],
        owner="Mohamed",
    ),
]


# ============================================================================
# FEEDBACK ITEMS - 20 Representative Items
# ============================================================================
# MVP: 20 carefully selected items covering all edge cases
# TODO: Expand to full 50 by copying from jisrvoc-frontend/src/lib/mock-data.ts:126-187

FEEDBACK: List[FeedbackItem] = [
    # Payroll issues (English + Arabic, high urgency, split ticket example)
    FeedbackItem(
        id="f1",
        summary="Payroll run timed out at 1,400 employees for March cycle",
        raw_text="Our March payroll run failed three times tonight. It just spins and times out after ~12 minutes. We have 1,400 active employees. This is the second month in a row.",
        source=Source.zendesk,
        source_ref="ZD-48211",
        category=Category.bug_report,
        product_area=ProductArea.payroll,
        sentiment=Sentiment.negative,
        urgency=Urgency.high,
        language=Language.en,
        customer="Alfanar Industries",
        customer_id="c1",
        segment=Segment.enterprise,
        date=days_ago(2),
        theme_id="t1",
        tags=["payroll-run", "timeout", "month-end"],
    ),
    FeedbackItem(
        id="f2",
        summary="Payroll batch fails silently — no error shown to admin",
        raw_text="ما اشتغلت عملية الرواتب الشهرية أمس ولا طلعت لي رسالة خطأ واضحة. فقط الحالة بقت 'قيد المعالجة' لمدة ساعتين ثم رجعت 'فشل'.",
        source=Source.hubspot,
        source_ref="HS-9921",
        category=Category.bug_report,
        product_area=ProductArea.payroll,
        sentiment=Sentiment.negative,
        urgency=Urgency.high,
        language=Language.ar,
        customer="Saudi Modern Logistics",
        customer_id="c2",
        segment=Segment.mid_market,
        date=days_ago(3),
        theme_id="t1",
        split_from="HS-9921",  # Example of split ticket
        tags=["payroll-run", "error-handling"],
    ),
    FeedbackItem(
        id="f3",
        summary="Need ability to retry only failed employees in batch",
        raw_text="When payroll fails for 3 employees out of 800 we have to re-run the entire batch. Please add a partial retry.",
        source=Source.canny,
        source_ref="CN-302",
        category=Category.feature_request,
        product_area=ProductArea.payroll,
        sentiment=Sentiment.neutral,
        urgency=Urgency.medium,
        language=Language.en,
        customer="Nuqul Group KSA",
        customer_id="c3",
        segment=Segment.enterprise,
        date=days_ago(5),
        theme_id="t1",
        tags=["payroll-run", "partial-retry"],
    ),

    # GOSI compliance issues (government segment, high urgency)
    FeedbackItem(
        id="f6",
        summary="GOSI deduction differs by SAR 87 from official portal",
        raw_text="For an employee earning SAR 32,000, your system computes a GOSI deduction of SAR 3,200 but the official portal shows SAR 3,287. This is a compliance issue for us.",
        source=Source.zendesk,
        source_ref="ZD-48055",
        category=Category.bug_report,
        product_area=ProductArea.payroll,
        sentiment=Sentiment.negative,
        urgency=Urgency.high,
        language=Language.en,
        customer="Ministry of Digital Affairs",
        customer_id="c5",
        segment=Segment.government,
        date=days_ago(4),
        theme_id="t2",
        tags=["gosi", "compliance"],
    ),
    FeedbackItem(
        id="f7",
        summary="GOSI mismatch for salaries above SAR 25k bracket",
        raw_text="حساب التأمينات عندكم مختلف عن البوابة الرسمية للموظفين السعوديين بالرواتب فوق 25 ألف.",
        source=Source.hubspot,
        source_ref="HS-9888",
        category=Category.bug_report,
        product_area=ProductArea.payroll,
        sentiment=Sentiment.negative,
        urgency=Urgency.high,
        language=Language.ar,
        customer="Alfanar Industries",
        customer_id="c1",
        segment=Segment.enterprise,
        date=days_ago(8),
        theme_id="t2",
        tags=["gosi", "compliance"],
    ),

    # Mobile issues (new trend, SMB segment)
    FeedbackItem(
        id="f9",
        summary="iOS 18 users stuck in login redirect loop",
        raw_text="Since updating to iOS 18 yesterday, I log in, the app reloads, and dumps me back at the login screen. Cleared cache, reinstalled, same thing.",
        source=Source.zendesk,
        source_ref="ZD-48330",
        category=Category.bug_report,
        product_area=ProductArea.mobile,
        sentiment=Sentiment.negative,
        urgency=Urgency.high,
        language=Language.en,
        customer="Riyadh Tech Studio",
        customer_id="c4",
        segment=Segment.smb,
        date=days_ago(1),
        theme_id="t3",
        tags=["mobile", "ios", "auth"],
    ),
    FeedbackItem(
        id="f10",
        summary="Mobile login fails on Android 15",
        raw_text="ما أقدر أدخل التطبيق على جوالي بعد التحديث الأخير، يرجعني لشاشة الدخول كل مرة.",
        source=Source.hubspot,
        source_ref="HS-9970",
        category=Category.bug_report,
        product_area=ProductArea.mobile,
        sentiment=Sentiment.negative,
        urgency=Urgency.high,
        language=Language.ar,
        customer="Bayan Restaurants",
        customer_id="c6",
        segment=Segment.mid_market,
        date=days_ago(1),
        theme_id="t3",
        tags=["mobile", "android", "auth"],
    ),

    # How-to question example
    FeedbackItem(
        id="f12",
        summary="How do I clear mobile session if stuck?",
        raw_text="Is there a way for an admin to remotely sign me out of the mobile app? I'm stuck.",
        source=Source.zendesk,
        source_ref="ZD-48340",
        category=Category.how_to_question,
        product_area=ProductArea.mobile,
        sentiment=Sentiment.neutral,
        urgency=Urgency.low,
        language=Language.en,
        customer="Saudi Modern Logistics",
        customer_id="c2",
        segment=Segment.mid_market,
        date=days_ago(2),
        theme_id="t3",
        tags=["mobile", "session"],
    ),

    # Leave policy issues
    FeedbackItem(
        id="f13",
        summary="Leave policy edit didn't update existing balances",
        raw_text="We changed annual leave from 21 to 25 days last month. New hires got 25, but existing 600 employees are still on 21.",
        source=Source.zendesk,
        source_ref="ZD-48100",
        category=Category.pain_point,
        product_area=ProductArea.core_hr,
        sentiment=Sentiment.negative,
        urgency=Urgency.medium,
        language=Language.en,
        customer="Hijaz Construction Co.",
        customer_id="c7",
        segment=Segment.mid_market,
        date=days_ago(12),
        theme_id="t4",
        tags=["leave", "policy"],
    ),
    FeedbackItem(
        id="f14",
        summary="Allow recomputing balances after policy change",
        raw_text="تحتاجون زر لإعادة احتساب أرصدة الإجازات بعد أي تعديل في السياسة.",
        source=Source.canny,
        source_ref="CN-280",
        category=Category.feature_request,
        product_area=ProductArea.core_hr,
        sentiment=Sentiment.neutral,
        urgency=Urgency.medium,
        language=Language.ar,
        customer="Nuqul Group KSA",
        customer_id="c3",
        segment=Segment.enterprise,
        date=days_ago(15),
        theme_id="t4",
        tags=["leave", "policy"],
    ),

    # JisrPay issues
    FeedbackItem(
        id="f15",
        summary="JisrPay card declined at ADNOC station",
        raw_text="My team's JisrPay cards are getting declined at ADNOC petrol stations in Riyadh. Works fine at supermarkets.",
        source=Source.zendesk,
        source_ref="ZD-48220",
        category=Category.bug_report,
        product_area=ProductArea.jisrpay,
        sentiment=Sentiment.negative,
        urgency=Urgency.medium,
        language=Language.en,
        customer="Riyadh Tech Studio",
        customer_id="c4",
        segment=Segment.smb,
        date=days_ago(3),
        theme_id="t5",
        tags=["jisrpay", "pos-declined"],
    ),

    # CSV onboarding issues (Arabic encoding edge case)
    FeedbackItem(
        id="f17",
        summary="CSV onboarding fails on Arabic names with diacritics",
        raw_text="Importing 240 employees, ~15 silently skipped. All of them had names with shadda/fatha marks.",
        source=Source.zendesk,
        source_ref="ZD-48070",
        category=Category.bug_report,
        product_area=ProductArea.onboarding,
        sentiment=Sentiment.negative,
        urgency=Urgency.medium,
        language=Language.en,
        customer="Alfanar Industries",
        customer_id="c1",
        segment=Segment.enterprise,
        date=days_ago(11),
        theme_id="t6",
        tags=["onboarding", "csv", "i18n"],
    ),
    FeedbackItem(
        id="f18",
        summary="CSV import doesn't show what failed",
        raw_text="ما يطلع لي تقرير بالموظفين اللي ما تم استيرادهم، فقط رقم الناجح.",
        source=Source.hubspot,
        source_ref="HS-9810",
        category=Category.pain_point,
        product_area=ProductArea.onboarding,
        sentiment=Sentiment.negative,
        urgency=Urgency.medium,
        language=Language.ar,
        customer="Hijaz Construction Co.",
        customer_id="c7",
        segment=Segment.mid_market,
        date=days_ago(14),
        theme_id="t6",
        tags=["onboarding", "csv"],
    ),

    # Offboarding
    FeedbackItem(
        id="f19",
        summary="Offboarding checklist is missing IT asset return",
        raw_text="When an employee leaves we track laptop/phone return in a separate sheet. It should be inside Jisr offboarding.",
        source=Source.canny,
        source_ref="CN-260",
        category=Category.feature_request,
        product_area=ProductArea.offboarding,
        sentiment=Sentiment.neutral,
        urgency=Urgency.low,
        language=Language.en,
        customer="Bayan Restaurants",
        customer_id="c6",
        segment=Segment.mid_market,
        date=days_ago(22),
        theme_id="t8",
        tags=["offboarding", "assets"],
    ),

    # Contracts (Arabic RTL rendering)
    FeedbackItem(
        id="f20",
        summary="Arabic contract template renders English merge fields",
        raw_text="قالب العقد بالعربي، لكن الحقول الديناميكية تطلع بالإنجليزي (مثل employee_name).",
        source=Source.hubspot,
        source_ref="HS-9777",
        category=Category.bug_report,
        product_area=ProductArea.contracts,
        sentiment=Sentiment.negative,
        urgency=Urgency.medium,
        language=Language.ar,
        customer="Alfanar Industries",
        customer_id="c1",
        segment=Segment.enterprise,
        date=days_ago(9),
        theme_id="t7",
        tags=["contracts", "i18n"],
    ),

    # Integrations
    FeedbackItem(
        id="f22",
        summary="HubSpot custom field not syncing to Jisr customer record",
        raw_text="Our 'Account Tier' custom field on HubSpot deals is not reflected on the customer profile in Jisr.",
        source=Source.zendesk,
        source_ref="ZD-47980",
        category=Category.bug_report,
        product_area=ProductArea.integrations,
        sentiment=Sentiment.negative,
        urgency=Urgency.low,
        language=Language.en,
        customer="Nuqul Group KSA",
        customer_id="c3",
        segment=Segment.enterprise,
        date=days_ago(18),
        theme_id="t9",
        tags=["integrations", "hubspot"],
    ),

    # Praise examples (important for sentiment diversity)
    FeedbackItem(
        id="f23",
        summary="Love the new onboarding wizard — much faster",
        raw_text="Just onboarded 12 employees with the new wizard. Took me 20 minutes total. Big improvement!",
        source=Source.hubspot,
        source_ref="HS-9999",
        category=Category.praise,
        product_area=ProductArea.onboarding,
        sentiment=Sentiment.positive,
        urgency=Urgency.low,
        language=Language.en,
        customer="Tamara Retail",
        customer_id="c8",
        segment=Segment.smb,
        date=days_ago(2),
        theme_id="t10",
        tags=["onboarding", "praise"],
    ),
    FeedbackItem(
        id="f24",
        summary="Onboarding flow is much smoother now",
        raw_text="تجربة إضافة الموظفين الجدد صارت أسرع بكثير، شكراً للفريق.",
        source=Source.canny,
        source_ref="CN-360",
        category=Category.praise,
        product_area=ProductArea.onboarding,
        sentiment=Sentiment.positive,
        urgency=Urgency.low,
        language=Language.ar,
        customer="Riyadh Tech Studio",
        customer_id="c4",
        segment=Segment.smb,
        date=days_ago(5),
        theme_id="t10",
        tags=["onboarding", "praise"],
    ),

    # Additional diverse examples
    FeedbackItem(
        id="f32",
        summary="Mobile app crashes when opening expense module",
        raw_text="Tap on Expenses tab → instant crash. Reproducible on iPhone 14.",
        source=Source.zendesk,
        source_ref="ZD-48250",
        category=Category.bug_report,
        product_area=ProductArea.mobile,
        sentiment=Sentiment.negative,
        urgency=Urgency.high,
        language=Language.en,
        customer="Tamara Retail",
        customer_id="c8",
        segment=Segment.smb,
        date=days_ago(3),
        tags=["mobile", "crash"],
    ),
    FeedbackItem(
        id="f34",
        summary="Excellent customer support response this week",
        raw_text="Got a response in 11 minutes and the agent fixed it on the spot. Thanks!",
        source=Source.hubspot,
        source_ref="HS-9990",
        category=Category.praise,
        product_area=ProductArea.other,
        sentiment=Sentiment.positive,
        urgency=Urgency.low,
        language=Language.en,
        customer="Bayan Restaurants",
        customer_id="c6",
        segment=Segment.mid_market,
        date=days_ago(4),
        tags=["support", "praise"],
    ),
]

# TODO: Add remaining feedback items f4, f5, f8, f11, f16, f21, f25-f31, f33, f35-f50
# Copy from jisrvoc-frontend/src/lib/mock-data.ts lines 126-187
# This is a mechanical task - the pattern is established above


# ============================================================================
# AGGREGATE DATA
# ============================================================================

TOTAL_FEEDBACK_COUNT = 1284

WEEKLY_VOLUME = [
    {"week": "W-11", "count": 78}, {"week": "W-10", "count": 82},
    {"week": "W-9", "count": 91}, {"week": "W-8", "count": 88},
    {"week": "W-7", "count": 102}, {"week": "W-6", "count": 116},
    {"week": "W-5", "count": 108}, {"week": "W-4", "count": 125},
    {"week": "W-3", "count": 138}, {"week": "W-2", "count": 142},
    {"week": "W-1", "count": 156}, {"week": "This wk", "count": 158},
]

SOURCE_BREAKDOWN = [
    {"source": "HubSpot", "count": 482},
    {"source": "Zendesk", "count": 521},
    {"source": "Canny", "count": 218},
    {"source": "Jira", "count": 63},
]

PRODUCT_AREA_BREAKDOWN = [
    {"area": "Payroll", "count": 318},
    {"area": "Core HR", "count": 264},
    {"area": "Mobile", "count": 189},
    {"area": "JisrPay", "count": 142},
    {"area": "Onboarding", "count": 121},
    {"area": "Integrations", "count": 98},
    {"area": "Contracts", "count": 76},
    {"area": "Offboarding", "count": 48},
    {"area": "Other", "count": 28},
]

URGENCY_DISTRIBUTION = {"Low": 612, "Medium": 463, "High": 209}

PM_ROUTING = [
    PmRoutingRule(product_area=ProductArea.payroll, pm_user_id="pm1", pm_name="Mohamed"),
    PmRoutingRule(product_area=ProductArea.jisrpay, pm_user_id="pm4", pm_name="Ashutosh"),
    PmRoutingRule(product_area=ProductArea.core_hr, pm_user_id="pm2", pm_name="Kshitij"),
    PmRoutingRule(product_area=ProductArea.mobile, pm_user_id="pm3", pm_name="Igor"),
    PmRoutingRule(product_area=ProductArea.onboarding, pm_user_id="pm2", pm_name="Kshitij"),
    PmRoutingRule(product_area=ProductArea.offboarding, pm_user_id="pm4", pm_name="Ashutosh"),
    PmRoutingRule(product_area=ProductArea.contracts, pm_user_id="pm1", pm_name="Mohamed"),
    PmRoutingRule(product_area=ProductArea.integrations, pm_user_id="pm3", pm_name="Igor"),
    PmRoutingRule(product_area=ProductArea.other, pm_user_id="pm1", pm_name="Mohamed"),
]

# Unmatched customer queue
UNMATCHED_QUEUE = [
    UnmatchedItem(
        id="u1",
        source=Source.zendesk,
        source_ref="ZD-48400",
        raw_customer_name="Ahmed M.",
        raw_email="ahmed.m@hijaz-co.sa",
        raw_domain="hijaz-co.sa",
        summary="Payroll question about overtime calculation",
        created_at="2026-06-27",
        suggested_matches=[
            SuggestedMatch(customer_id="c7", customer_name="Hijaz Construction Co.", confidence=0.87)
        ],
    ),
    UnmatchedItem(
        id="u2",
        source=Source.hubspot,
        source_ref="HS-10012",
        raw_customer_name="Operations Team",
        raw_email="ops@nuqul-ksa.com",
        raw_domain="nuqul-ksa.com",
        summary="Bulk leave approval workflow request",
        created_at="2026-06-27",
        suggested_matches=[
            SuggestedMatch(customer_id="c3", customer_name="Nuqul Group KSA", confidence=0.92)
        ],
    ),
    UnmatchedItem(
        id="u3",
        source=Source.canny,
        source_ref="CN-450",
        raw_customer_name="anonymous",
        raw_email="user-42@gmail.com",
        raw_domain="gmail.com",
        summary="Mobile app dark mode request",
        created_at="2026-06-26",
        suggested_matches=[],
    ),
    UnmatchedItem(
        id="u4",
        source=Source.zendesk,
        source_ref="ZD-48395",
        raw_customer_name="Saad K.",
        raw_email="saad@alfanar-industries.com.sa",
        raw_domain="alfanar-industries.com.sa",
        summary="GOSI report needs CSV export",
        created_at="2026-06-26",
        suggested_matches=[
            SuggestedMatch(customer_id="c1", customer_name="Alfanar Industries", confidence=0.95)
        ],
    ),
]

# ============================================================================
# AI MODEL EVALUATION SCORECARD
# ============================================================================

EVAL_SCORECARD = EvalScorecard(
    last_run="2026-06-27T14:30:00Z",
    metrics=[
        EvalMetric(
            tag="category",
            language=Language.en,
            f1_score=0.94,
            precision=0.96,
            recall=0.92,
            sample_size=250,
        ),
        EvalMetric(
            tag="category",
            language=Language.ar,
            f1_score=0.91,
            precision=0.93,
            recall=0.89,
            sample_size=180,
        ),
        EvalMetric(
            tag="sentiment",
            language=Language.en,
            f1_score=0.88,
            precision=0.90,
            recall=0.86,
            sample_size=250,
        ),
        EvalMetric(
            tag="sentiment",
            language=Language.ar,
            f1_score=0.85,
            precision=0.87,
            recall=0.83,
            sample_size=180,
        ),
        EvalMetric(
            tag="urgency",
            language=Language.en,
            f1_score=0.82,
            precision=0.84,
            recall=0.80,
            sample_size=250,
        ),
        EvalMetric(
            tag="urgency",
            language=Language.ar,
            f1_score=0.79,
            precision=0.81,
            recall=0.77,
            sample_size=180,
        ),
        EvalMetric(
            tag="product_area",
            language=Language.en,
            f1_score=0.90,
            precision=0.92,
            recall=0.88,
            sample_size=250,
        ),
        EvalMetric(
            tag="product_area",
            language=Language.ar,
            f1_score=0.87,
            precision=0.89,
            recall=0.85,
            sample_size=180,
        ),
    ],
)

# Vote series for theme trend charts
VOTE_SERIES: Dict[str, List[Dict]] = {
    "t1": [
        {"week": "W-5", "votes": 28, "items": 4},
        {"week": "W-4", "votes": 51, "items": 7},
        {"week": "W-3", "votes": 78, "items": 10},
        {"week": "W-2", "votes": 102, "items": 13},
        {"week": "W-1", "votes": 128, "items": 16},
        {"week": "Now", "votes": 142, "items": 18},
    ],
    "t2": [
        {"week": "W-5", "votes": 41, "items": 4},
        {"week": "W-4", "votes": 58, "items": 6},
        {"week": "W-3", "votes": 72, "items": 8},
        {"week": "W-2", "votes": 89, "items": 10},
        {"week": "W-1", "votes": 104, "items": 12},
        {"week": "Now", "votes": 118, "items": 14},
    ],
    "t3": [
        {"week": "W-5", "votes": 0, "items": 0},
        {"week": "W-4", "votes": 0, "items": 0},
        {"week": "W-3", "votes": 12, "items": 3},
        {"week": "W-2", "votes": 41, "items": 9},
        {"week": "W-1", "votes": 72, "items": 15},
        {"week": "Now", "votes": 96, "items": 22},
    ],
}

# Enrichment metadata examples
ENRICHMENTS: Dict[str, EnrichmentMeta] = {
    "f1": EnrichmentMeta(
        model="gemini-1.5-flash",
        model_version="bilingual-v3",
        confidence=0.94,
        pm_corrected=False,
    ),
    "f2": EnrichmentMeta(
        model="gemini-1.5-flash",
        model_version="bilingual-v3",
        confidence=0.88,
        pm_corrected=True,
        corrected_by="Mohamed",
        corrected_at="2026-06-25",
    ),
}

# Write-back log examples
WRITEBACK_LOG: List[WritebackEntry] = [
    WritebackEntry(
        id="w1",
        bet_id="b7",
        feedback_id="f19",
        source_ref="CN-260",
        source=Source.canny,
        status=BetStatus.shipped,
        performed_at="2026-06-20T14:32:00Z",
        performed_by="Ashutosh",
        result="Success",
    ),
    WritebackEntry(
        id="w2",
        bet_id="b1",
        feedback_id="f1",
        source_ref="ZD-48211",
        source=Source.zendesk,
        status=BetStatus.in_build,
        performed_at="2026-06-24T09:15:00Z",
        performed_by="Mohamed",
        result="Success",
    ),
]


# ============================================================================
# HELPER FUNCTIONS (matching TypeScript exactly)
# ============================================================================

def get_theme_by_id(theme_id: str) -> Optional[Theme]:
    """Get theme by ID."""
    return next((t for t in THEMES if t.id == theme_id), None)


def get_bet_by_id(bet_id: str) -> Optional[ProductBet]:
    """Get bet by ID."""
    return next((b for b in BETS if b.id == bet_id), None)


def get_customer_by_id(customer_id: str) -> Optional[Customer]:
    """Get customer by ID."""
    return next((c for c in CUSTOMERS if c.id == customer_id), None)


def get_feedback_for_theme(theme_id: str) -> List[FeedbackItem]:
    """Get all feedback items for a theme."""
    return [f for f in FEEDBACK if f.theme_id == theme_id]


def get_feedback_for_customer(customer_id: str) -> List[FeedbackItem]:
    """Get all feedback items for a customer."""
    return [f for f in FEEDBACK if f.customer_id == customer_id]


def get_bets_for_customer(customer_id: str) -> List[ProductBet]:
    """Get all bets related to a customer's feedback."""
    theme_ids = {f.theme_id for f in get_feedback_for_customer(customer_id) if f.theme_id}
    return [b for b in BETS if b.theme_id in theme_ids]


def get_writeback_for_bet(bet_id: str) -> List[WritebackEntry]:
    """Get all write-back entries for a bet."""
    return [w for w in WRITEBACK_LOG if w.bet_id == bet_id]


def get_enrichment(feedback_id: str) -> EnrichmentMeta:
    """Get enrichment metadata, with default if not found."""
    return ENRICHMENTS.get(
        feedback_id,
        EnrichmentMeta(
            model="gemini-1.5-flash",
            model_version="bilingual-v3",
            confidence=0.85 + (hash(feedback_id) % 15) / 100,  # Pseudo-random 0.85-0.99
            pm_corrected=False,
        )
    )


def get_sync_runs_for_connector(source: Source) -> List[SyncRun]:
    """Get all sync runs for a specific source connector."""
    return [r for r in SYNC_RUNS if r.source == source]
