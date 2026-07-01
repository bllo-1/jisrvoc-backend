"""
Unit tests for DisambiguationAgent.

Tests agent behavior including context enrichment and cross-tagging.
"""

import pytest
from app.agents.base import AgentContext, AgentStatus
from app.agents.disambiguation_agent import DisambiguationAgent
from app.services.rule_engine import get_rule_engine


@pytest.fixture
def disambiguation_agent():
    """Create DisambiguationAgent instance."""
    rule_engine = get_rule_engine()
    return DisambiguationAgent(rule_engine)


@pytest.mark.asyncio
class TestDisambiguationAgent:
    """Test disambiguation agent execution."""

    async def test_final_settlement_classification(self, disambiguation_agent):
        """Test agent classifies Final Settlement correctly."""
        context = AgentContext(
            feedback_id="test-001",
            raw_text="Employee leaving company needs final settlement for end of service",
            language="EN",
            correlation_id="test-corr-001",
        )

        result = await disambiguation_agent.execute_with_logging(context)

        assert result.status == AgentStatus.SUCCESS
        assert context.product_area == "Payroll"
        assert "scope:Payroll" in result.tags_added
        assert result.execution_time_ms > 0

    async def test_vacation_settlement_with_cross_tag(self, disambiguation_agent):
        """Test Vacation Settlement adds cross-tag."""
        context = AgentContext(
            feedback_id="test-002",
            raw_text="Need to process vacation settlement for leave balance payout",
            language="EN",
            correlation_id="test-corr-002",
        )

        result = await disambiguation_agent.execute_with_logging(context)

        assert result.status == AgentStatus.SUCCESS
        assert context.product_area == "Payroll"
        assert "Attendance & Leaves" in context.cross_tags
        assert "cross_tag:Attendance & Leaves" in result.tags_added

    async def test_leave_approval_cross_tag(self, disambiguation_agent):
        """Test Leave Approval adds Org Management cross-tag."""
        context = AgentContext(
            feedback_id="test-003",
            raw_text="Manager cannot process leave approval requests in the system",
            language="EN",
            correlation_id="test-corr-003",
        )

        result = await disambiguation_agent.execute_with_logging(context)

        assert result.status == AgentStatus.SUCCESS
        assert "Org Management" in context.cross_tags

    async def test_no_matches(self, disambiguation_agent):
        """Test agent succeeds with no matches."""
        context = AgentContext(
            feedback_id="test-004",
            raw_text="This is generic feedback with no specific keywords",
            language="EN",
            correlation_id="test-corr-004",
        )

        result = await disambiguation_agent.execute_with_logging(context)

        assert result.status == AgentStatus.SUCCESS
        assert len(result.tags_added) == 0
        assert context.product_area is None

    async def test_multiple_disambiguation_terms(self, disambiguation_agent):
        """Test feedback with multiple disambiguable terms."""
        context = AgentContext(
            feedback_id="test-005",
            raw_text="Final settlement calculation and leave approval both broken",
            language="EN",
            correlation_id="test-corr-005",
        )

        result = await disambiguation_agent.execute_with_logging(context)

        assert result.status == AgentStatus.SUCCESS
        # Should have multiple matches in metadata
        assert len(result.metadata.get("matches", [])) > 0

    async def test_confidence_scores(self, disambiguation_agent):
        """Test agent returns confidence scores."""
        context = AgentContext(
            feedback_id="test-006",
            raw_text="GOSI file generation is broken for submissions",
            language="EN",
            correlation_id="test-corr-006",
        )

        result = await disambiguation_agent.execute_with_logging(context)

        assert result.status == AgentStatus.SUCCESS
        assert len(result.confidence_scores) > 0
        # Confidence should be between 0 and 1
        for score in result.confidence_scores.values():
            assert 0.0 <= score <= 1.0

    async def test_agent_result_added_to_context(self, disambiguation_agent):
        """Test agent result is tracked in context."""
        context = AgentContext(
            feedback_id="test-007",
            raw_text="Expense settlement reimbursement issue",
            language="EN",
            correlation_id="test-corr-007",
        )

        result = await disambiguation_agent.execute_with_logging(context)

        # Add result to context (this would be done by pipeline)
        context.agent_results.append(result)

        assert len(context.agent_results) == 1
        assert context.agent_results[0].agent_name == "disambiguation"
