"""
Scope Classifier Agent - applies Section 1 L1 taxonomy.

This agent classifies feedback into one of 13 product areas (L1 scopes)
by matching keywords and mental model terms from the taxonomy.
"""

from typing import List
from app.agents.base import BaseAgent, AgentContext, AgentResult, AgentStatus
from app.services.rule_engine import RuleEngine


class ScopeClassifierAgent(BaseAgent):
    """
    Agent that classifies feedback into L1 product scopes.

    Uses keyword matching and scoring to determine the most relevant
    product area. Falls back to "Other / Unclassified" if no strong match.
    """

    def __init__(self, rule_engine: RuleEngine, min_score_threshold: int = 1):
        """
        Initialize scope classifier agent.

        Args:
            rule_engine: Shared rule engine
            min_score_threshold: Minimum keyword match score to assign scope
        """
        super().__init__(name="scope_classifier", rule_engine=rule_engine)
        self.min_score_threshold = min_score_threshold

    async def execute(self, context: AgentContext) -> AgentResult:
        """
        Classify feedback into L1 product scope.

        Args:
            context: Shared agent context

        Returns:
            AgentResult with scope classification
        """
        matches = self.rule_engine.match_scope_keywords(
            text=context.raw_text,
            language=context.language
        )

        tags_added = []
        confidence_scores = {}
        metadata = {
            "matches": [],
            "top_scope": None,
            "score": 0,
        }

        if matches:
            # Get top match
            top_match = matches[0]
            scope = top_match.get("scope")
            score = top_match.get("score", 0)

            # Only assign if score meets threshold
            if score >= self.min_score_threshold:
                # Set product area if not already set by disambiguation agent
                if not context.product_area:
                    context.product_area = scope
                    tags_added.append(f"scope:{scope}")
                    confidence_scores[scope] = min(score / 5.0, 1.0)  # Normalize to 0-1

                    self.logger.info(
                        f"Scope classified: {scope} (score={score})",
                        extra={
                            "correlation_id": context.correlation_id,
                            "feedback_id": context.feedback_id,
                            "scope": scope,
                            "score": score,
                        }
                    )
                else:
                    self.logger.debug(
                        f"Scope already set to {context.product_area}, skipping classification",
                        extra={
                            "correlation_id": context.correlation_id,
                            "feedback_id": context.feedback_id,
                        }
                    )

                metadata["top_scope"] = scope
                metadata["score"] = score

            # Track all matches for analysis
            metadata["matches"] = [
                {
                    "scope": m.get("scope"),
                    "score": m.get("score"),
                    "matched_keywords": m.get("matched_keywords", []),
                    "matched_mental_model": m.get("matched_mental_model", []),
                }
                for m in matches[:5]  # Top 5 matches
            ]

            status = AgentStatus.SUCCESS

        else:
            # No matches - assign "Other / Unclassified"
            if not context.product_area:
                context.product_area = "Other / Unclassified"
                tags_added.append("scope:Other / Unclassified")
                confidence_scores["Other / Unclassified"] = 0.1  # Low confidence

                self.logger.info(
                    "No scope matches, assigned to Other / Unclassified",
                    extra={
                        "correlation_id": context.correlation_id,
                        "feedback_id": context.feedback_id,
                    }
                )

            metadata["top_scope"] = "Other / Unclassified"
            metadata["score"] = 0
            status = AgentStatus.SUCCESS

        return AgentResult(
            agent_name=self.name,
            status=status,
            tags_added=tags_added,
            confidence_scores=confidence_scores,
            metadata=metadata,
        )
