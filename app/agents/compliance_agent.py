"""
Compliance Detection Agent - applies Section 3 compliance lexicon.

This agent detects regulatory/compliance terms in feedback.
Any match triggers highest Business Impact classification regardless of tier or frequency.
"""

from typing import List
from app.agents.base import BaseAgent, AgentContext, AgentResult, AgentStatus
from app.services.rule_engine import RuleEngine


class ComplianceAgent(BaseAgent):
    """
    Agent that detects compliance and regulatory terms.

    Compliance matches override all other classification - they are
    automatically the highest Business Impact level.
    """

    def __init__(self, rule_engine: RuleEngine):
        super().__init__(name="compliance", rule_engine=rule_engine)

    async def execute(self, context: AgentContext) -> AgentResult:
        """
        Detect compliance/regulatory terms in feedback.

        Args:
            context: Shared agent context

        Returns:
            AgentResult with compliance tags
        """
        matches = self.rule_engine.detect_compliance_terms(
            text=context.raw_text,
            language=context.language
        )

        tags_added = []
        confidence_scores = {}
        metadata = {
            "matches": [],
            "is_compliance": False,
            "regulations": [],
        }

        if matches:
            # Mark as compliance issue
            metadata["is_compliance"] = True

            # Add compliance tag if not already present
            compliance_tag = "Compliance"
            if compliance_tag not in context.compliance_tags:
                context.compliance_tags.append(compliance_tag)
                tags_added.append(f"compliance:{compliance_tag}")

            # Track all matched regulations
            for match in matches:
                regulation = match.get("regulation")
                country = match.get("country")
                matched_terms = match.get("matched_terms", [])
                confidence = match.get("confidence", "High")

                metadata["regulations"].append({
                    "name": regulation,
                    "country": country,
                    "matched_terms": matched_terms,
                    "term_count": len(matched_terms),
                })

                # Add regulation-specific tag
                if regulation not in context.compliance_tags:
                    context.compliance_tags.append(regulation)
                    tags_added.append(f"regulation:{regulation}")

                # Set confidence score (High=1.0, Medium=0.7)
                conf_value = 1.0 if confidence == "High" else 0.7
                confidence_scores[regulation] = conf_value

                self.logger.info(
                    f"Compliance match: {regulation} ({country}) - {len(matched_terms)} terms",
                    extra={
                        "correlation_id": context.correlation_id,
                        "feedback_id": context.feedback_id,
                        "regulation": regulation,
                        "terms": matched_terms,
                    }
                )

            metadata["matches"] = matches
            status = AgentStatus.SUCCESS

        else:
            # No compliance matches - still success
            status = AgentStatus.SUCCESS
            self.logger.debug(
                "No compliance terms detected",
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
