"""
Base agent classes and models for the VoC agent framework.

Provides:
- AgentStatus: Execution status enum
- AgentResult: Result model from agent execution
- AgentContext: Shared context passed through agent pipeline
- BaseAgent: Abstract base class with logging and error handling
"""

from __future__ import annotations
import logging
import time
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, List, Optional, TYPE_CHECKING
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from app.services.rule_engine import RuleEngine


class AgentStatus(str, Enum):
    """Agent execution status."""
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"  # Some rules applied, some failed


class AgentResult(BaseModel):
    """Result from a single agent execution."""
    agent_name: str
    status: AgentStatus
    tags_added: List[str] = Field(default_factory=list)
    confidence_scores: Dict[str, float] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    error_message: Optional[str] = None
    execution_time_ms: float = 0.0


class AgentContext(BaseModel):
    """
    Shared context passed through the agent pipeline.

    Each agent enriches this context with classification results.
    The context accumulates all agent results for traceability.
    """
    feedback_id: str
    raw_text: str
    language: str  # "AR", "EN", "Mixed"

    # Enrichment results (built up by agents)
    product_area: Optional[str] = None  # L1 scope from taxonomy
    compliance_tags: List[str] = Field(default_factory=list)
    cross_tags: List[str] = Field(default_factory=list)  # Multi-label tags
    severity: Optional[str] = None  # "Blocker", "Warning", "Info"

    # Agent execution history
    agent_results: List[AgentResult] = Field(default_factory=list)
    correlation_id: Optional[str] = None

    # Allow arbitrary fields for future extensibility
    model_config = {"extra": "allow"}


class BaseAgent(ABC):
    """
    Abstract base class for all agents.

    Provides:
    - Structured logging with correlation IDs
    - Automatic timing and error handling
    - Access to shared rule engine

    Subclasses must implement the execute() method.
    """

    def __init__(self, name: str, rule_engine: RuleEngine):
        """
        Initialize agent.

        Args:
            name: Agent name for logging
            rule_engine: Shared rule engine instance
        """
        self.name = name
        self.rule_engine = rule_engine
        self.logger = logging.getLogger(f"agent.{name}")

    @abstractmethod
    async def execute(self, context: AgentContext) -> AgentResult:
        """
        Execute agent logic. Must be implemented by subclasses.

        Args:
            context: Shared agent context with feedback data

        Returns:
            AgentResult with classification results
        """
        pass

    async def execute_with_logging(self, context: AgentContext) -> AgentResult:
        """
        Execute agent with timing and error handling.

        This wrapper should always be used instead of calling execute() directly.
        It ensures consistent logging, timing, and error handling across all agents.

        Args:
            context: Shared agent context

        Returns:
            AgentResult with execution metadata
        """
        start_time = time.time()

        self.logger.info(
            f"Agent {self.name} started",
            extra={
                "correlation_id": context.correlation_id,
                "feedback_id": context.feedback_id,
                "agent": self.name,
            }
        )

        try:
            result = await self.execute(context)
            result.execution_time_ms = (time.time() - start_time) * 1000

            self.logger.info(
                f"Agent {self.name} completed",
                extra={
                    "correlation_id": context.correlation_id,
                    "feedback_id": context.feedback_id,
                    "agent": self.name,
                    "status": result.status,
                    "execution_time_ms": result.execution_time_ms,
                    "tags_added": len(result.tags_added),
                }
            )
            return result

        except Exception as e:
            execution_time_ms = (time.time() - start_time) * 1000
            self.logger.error(
                f"Agent {self.name} failed",
                extra={
                    "correlation_id": context.correlation_id,
                    "feedback_id": context.feedback_id,
                    "agent": self.name,
                    "error": str(e),
                },
                exc_info=True
            )
            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.FAILED,
                error_message=str(e),
                execution_time_ms=execution_time_ms
            )
