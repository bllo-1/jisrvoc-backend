"""
Agent foundation layer for VoC feedback classification.

This module provides base classes and infrastructure for building
classification agents that enrich feedback items with metadata.
"""

from .base import (
    AgentStatus,
    AgentResult,
    AgentContext,
    BaseAgent,
)
from .disambiguation_agent import DisambiguationAgent
from .compliance_agent import ComplianceAgent
from .scope_classifier_agent import ScopeClassifierAgent
from .triage_agent import TriageAgent

__all__ = [
    "AgentStatus",
    "AgentResult",
    "AgentContext",
    "BaseAgent",
    "DisambiguationAgent",
    "ComplianceAgent",
    "ScopeClassifierAgent",
    "TriageAgent",
]
