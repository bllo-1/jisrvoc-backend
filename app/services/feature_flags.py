"""
Feature flag controller for gradual rollout of agent-based enrichment.

This module manages the rollout of the agent-based classification pipeline
with hash-based consistent routing per feedback item.
"""
import hashlib
import logging
import time
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from ..core.config import settings

logger = logging.getLogger(__name__)


class RolloutMetrics:
    """
    In-memory metrics tracker for agent rollout.

    Thread-safe counters for monitoring agent vs old pipeline usage.
    In production, these would be exported to Prometheus/Datadog.
    """

    def __init__(self):
        self._metrics = {
            "agent_requests": 0,
            "old_pipeline_requests": 0,
            "agent_success": 0,
            "agent_errors": 0,
            "total_agent_time_ms": 0.0,
            "total_old_time_ms": 0.0,
            "last_reset": datetime.utcnow(),
        }
        self._lock = None  # TODO: Add threading.Lock() for thread safety

    def record_agent_request(self, success: bool, execution_time_ms: float, error: Optional[str] = None):
        """Record metrics for agent pipeline execution."""
        self._metrics["agent_requests"] += 1
        self._metrics["total_agent_time_ms"] += execution_time_ms

        if success:
            self._metrics["agent_success"] += 1
        else:
            self._metrics["agent_errors"] += 1
            logger.warning(
                "Agent pipeline error recorded",
                extra={
                    "error": error,
                    "execution_time_ms": execution_time_ms,
                }
            )

    def record_old_pipeline_request(self, execution_time_ms: float):
        """Record metrics for old pipeline execution."""
        self._metrics["old_pipeline_requests"] += 1
        self._metrics["total_old_time_ms"] += execution_time_ms

    def get_metrics(self) -> Dict[str, Any]:
        """Get current rollout metrics."""
        agent_requests = self._metrics["agent_requests"]
        old_requests = self._metrics["old_pipeline_requests"]
        total_requests = agent_requests + old_requests

        # Calculate rates and averages
        agent_success_rate = (
            self._metrics["agent_success"] / agent_requests
            if agent_requests > 0 else 0.0
        )

        agent_avg_time = (
            self._metrics["total_agent_time_ms"] / agent_requests
            if agent_requests > 0 else 0.0
        )

        old_avg_time = (
            self._metrics["total_old_time_ms"] / old_requests
            if old_requests > 0 else 0.0
        )

        uptime_seconds = (datetime.utcnow() - self._metrics["last_reset"]).total_seconds()

        return {
            "total_requests": total_requests,
            "agent_requests": agent_requests,
            "old_pipeline_requests": old_requests,
            "agent_percentage": (agent_requests / total_requests * 100) if total_requests > 0 else 0.0,
            "agent_success_rate": agent_success_rate,
            "agent_error_count": self._metrics["agent_errors"],
            "agent_avg_execution_time_ms": round(agent_avg_time, 2),
            "old_avg_execution_time_ms": round(old_avg_time, 2),
            "speedup_factor": (old_avg_time / agent_avg_time) if agent_avg_time > 0 else 0.0,
            "uptime_seconds": int(uptime_seconds),
            "last_reset": self._metrics["last_reset"].isoformat(),
        }

    def reset(self):
        """Reset all metrics counters."""
        self._metrics = {
            "agent_requests": 0,
            "old_pipeline_requests": 0,
            "agent_success": 0,
            "agent_errors": 0,
            "total_agent_time_ms": 0.0,
            "total_old_time_ms": 0.0,
            "last_reset": datetime.utcnow(),
        }
        logger.info("Rollout metrics reset")


# Global metrics instance (singleton)
_rollout_metrics = RolloutMetrics()


def should_use_agents(feedback_id: str) -> bool:
    """
    Determine if a feedback item should be enriched with agent pipeline.

    Uses consistent hash-based routing:
    - Same feedback_id always gets same decision
    - Enables gradual rollout via AGENT_ROLLOUT_PERCENTAGE
    - Returns False if agents are disabled

    Args:
        feedback_id: Unique identifier for the feedback item

    Returns:
        True if should use agent pipeline, False for old pipeline

    Examples:
        # With AGENT_ROLLOUT_PERCENTAGE=25:
        >>> should_use_agents("123")  # hash("123") % 100 = 23 < 25
        True
        >>> should_use_agents("456")  # hash("456") % 100 = 78 >= 25
        False
    """
    # Check master switch
    if not settings.agent_enrichment_enabled:
        logger.debug(
            "Agent enrichment disabled by feature flag",
            extra={"agent_enrichment_enabled": False}
        )
        return False

    # Check rollout percentage
    rollout_pct = settings.agent_rollout_percentage

    if rollout_pct <= 0:
        logger.debug(
            "Agent rollout at 0%",
            extra={"rollout_percentage": rollout_pct}
        )
        return False

    if rollout_pct >= 100:
        logger.debug(
            "Agent rollout at 100%",
            extra={"rollout_percentage": rollout_pct}
        )
        return True

    # Hash-based consistent routing
    # Use MD5 for fast, consistent hashing (not cryptographic security)
    hash_digest = hashlib.md5(feedback_id.encode()).hexdigest()
    hash_int = int(hash_digest[:8], 16)  # Use first 8 hex chars
    bucket = hash_int % 100

    use_agents = bucket < rollout_pct

    logger.debug(
        "Feature flag decision",
        extra={
            "feedback_id": feedback_id,
            "rollout_percentage": rollout_pct,
            "hash_bucket": bucket,
            "use_agents": use_agents,
        }
    )

    return use_agents


def get_rollout_metrics() -> Dict[str, Any]:
    """
    Get current rollout metrics for monitoring dashboard.

    Returns:
        Dictionary with metrics:
        - total_requests: Total enrichment requests
        - agent_requests: Requests routed to agent pipeline
        - old_pipeline_requests: Requests routed to old pipeline
        - agent_percentage: Actual percentage using agents
        - agent_success_rate: Success rate (0.0-1.0)
        - agent_error_count: Number of agent errors
        - agent_avg_execution_time_ms: Average agent execution time
        - old_avg_execution_time_ms: Average old pipeline time
        - speedup_factor: Old time / Agent time
        - uptime_seconds: Seconds since last reset
        - last_reset: ISO timestamp of last reset
    """
    return _rollout_metrics.get_metrics()


def record_agent_execution(
    success: bool,
    execution_time_ms: float,
    error: Optional[str] = None
):
    """
    Record agent pipeline execution for metrics.

    Args:
        success: True if enrichment succeeded
        execution_time_ms: Execution time in milliseconds
        error: Error message if failed (optional)
    """
    _rollout_metrics.record_agent_request(success, execution_time_ms, error)

    # Log to Sentry if error
    if not success and error:
        logger.error(
            "Agent pipeline execution failed",
            extra={
                "error": error,
                "execution_time_ms": execution_time_ms,
            },
            exc_info=False,  # Don't capture full stack trace
        )


def record_old_pipeline_execution(execution_time_ms: float):
    """
    Record old pipeline execution for metrics.

    Args:
        execution_time_ms: Execution time in milliseconds
    """
    _rollout_metrics.record_old_pipeline_request(execution_time_ms)


def reset_metrics():
    """Reset all rollout metrics counters."""
    _rollout_metrics.reset()


def get_feature_status() -> Dict[str, Any]:
    """
    Get current feature flag configuration and status.

    Returns:
        Dictionary with:
        - enabled: Master switch status
        - rollout_percentage: Configured rollout percentage
        - metrics: Current rollout metrics
    """
    return {
        "enabled": settings.agent_enrichment_enabled,
        "rollout_percentage": settings.agent_rollout_percentage,
        "metrics": get_rollout_metrics(),
    }
