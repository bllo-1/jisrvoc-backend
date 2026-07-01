"""
Unit tests for ComplianceAgent.

Tests compliance detection and highest impact classification.
"""

import pytest
from app.agents.base import AgentContext, AgentStatus
from app.agents.compliance_agent import ComplianceAgent
from app.services.rule_engine import get_rule_engine


@pytest.fixture
def compliance_agent():
    """Create ComplianceAgent instance."""
    rule_engine = get_rule_engine()
    return ComplianceAgent(rule_engine)


@pytest.mark.asyncio
class TestComplianceAgent:
    """Test compliance detection agent execution."""

    async def test_gosi_compliance_detection(self, compliance_agent):
        """Test GOSI terms trigger compliance flag."""
        context = AgentContext(
            feedback_id="test-101",
            raw_text="GOSI file submission deadline and social insurance contribution",
            language="EN",
            correlation_id="test-corr-101",
        )

        result = await compliance_agent.execute_with_logging(context)

        assert result.status == AgentStatus.SUCCESS
        assert "Compliance" in context.compliance_tags
        assert "GOSI" in context.compliance_tags
        assert result.metadata["is_compliance"] is True
        assert len(result.metadata["regulations"]) > 0

    async def test_wps_compliance_detection(self, compliance_agent):
        """Test WPS terms trigger compliance flag."""
        context = AgentContext(
            feedback_id="test-102",
            raw_text="WPS bank file must be ready for wage protection deadline",
            language="EN",
            correlation_id="test-corr-102",
        )

        result = await compliance_agent.execute_with_logging(context)

        assert result.status == AgentStatus.SUCCESS
        assert "Compliance" in context.compliance_tags
        assert result.metadata["is_compliance"] is True

    async def test_pdpl_compliance_detection(self, compliance_agent):
        """Test PDPL terms trigger compliance flag."""
        context = AgentContext(
            feedback_id="test-103",
            raw_text="PDPL personal data protection and Article 18 retention policy needed",
            language="EN",
            correlation_id="test-corr-103",
        )

        result = await compliance_agent.execute_with_logging(context)

        assert result.status == AgentStatus.SUCCESS
        assert "Compliance" in context.compliance_tags
        assert "PDPL" in context.compliance_tags

    async def test_multiple_regulations(self, compliance_agent):
        """Test multiple regulations detected."""
        context = AgentContext(
            feedback_id="test-104",
            raw_text="Need GOSI file for social insurance and WPS bank submission",
            language="EN",
            correlation_id="test-corr-104",
        )

        result = await compliance_agent.execute_with_logging(context)

        assert result.status == AgentStatus.SUCCESS
        assert len(result.metadata["regulations"]) >= 2
        # Should have both GOSI and WPS
        regulation_names = [r["name"] for r in result.metadata["regulations"]]
        assert "GOSI" in regulation_names

    async def test_trigger_phrases(self, compliance_agent):
        """Test compliance trigger phrases."""
        context = AgentContext(
            feedback_id="test-105",
            raw_text="This is mandatory by law and required for government audit",
            language="EN",
            correlation_id="test-corr-105",
        )

        result = await compliance_agent.execute_with_logging(context)

        assert result.status == AgentStatus.SUCCESS
        assert "Compliance" in context.compliance_tags

    async def test_no_compliance_terms(self, compliance_agent):
        """Test feedback with no compliance terms."""
        context = AgentContext(
            feedback_id="test-106",
            raw_text="Mobile app is slow when loading employee list",
            language="EN",
            correlation_id="test-corr-106",
        )

        result = await compliance_agent.execute_with_logging(context)

        assert result.status == AgentStatus.SUCCESS
        assert result.metadata["is_compliance"] is False
        assert len(result.metadata["regulations"]) == 0
        assert len(context.compliance_tags) == 0

    async def test_confidence_scores(self, compliance_agent):
        """Test compliance confidence scores."""
        context = AgentContext(
            feedback_id="test-107",
            raw_text="GOSI and ZATCA compliance required",
            language="EN",
            correlation_id="test-corr-107",
        )

        result = await compliance_agent.execute_with_logging(context)

        assert result.status == AgentStatus.SUCCESS
        assert len(result.confidence_scores) > 0
        # All compliance matches should have high confidence (1.0)
        for score in result.confidence_scores.values():
            assert score >= 0.7  # High or Medium confidence

    async def test_country_tracking(self, compliance_agent):
        """Test country information is tracked."""
        context = AgentContext(
            feedback_id="test-108",
            raw_text="Kuwait labor law MoSAL compliance needed",
            language="EN",
            correlation_id="test-corr-108",
        )

        result = await compliance_agent.execute_with_logging(context)

        assert result.status == AgentStatus.SUCCESS
        if result.metadata["regulations"]:
            # Check first regulation has country
            assert result.metadata["regulations"][0].get("country") is not None

    async def test_compliance_tags_not_duplicated(self, compliance_agent):
        """Test compliance tags are not duplicated."""
        context = AgentContext(
            feedback_id="test-109",
            raw_text="GOSI GOSI GOSI mentioned multiple times",
            language="EN",
            correlation_id="test-corr-109",
        )

        result = await compliance_agent.execute_with_logging(context)

        assert result.status == AgentStatus.SUCCESS
        # GOSI should only appear once in compliance_tags
        assert context.compliance_tags.count("GOSI") == 1
        assert context.compliance_tags.count("Compliance") == 1
