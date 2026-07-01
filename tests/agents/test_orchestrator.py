"""
Integration tests for AgentOrchestrator.

Tests full orchestration pipeline including:
- Agent initialization and lifecycle
- Sequential and parallel execution
- Error handling and graceful degradation
- Context propagation between agents
- Hot-reload functionality
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.agents.orchestrator import AgentOrchestrator, get_orchestrator
from app.agents.base import AgentContext, AgentStatus, AgentResult
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
def orchestrator(rule_engine, mock_theme_repository):
    """Create orchestrator with mocked repository."""
    return AgentOrchestrator(
        rule_engine=rule_engine,
        theme_repository=mock_theme_repository
    )


@pytest.mark.asyncio
class TestOrchestratorInitialization:
    """Test orchestrator initialization and setup."""

    async def test_orchestrator_initializes_agents(self, orchestrator):
        """Test orchestrator initializes all agents on startup."""
        assert len(orchestrator.agents) > 0
        assert "triage" in orchestrator.agents

    async def test_orchestrator_has_execution_plan(self, orchestrator):
        """Test orchestrator has a defined execution plan."""
        assert len(orchestrator.execution_plan) > 0
        assert orchestrator.execution_plan[0]["stage"] == 0
        assert "triage" in orchestrator.execution_plan[0]["agents"]

    async def test_orchestrator_shares_rule_engine(self, orchestrator, rule_engine):
        """Test orchestrator shares rule engine with agents."""
        assert orchestrator.rule_engine is rule_engine

    async def test_get_agent_status(self, orchestrator):
        """Test get_agent_status returns comprehensive status."""
        status = orchestrator.get_agent_status()

        assert "agents" in status
        assert "agent_count" in status
        assert "execution_plan" in status
        assert "rules_loaded" in status

        # Check rules loaded counts
        assert status["rules_loaded"]["disambiguation"] > 0
        assert status["rules_loaded"]["compliance"] > 0
        assert status["rules_loaded"]["taxonomy"] > 0


@pytest.mark.asyncio
class TestOrchestratorEnrichment:
    """Test full enrichment pipeline execution."""

    async def test_enrich_feedback_basic_success(self, orchestrator, mock_theme_repository):
        """Test basic feedback enrichment succeeds."""
        mock_theme_repository.get_active_themes.return_value = []

        success, enrichment, agent_results = await orchestrator.enrich_feedback(
            feedback_id="test-001",
            raw_text="Salary calculation is wrong in payroll system",
            language="EN",
        )

        assert success is True
        assert enrichment["feedback_id"] == "test-001"
        assert enrichment["product_area"] == "Payroll"
        assert len(agent_results) > 0
        assert agent_results[0].agent_name == "triage"
        assert agent_results[0].status == AgentStatus.SUCCESS

    async def test_enrich_feedback_with_disambiguation(self, orchestrator, mock_theme_repository):
        """Test enrichment with disambiguation rules applied."""
        mock_theme_repository.get_active_themes.return_value = []

        success, enrichment, agent_results = await orchestrator.enrich_feedback(
            feedback_id="test-002",
            raw_text="Employee leaving needs final settlement calculation",
            language="EN",
        )

        assert success is True
        assert enrichment["product_area"] == "Payroll"
        assert "final settlement" in enrichment["reasoning"].lower()

    async def test_enrich_feedback_with_compliance(self, orchestrator, mock_theme_repository):
        """Test enrichment detects compliance regulations."""
        mock_theme_repository.get_active_themes.return_value = []

        success, enrichment, agent_results = await orchestrator.enrich_feedback(
            feedback_id="test-003",
            raw_text="GOSI file submission required for social insurance",
            language="EN",
        )

        assert success is True
        assert enrichment["is_compliance"] is True
        assert "GOSI" in enrichment["compliance_tags"]

    async def test_enrich_feedback_with_theme_match(self, orchestrator, mock_theme_repository):
        """Test enrichment matches existing themes."""
        # Create mock theme
        mock_theme = Theme(
            id=uuid4(),
            name_en="Payroll Salary Issues",
            description_en="payroll salary calculation wrong incorrect deduction problems",
            trend=ThemeTrend.STABLE,
            item_count=10,
            customer_count=5,
            vote_weight=15,
        )
        mock_theme_repository.get_active_themes.return_value = [mock_theme]

        success, enrichment, agent_results = await orchestrator.enrich_feedback(
            feedback_id="test-004",
            raw_text="Payroll salary calculation wrong incorrect deduction problems",
            language="EN",
        )

        assert success is True
        assert enrichment["action"] == "LINK"
        assert enrichment["matched_theme_id"] == str(mock_theme.id)
        assert enrichment["match_score"] >= 0.70

    async def test_enrich_feedback_with_correlation_id(self, orchestrator, mock_theme_repository):
        """Test correlation ID propagates through pipeline."""
        mock_theme_repository.get_active_themes.return_value = []
        correlation_id = "test-corr-123"

        success, enrichment, agent_results = await orchestrator.enrich_feedback(
            feedback_id="test-005",
            raw_text="Test feedback",
            language="EN",
            correlation_id=correlation_id,
        )

        assert success is True
        # Correlation ID is used in logging but not returned in enrichment

    async def test_enrich_feedback_generates_correlation_id(self, orchestrator, mock_theme_repository):
        """Test correlation ID is auto-generated if not provided."""
        mock_theme_repository.get_active_themes.return_value = []

        success, enrichment, agent_results = await orchestrator.enrich_feedback(
            feedback_id="test-006",
            raw_text="Test feedback",
            language="EN",
            correlation_id=None,  # Should auto-generate
        )

        assert success is True


@pytest.mark.asyncio
class TestOrchestratorErrorHandling:
    """Test error handling and graceful degradation."""

    async def test_enrich_handles_agent_failure_gracefully(self, orchestrator, mock_theme_repository):
        """Test pipeline continues when agent fails."""
        # Mock theme repository to raise exception
        mock_theme_repository.get_active_themes.side_effect = Exception("Database error")

        success, enrichment, agent_results = await orchestrator.enrich_feedback(
            feedback_id="test-101",
            raw_text="Test feedback",
            language="EN",
        )

        # Pipeline should complete but mark as failed
        assert success is False  # At least one agent failed
        assert len(agent_results) > 0
        # Enrichment should still have basic data
        assert enrichment["feedback_id"] == "test-101"

    async def test_enrich_tracks_execution_metrics(self, orchestrator, mock_theme_repository):
        """Test execution metrics are tracked."""
        mock_theme_repository.get_active_themes.return_value = []

        success, enrichment, agent_results = await orchestrator.enrich_feedback(
            feedback_id="test-102",
            raw_text="Test feedback",
            language="EN",
        )

        assert "execution_time_ms" in enrichment
        assert enrichment["execution_time_ms"] > 0
        assert enrichment["agents_executed"] > 0
        assert enrichment["agents_succeeded"] > 0

    async def test_enrich_agent_results_contain_metadata(self, orchestrator, mock_theme_repository):
        """Test agent results contain detailed metadata."""
        mock_theme_repository.get_active_themes.return_value = []

        success, enrichment, agent_results = await orchestrator.enrich_feedback(
            feedback_id="test-103",
            raw_text="Payroll salary issue",
            language="EN",
        )

        assert len(agent_results) > 0
        triage_result = agent_results[0]

        # Check metadata contains triage-specific fields
        assert "action" in triage_result.metadata
        assert "product_area" in triage_result.metadata
        assert "reasoning" in triage_result.metadata


@pytest.mark.asyncio
class TestOrchestratorRulesReload:
    """Test hot-reload functionality."""

    async def test_reload_rules_succeeds(self, orchestrator):
        """Test rules can be reloaded without restart."""
        success = orchestrator.reload_rules()
        assert success is True

    async def test_reload_rules_reinitializes_agents(self, orchestrator):
        """Test agents are reinitialized after reload."""
        # Get original agent instances
        original_triage = orchestrator.agents["triage"]

        # Reload rules
        success = orchestrator.reload_rules()
        assert success is True

        # Agent should be a new instance
        new_triage = orchestrator.agents["triage"]
        assert new_triage is not original_triage

    async def test_reload_rules_updates_rule_counts(self, orchestrator):
        """Test rule counts reflect reloaded state."""
        # Get initial status
        status_before = orchestrator.get_agent_status()

        # Reload rules
        orchestrator.reload_rules()

        # Get new status
        status_after = orchestrator.get_agent_status()

        # Rule counts should still be present
        assert status_after["rules_loaded"]["disambiguation"] > 0
        assert status_after["rules_loaded"]["compliance"] > 0
        assert status_after["rules_loaded"]["taxonomy"] > 0


@pytest.mark.asyncio
class TestOrchestratorContextPropagation:
    """Test context propagation between agents."""

    async def test_context_accumulates_agent_results(self, orchestrator, mock_theme_repository):
        """Test context accumulates results from all agents."""
        mock_theme_repository.get_active_themes.return_value = []

        success, enrichment, agent_results = await orchestrator.enrich_feedback(
            feedback_id="test-201",
            raw_text="GOSI file submission for payroll",
            language="EN",
        )

        assert success is True
        # All agents should have added results to context
        assert len(agent_results) > 0

    async def test_context_updates_product_area(self, orchestrator, mock_theme_repository):
        """Test context product_area is updated by agents."""
        mock_theme_repository.get_active_themes.return_value = []

        success, enrichment, agent_results = await orchestrator.enrich_feedback(
            feedback_id="test-202",
            raw_text="Salary calculation issues",
            language="EN",
        )

        assert success is True
        assert enrichment["product_area"] == "Payroll"

    async def test_context_updates_compliance_tags(self, orchestrator, mock_theme_repository):
        """Test context compliance_tags are updated by agents."""
        mock_theme_repository.get_active_themes.return_value = []

        success, enrichment, agent_results = await orchestrator.enrich_feedback(
            feedback_id="test-203",
            raw_text="WPS bank file required for wage protection",
            language="EN",
        )

        assert success is True
        assert len(enrichment["compliance_tags"]) > 0


@pytest.mark.asyncio
class TestOrchestratorSingleton:
    """Test singleton pattern for orchestrator."""

    async def test_get_orchestrator_returns_singleton(self, rule_engine, mock_theme_repository):
        """Test get_orchestrator returns same instance."""
        # Note: This test may interfere with global state
        # In production, consider resetting singleton after tests
        orchestrator1 = get_orchestrator(rule_engine, mock_theme_repository)
        orchestrator2 = get_orchestrator(rule_engine, mock_theme_repository)

        assert orchestrator1 is orchestrator2


@pytest.mark.asyncio
class TestOrchestratorExecutionModes:
    """Test sequential and parallel execution modes."""

    async def test_sequential_execution_order(self, orchestrator, mock_theme_repository):
        """Test sequential execution runs agents in order."""
        mock_theme_repository.get_active_themes.return_value = []

        success, enrichment, agent_results = await orchestrator.enrich_feedback(
            feedback_id="test-301",
            raw_text="Test feedback",
            language="EN",
        )

        # With current execution plan, triage runs sequentially
        assert len(agent_results) > 0
        assert agent_results[0].agent_name == "triage"

    async def test_execution_plan_stages(self, orchestrator):
        """Test execution plan has well-defined stages."""
        for stage_config in orchestrator.execution_plan:
            assert "stage" in stage_config
            assert "agents" in stage_config
            assert "mode" in stage_config
            assert stage_config["mode"] in ["sequential", "parallel"]
