"""
Disambiguation Agent - applies Section 2 disambiguation rules.

This agent resolves confusable terms like "Settlement", "Approval", "Integration"
by examining surrounding context (noun before term, workflow described).
"""

from typing import List
from app.agents.base import BaseAgent, AgentContext, AgentResult, AgentStatus
from app.services.rule_engine import RuleEngine


class DisambiguationAgent(BaseAgent):
    """
    Agent that applies disambiguation rules to resolve ambiguous terms.

    Uses context patterns to distinguish between different meanings of
    the same term (e.g., "Final Settlement" vs "Vacation Settlement").
    """

    def __init__(self, rule_engine: RuleEngine):
        super().__init__(name="disambiguation", rule_engine=rule_engine)

    async def execute(self, context: AgentContext) -> AgentResult:
        """
        Apply disambiguation rules to the feedback text.

        Args:
            context: Shared agent context

        Returns:
            AgentResult with disambiguation tags
        """
        matches = self.rule_engine.apply_disambiguation_rules(
            text=context.raw_text,
            language=context.language
        )

        tags_added = []
        confidence_scores = {}
        metadata = {"matches": []}

        for match in matches:
            scope = match.get("scope")
            variant = match.get("variant")
            confidence = match.get("confidence", 1.0)

            # Set primary product area if not already set
            if scope and not context.product_area:
                context.product_area = scope
                tags_added.append(f"scope:{scope}")
                confidence_scores[scope] = confidence

            # Add cross-tag if specified
            cross_tag = match.get("cross_tag")
            if cross_tag and cross_tag not in context.cross_tags:
                context.cross_tags.append(cross_tag)
                tags_added.append(f"cross_tag:{cross_tag}")

            # Track match metadata
            metadata["matches"].append({
                "term": match.get("term"),
                "variant": variant,
                "scope": scope,
                "confidence": confidence,
            })

            self.logger.debug(
                f"Disambiguation match: {match.get('term')} -> {variant} ({scope})",
                extra={
                    "correlation_id": context.correlation_id,
                    "feedback_id": context.feedback_id,
                }
            )

        # Determine status
        if matches:
            status = AgentStatus.SUCCESS
        else:
            status = AgentStatus.SUCCESS  # No matches is not a failure
            self.logger.debug(
                "No disambiguation matches found",
                extra={
                    "correlation_id": context.correlation_id,
                    "feedback_id": context.feedback_id,
                }
            )

        return AgentResult(
            agent_name=self.name,
            status=status,
            tags_added=tags_added,
            confidence_scores=confidence_scores,
            metadata=metadata,
        )
