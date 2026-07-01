"""
Agent Orchestrator - manages agent execution pipeline.

The orchestrator coordinates multiple agents to enrich feedback items.
It handles:
- Agent initialization and lifecycle
- Sequential/parallel execution based on dependencies
- Error handling and graceful degradation
- Hot-reloading of YAML rules
- Correlation ID propagation for observability
"""

import logging
import time
import asyncio
from typing import Dict, List, Optional, Tuple, Any
from uuid import uuid4

from app.agents.base import BaseAgent, AgentContext, AgentResult, AgentStatus
from app.agents.triage_agent import TriageAgent
from app.services.rule_engine import RuleEngine, get_rule_engine
from app.repositories.theme import ThemeRepository


logger = logging.getLogger("orchestrator")


class AgentOrchestrator:
    """
    Orchestrates agent execution pipeline for feedback enrichment.

    Manages agent lifecycle, execution order, error handling,
    and result aggregation.
    """

    def __init__(
        self,
        rule_engine: Optional[RuleEngine] = None,
        theme_repository: Optional[ThemeRepository] = None,
    ):
        """
        Initialize orchestrator and all agents.

        Args:
            rule_engine: Shared rule engine (defaults to singleton)
            theme_repository: Theme repository for triage agent
        """
        self.rule_engine = rule_engine or get_rule_engine()
        self.theme_repository = theme_repository

        # Initialize agents
        self.agents: Dict[str, BaseAgent] = {}
        self._initialize_agents()

        # Define execution plan (stages with dependencies)
        # Stage 0: Always runs first
        # Stage 1: Depends on Stage 0, etc.
        self.execution_plan = [
            {
                "stage": 0,
                "agents": ["triage"],
                "mode": "sequential",  # or "parallel"
                "description": "Main triage classification"
            },
            # Future stages for additional agents:
            # {
            #     "stage": 1,
            #     "agents": ["llm_enrichment", "embedding_generator"],
            #     "mode": "parallel",
            #     "description": "AI enrichment"
            # },
        ]

        logger.info(
            f"Agent orchestrator initialized with {len(self.agents)} agents",
            extra={"agents": list(self.agents.keys())}
        )

    def _initialize_agents(self):
        """Initialize all agents and register them."""
        # Triage agent (rule-based classification + theme matching)
        self.agents["triage"] = TriageAgent(
            rule_engine=self.rule_engine,
            theme_repository=self.theme_repository
        )

        # Future agents will be added here:
        # self.agents["llm_enrichment"] = LLMEnrichmentAgent(...)
        # self.agents["embedding"] = EmbeddingAgent(...)

    async def enrich_feedback(
        self,
        feedback_id: str,
        raw_text: str,
        language: str = "EN",
        correlation_id: Optional[str] = None,
    ) -> Tuple[bool, Dict[str, Any], List[AgentResult]]:
        """
        Execute full enrichment pipeline for a feedback item.

        Args:
            feedback_id: Feedback item ID
            raw_text: Raw feedback text
            language: Language code (EN, AR, Mixed)
            correlation_id: Optional correlation ID for tracing

        Returns:
            Tuple of (success, enrichment_data, agent_results)
            - success: True if pipeline completed without critical failures
            - enrichment_data: Dict with product_area, compliance, action, etc.
            - agent_results: List of AgentResult objects from all agents
        """
        start_time = time.time()

        # Generate correlation ID if not provided
        if correlation_id is None:
            correlation_id = f"enrich-{uuid4()}"

        logger.info(
            f"Starting enrichment pipeline for feedback {feedback_id}",
            extra={
                "correlation_id": correlation_id,
                "feedback_id": feedback_id,
                "language": language,
            }
        )

        # Create shared agent context
        context = AgentContext(
            feedback_id=feedback_id,
            raw_text=raw_text,
            language=language,
            correlation_id=correlation_id,
        )

        # Execute all stages
        all_results: List[AgentResult] = []
        pipeline_success = True

        for stage_config in self.execution_plan:
            stage_num = stage_config["stage"]
            agent_names = stage_config["agents"]
            mode = stage_config["mode"]
            description = stage_config["description"]

            logger.info(
                f"Executing stage {stage_num}: {description}",
                extra={
                    "correlation_id": correlation_id,
                    "stage": stage_num,
                    "agents": agent_names,
                    "mode": mode,
                }
            )

            # Execute agents in this stage
            if mode == "sequential":
                stage_results = await self._execute_sequential(context, agent_names)
            elif mode == "parallel":
                stage_results = await self._execute_parallel(context, agent_names)
            else:
                logger.error(f"Unknown execution mode: {mode}")
                stage_results = []

            # Aggregate results
            all_results.extend(stage_results)

            # Check for critical failures
            failed_agents = [r for r in stage_results if r.status == AgentStatus.FAILED]
            if failed_agents:
                logger.warning(
                    f"Stage {stage_num} had {len(failed_agents)} failed agents",
                    extra={
                        "correlation_id": correlation_id,
                        "failed_agents": [r.agent_name for r in failed_agents],
                    }
                )
                # Continue pipeline but mark as degraded
                pipeline_success = False

        # Build enrichment data from context and results
        enrichment_data = self._build_enrichment_data(context, all_results)

        execution_time_ms = (time.time() - start_time) * 1000

        logger.info(
            f"Enrichment pipeline completed for feedback {feedback_id}",
            extra={
                "correlation_id": correlation_id,
                "success": pipeline_success,
                "execution_time_ms": execution_time_ms,
                "agents_executed": len(all_results),
            }
        )

        enrichment_data["execution_time_ms"] = execution_time_ms

        return pipeline_success, enrichment_data, all_results

    async def _execute_sequential(
        self,
        context: AgentContext,
        agent_names: List[str],
    ) -> List[AgentResult]:
        """
        Execute agents sequentially (one after another).

        Args:
            context: Shared agent context
            agent_names: List of agent names to execute

        Returns:
            List of agent results
        """
        results = []

        for agent_name in agent_names:
            agent = self.agents.get(agent_name)
            if not agent:
                logger.error(
                    f"Agent '{agent_name}' not found",
                    extra={"correlation_id": context.correlation_id}
                )
                continue

            # Execute agent with logging
            result = await agent.execute_with_logging(context)
            results.append(result)

            # Update context with result
            context.agent_results.append(result)

        return results

    async def _execute_parallel(
        self,
        context: AgentContext,
        agent_names: List[str],
    ) -> List[AgentResult]:
        """
        Execute agents in parallel using asyncio.gather().

        Args:
            context: Shared agent context
            agent_names: List of agent names to execute

        Returns:
            List of agent results
        """
        # Get agents
        agents = []
        for agent_name in agent_names:
            agent = self.agents.get(agent_name)
            if agent:
                agents.append((agent_name, agent))
            else:
                logger.error(
                    f"Agent '{agent_name}' not found",
                    extra={"correlation_id": context.correlation_id}
                )

        if not agents:
            return []

        # Execute all agents concurrently
        tasks = [agent.execute_with_logging(context) for _, agent in agents]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Handle exceptions
        final_results = []
        for (agent_name, agent), result in zip(agents, results):
            if isinstance(result, Exception):
                logger.error(
                    f"Agent '{agent_name}' raised exception",
                    extra={"correlation_id": context.correlation_id, "error": str(result)},
                    exc_info=result
                )
                # Create failed result
                result = AgentResult(
                    agent_name=agent_name,
                    status=AgentStatus.FAILED,
                    error_message=str(result),
                    execution_time_ms=0.0,
                )

            final_results.append(result)
            context.agent_results.append(result)

        return final_results

    def _build_enrichment_data(
        self,
        context: AgentContext,
        agent_results: List[AgentResult],
    ) -> Dict[str, Any]:
        """
        Build enrichment data dictionary from context and agent results.

        Args:
            context: Final agent context
            agent_results: All agent results

        Returns:
            Dictionary with enrichment data
        """
        enrichment = {
            "feedback_id": context.feedback_id,
            "product_area": context.product_area,
            "compliance_tags": context.compliance_tags,
            "cross_tags": context.cross_tags,
            "severity": context.severity,
            "is_compliance": len(context.compliance_tags) > 0,
        }

        # Extract triage-specific data
        triage_result = next(
            (r for r in agent_results if r.agent_name == "triage"),
            None
        )

        if triage_result and triage_result.metadata:
            enrichment.update({
                "action": triage_result.metadata.get("action"),
                "matched_theme_id": triage_result.metadata.get("matched_theme_id"),
                "matched_theme_name": triage_result.metadata.get("matched_theme_name"),
                "match_score": triage_result.metadata.get("match_score"),
                "area_confidence": triage_result.metadata.get("area_confidence"),
                "reasoning": triage_result.metadata.get("reasoning"),
            })

        # Agent execution summary
        enrichment["agents_executed"] = len(agent_results)
        enrichment["agents_succeeded"] = sum(
            1 for r in agent_results if r.status == AgentStatus.SUCCESS
        )
        enrichment["agents_failed"] = sum(
            1 for r in agent_results if r.status == AgentStatus.FAILED
        )

        return enrichment

    def reload_rules(self):
        """
        Hot-reload all YAML rules without restarting the application.

        This allows PMs to update rules and test immediately.
        """
        logger.info("Hot-reloading all agent rules")

        try:
            # Reload rule engine
            self.rule_engine.reload()

            # Reinitialize agents with updated rules
            self._initialize_agents()

            logger.info("Rules reloaded successfully")
            return True

        except Exception as e:
            logger.error(f"Error reloading rules: {e}", exc_info=True)
            return False

    def get_agent_status(self) -> Dict[str, Any]:
        """
        Get status of all agents for health checks.

        Returns:
            Dictionary with agent status
        """
        return {
            "agents": list(self.agents.keys()),
            "agent_count": len(self.agents),
            "execution_plan": self.execution_plan,
            "rules_loaded": {
                "disambiguation": len(self.rule_engine.disambiguation_rules.get("rules", [])),
                "compliance": len(self.rule_engine.compliance_lexicon.get("regulations", [])),
                "taxonomy": len(self.rule_engine.taxonomy.get("scopes", [])),
            },
        }


# Singleton instance
_orchestrator_instance: Optional[AgentOrchestrator] = None


def get_orchestrator(
    rule_engine: Optional[RuleEngine] = None,
    theme_repository: Optional[ThemeRepository] = None,
) -> AgentOrchestrator:
    """
    Get or create singleton orchestrator instance.

    Args:
        rule_engine: Optional rule engine instance
        theme_repository: Optional theme repository

    Returns:
        AgentOrchestrator instance
    """
    global _orchestrator_instance

    if _orchestrator_instance is None:
        _orchestrator_instance = AgentOrchestrator(
            rule_engine=rule_engine,
            theme_repository=theme_repository
        )

    return _orchestrator_instance
