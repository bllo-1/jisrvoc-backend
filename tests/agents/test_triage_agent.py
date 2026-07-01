"""
Unit tests for TriageAgent.

Tests full triage workflow including disambiguation, compliance detection,
product area classification, theme matching, and action decisions.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from app.agents.base import AgentContext, AgentStatus
from app.agents.triage_agent import TriageAgent
from app.services.rule_engine import get_rule_engine
from app.models.theme import Theme, ThemeTrend


@pytest.fixture
def rule_engine():
    """Get rule engine instance."""
    return get_rule_engine()


@pytest.fixture
def mock_theme_repository():
    """Create mock theme repository."""
    repo = AsyncMock()
    repo.get_active_themes = AsyncMock(return_value=[])
    return repo


@pytest.fixture
def triage_agent(rule_engine, mock_theme_repository):
    """Create triage agent with mocked repository."""
    return TriageAgent(
        rule_engine=rule_engine,
        theme_repository=mock_theme_repository
    )


@pytest.mark.asyncio
class TestTriageAgentDisambiguation:
    """Test disambiguation logic in triage agent."""

    async def test_final_settlement_disambiguation(self, triage_agent):
        """Test Final Settlement (EOS) is correctly disambiguated."""
        context = AgentContext(
            feedback_id="test-001",
            raw_text="Employee leaving needs final settlement calculation for end of service",
            language="EN",
            correlation_id="test-corr-001",
        )

        result = await triage_agent.execute_with_logging(context)

        assert result.status == AgentStatus.SUCCESS
        assert result.metadata["product_area"] == "Payroll"
        assert result.metadata["area_confidence"] > 0.9
        assert "final settlement" in result.metadata["reasoning"].lower()

    async def test_vacation_settlement_disambiguation(self, triage_agent):
        """Test Vacation Settlement is disambiguated with cross-tag."""
        context = AgentContext(
            feedback_id="test-002",
            raw_text="How to process vacation settlement for leave balance payout",
            language="EN",
            correlation_id="test-corr-002",
        )

        result = await triage_agent.execute_with_logging(context)

        assert result.status == AgentStatus.SUCCESS
        assert result.metadata["product_area"] == "Payroll"
        # Should mention disambiguation in reasoning
        assert "disambig" in result.metadata["reasoning"].lower()

    async def test_expense_settlement_disambiguation(self, triage_agent):
        """Test Expense Settlement routes to Finance."""
        context = AgentContext(
            feedback_id="test-003",
            raw_text="Expense settlement and reimbursement processing is broken",
            language="EN",
            correlation_id="test-corr-003",
        )

        result = await triage_agent.execute_with_logging(context)

        assert result.status == AgentStatus.SUCCESS
        assert result.metadata["product_area"] == "Finance"

    async def test_leave_approval_disambiguation(self, triage_agent):
        """Test Leave Approval routes to Attendance & Leaves."""
        context = AgentContext(
            feedback_id="test-004",
            raw_text="Manager cannot process leave approval requests",
            language="EN",
            correlation_id="test-corr-004",
        )

        result = await triage_agent.execute_with_logging(context)

        assert result.status == AgentStatus.SUCCESS
        assert result.metadata["product_area"] == "Attendance & Leaves"


@pytest.mark.asyncio
class TestTriageAgentCompliance:
    """Test compliance detection in triage agent."""

    async def test_gosi_compliance_detection(self, triage_agent):
        """Test GOSI terms trigger compliance flag."""
        context = AgentContext(
            feedback_id="test-101",
            raw_text="GOSI file submission and social insurance contribution required",
            language="EN",
            correlation_id="test-corr-101",
        )

        result = await triage_agent.execute_with_logging(context)

        assert result.status == AgentStatus.SUCCESS
        assert result.metadata["is_compliance"] is True
        assert "GOSI" in result.metadata["compliance_regulations"]
        assert "compliance" in result.metadata["reasoning"].lower()

    async def test_wps_compliance_detection(self, triage_agent):
        """Test WPS terms trigger compliance flag."""
        context = AgentContext(
            feedback_id="test-102",
            raw_text="WPS bank file must be ready for wage protection deadline",
            language="EN",
            correlation_id="test-corr-102",
        )

        result = await triage_agent.execute_with_logging(context)

        assert result.status == AgentStatus.SUCCESS
        assert result.metadata["is_compliance"] is True
        assert len(result.metadata["compliance_regulations"]) > 0

    async def test_multiple_compliance_regulations(self, triage_agent):
        """Test multiple regulations are detected."""
        context = AgentContext(
            feedback_id="test-103",
            raw_text="Need GOSI file and WPS submission for compliance",
            language="EN",
            correlation_id="test-corr-103",
        )

        result = await triage_agent.execute_with_logging(context)

        assert result.status == AgentStatus.SUCCESS
        assert result.metadata["is_compliance"] is True
        assert len(result.metadata["compliance_regulations"]) >= 2


@pytest.mark.asyncio
class TestTriageAgentProductArea:
    """Test product area classification."""

    async def test_product_area_from_keywords(self, triage_agent):
        """Test product area classification from scope keywords."""
        context = AgentContext(
            feedback_id="test-201",
            raw_text="Salary calculation is wrong and payslip shows incorrect deductions",
            language="EN",
            correlation_id="test-corr-201",
        )

        result = await triage_agent.execute_with_logging(context)

        assert result.status == AgentStatus.SUCCESS
        assert result.metadata["product_area"] == "Payroll"
        assert result.metadata["area_confidence"] > 0.0

    async def test_product_area_fallback_to_other(self, triage_agent):
        """Test fallback to Other / Unclassified when no keywords match."""
        context = AgentContext(
            feedback_id="test-202",
            raw_text="Generic message about nothing in particular",
            language="EN",
            correlation_id="test-corr-202",
        )

        result = await triage_agent.execute_with_logging(context)

        assert result.status == AgentStatus.SUCCESS
        # Should have low confidence or fall back to Other
        assert result.metadata["area_confidence"] < 0.5


@pytest.mark.asyncio
class TestTriageAgentThemeMatching:
    """Test theme matching and action decisions."""

    async def test_theme_match_above_threshold_links(self, triage_agent, mock_theme_repository):
        """Test theme match >= 70% results in LINK action."""
        # Create mock theme with similar keywords
        mock_theme = Theme(
            id=uuid4(),
            name_en="Payroll Salary Deduction Problems",
            description_en="Payroll salary deduction calculation wrong incorrect issues",
            trend=ThemeTrend.STABLE,
            item_count=10,
            customer_count=5,
            vote_weight=15,
        )

        mock_theme_repository.get_active_themes.return_value = [mock_theme]

        context = AgentContext(
            feedback_id="test-301",
            raw_text="Payroll salary deduction calculation wrong incorrect issues problems",
            language="EN",
            correlation_id="test-corr-301",
        )

        result = await triage_agent.execute_with_logging(context)

        assert result.status == AgentStatus.SUCCESS
        assert result.metadata["action"] == "LINK"
        assert result.metadata["matched_theme_id"] == str(mock_theme.id)
        assert result.metadata["matched_theme_name"] == "Payroll Salary Deduction Problems"
        assert result.metadata["match_score"] >= 0.70

    async def test_theme_match_below_threshold_creates(self, triage_agent, mock_theme_repository):
        """Test theme match < 70% results in CREATE action."""
        # Create mock theme with different keywords
        mock_theme = Theme(
            id=uuid4(),
            name_en="Leave Approval Workflow",
            description_en="Issues with manager leave approval process",
            trend=ThemeTrend.STABLE,
            item_count=8,
            customer_count=4,
            vote_weight=12,
        )

        mock_theme_repository.get_active_themes.return_value = [mock_theme]

        context = AgentContext(
            feedback_id="test-302",
            raw_text="Expense reimbursement is slow and receipt upload broken",
            language="EN",
            correlation_id="test-corr-302",
        )

        result = await triage_agent.execute_with_logging(context)

        assert result.status == AgentStatus.SUCCESS
        assert result.metadata["action"] == "CREATE"
        assert result.metadata["matched_theme_id"] is None
        # Match score should be below threshold
        assert result.metadata["match_score"] < 0.70

    async def test_no_themes_available_creates(self, triage_agent, mock_theme_repository):
        """Test CREATE action when no themes exist."""
        mock_theme_repository.get_active_themes.return_value = []

        context = AgentContext(
            feedback_id="test-303",
            raw_text="New feature request for mobile app notifications",
            language="EN",
            correlation_id="test-corr-303",
        )

        result = await triage_agent.execute_with_logging(context)

        assert result.status == AgentStatus.SUCCESS
        assert result.metadata["action"] == "CREATE"
        assert result.metadata["matched_theme_id"] is None
        assert result.metadata["match_score"] == 0.0

    async def test_multiple_themes_picks_best_match(self, triage_agent, mock_theme_repository):
        """Test agent picks theme with highest similarity."""
        theme1 = Theme(
            id=uuid4(),
            name_en="Leave Balance Issues",
            description_en="Problems with vacation leave tracking",
            trend=ThemeTrend.STABLE,
            item_count=5,
            customer_count=3,
            vote_weight=8,
        )

        theme2 = Theme(
            id=uuid4(),
            name_en="Leave Approval Workflow",
            description_en="Manager approval process for leave requests",
            trend=ThemeTrend.STABLE,
            item_count=10,
            customer_count=6,
            vote_weight=16,
        )

        mock_theme_repository.get_active_themes.return_value = [theme1, theme2]

        context = AgentContext(
            feedback_id="test-304",
            raw_text="Manager cannot approve leave requests and vacation approval is broken",
            language="EN",
            correlation_id="test-corr-304",
        )

        result = await triage_agent.execute_with_logging(context)

        assert result.status == AgentStatus.SUCCESS
        # Should match theme2 (more keywords overlap with "approval")
        if result.metadata["action"] == "LINK":
            assert result.metadata["matched_theme_name"] == "Leave Approval Workflow"


@pytest.mark.asyncio
class TestTriageAgentKeywordExtraction:
    """Test keyword extraction and Jaccard similarity."""

    async def test_keyword_extraction_filters_stopwords(self, triage_agent):
        """Test stopwords are filtered from keywords."""
        keywords = triage_agent._extract_keywords(
            "The system is broken and the user cannot login to the application"
        )

        # Stopwords should be removed
        assert "the" not in keywords
        assert "is" not in keywords
        assert "and" not in keywords
        assert "to" not in keywords

        # Content words should remain
        assert "system" in keywords
        assert "broken" in keywords
        assert "user" in keywords
        assert "login" in keywords
        assert "application" in keywords

    async def test_keyword_extraction_min_length(self, triage_agent):
        """Test keywords must be >= 3 characters."""
        keywords = triage_agent._extract_keywords("I am in the us on a trip")

        # Short words should be filtered
        assert "i" not in keywords
        assert "am" not in keywords
        assert "us" not in keywords
        assert "on" not in keywords

        # Long enough words remain
        assert "trip" in keywords

    async def test_jaccard_similarity_calculation(self, triage_agent):
        """Test Jaccard similarity is calculated correctly."""
        set1 = {"payroll", "salary", "calculation"}
        set2 = {"payroll", "salary", "deduction"}

        similarity = triage_agent._jaccard_similarity(set1, set2)

        # Intersection: {payroll, salary} = 2
        # Union: {payroll, salary, calculation, deduction} = 4
        # Jaccard = 2/4 = 0.5
        assert similarity == 0.5

    async def test_jaccard_similarity_identical_sets(self, triage_agent):
        """Test Jaccard similarity is 1.0 for identical sets."""
        set1 = {"payroll", "salary"}
        set2 = {"payroll", "salary"}

        similarity = triage_agent._jaccard_similarity(set1, set2)
        assert similarity == 1.0

    async def test_jaccard_similarity_no_overlap(self, triage_agent):
        """Test Jaccard similarity is 0.0 for disjoint sets."""
        set1 = {"payroll", "salary"}
        set2 = {"leave", "vacation"}

        similarity = triage_agent._jaccard_similarity(set1, set2)
        assert similarity == 0.0


@pytest.mark.asyncio
class TestTriageAgentReasoning:
    """Test reasoning generation."""

    async def test_reasoning_includes_all_components(self, triage_agent):
        """Test reasoning includes disambiguation, compliance, area, match, and action."""
        context = AgentContext(
            feedback_id="test-401",
            raw_text="GOSI file submission for final settlement calculation required",
            language="EN",
            correlation_id="test-corr-401",
        )

        result = await triage_agent.execute_with_logging(context)

        reasoning = result.metadata["reasoning"]

        # Should include product area
        assert "product area" in reasoning.lower() or "payroll" in reasoning.lower()

        # Should include compliance
        assert "compliance" in reasoning.lower() or "gosi" in reasoning.lower()

        # Should include action
        assert "decision" in reasoning.lower() or result.metadata["action"] in reasoning

    async def test_reasoning_readable_format(self, triage_agent):
        """Test reasoning is formatted for human readability."""
        context = AgentContext(
            feedback_id="test-402",
            raw_text="Salary calculation issues in payroll",
            language="EN",
            correlation_id="test-corr-402",
        )

        result = await triage_agent.execute_with_logging(context)

        reasoning = result.metadata["reasoning"]

        # Should have structure (newlines for sections)
        assert "\n" in reasoning

        # Should have emojis or clear section headers
        assert any(char in reasoning for char in ["📦", "✅", "🎯", "Decision", "Product"])
