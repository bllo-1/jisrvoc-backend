"""
Triage Agent - orchestrates full feedback classification and theme matching.

This agent is the main entry point for feedback triage. It:
1. Applies disambiguation rules to resolve ambiguous terms
2. Detects compliance/regulatory terms
3. Determines product area (L1 scope) with confidence
4. Matches against existing themes using keyword overlap
5. Decides LINK vs CREATE action based on similarity threshold
6. Builds human-readable reasoning for the decision
"""

import logging
import re
from typing import Dict, List, Optional, Set, Tuple
import yaml
from pathlib import Path

from app.agents.base import BaseAgent, AgentContext, AgentResult, AgentStatus
from app.services.rule_engine import RuleEngine
from app.repositories.theme import ThemeRepository
from app.models.theme import Theme


logger = logging.getLogger("triage_agent")


class TriageAgent(BaseAgent):
    """
    Main triage agent that orchestrates feedback classification and theme matching.

    Uses rule-based disambiguation, compliance detection, and keyword-based
    theme matching to decide whether to LINK feedback to existing theme or
    CREATE a new theme.
    """

    def __init__(
        self,
        rule_engine: RuleEngine,
        theme_repository: Optional[ThemeRepository] = None,
        config_path: Optional[Path] = None,
    ):
        """
        Initialize triage agent.

        Args:
            rule_engine: Shared rule engine instance
            theme_repository: Repository for theme queries (optional for testing)
            config_path: Path to agent config YAML (defaults to app/config/agents/triage_agent.yaml)
        """
        super().__init__(name="triage", rule_engine=rule_engine)
        self.theme_repository = theme_repository

        # Load agent configuration
        if config_path is None:
            config_path = Path(__file__).parent.parent / "config" / "agents" / "triage_agent.yaml"

        self.config = self._load_config(config_path)

    def _load_config(self, config_path: Path) -> Dict:
        """Load agent configuration from YAML."""
        try:
            if config_path.exists():
                with open(config_path, "r", encoding="utf-8") as f:
                    config = yaml.safe_load(f) or {}
                self.logger.info(f"Loaded triage agent config from {config_path}")
                return config
            else:
                self.logger.warning(f"Config not found: {config_path}, using defaults")
                return {}
        except Exception as e:
            self.logger.error(f"Error loading config: {e}", exc_info=True)
            return {}

    async def execute(self, context: AgentContext) -> AgentResult:
        """
        Execute full triage logic.

        Args:
            context: Shared agent context with feedback data

        Returns:
            AgentResult with triage decision and reasoning
        """
        # Step 1: Apply disambiguation rules
        disambiguation_signals = self._apply_disambiguation(context)

        # Step 2: Detect compliance terms
        compliance_signals = self._detect_compliance(context)

        # Step 3: Determine product area with confidence
        product_area, area_confidence, area_reasoning = self._determine_product_area(
            context, disambiguation_signals, compliance_signals
        )

        # Step 4: Match against existing themes (if repository available)
        matched_theme = None
        match_score = 0.0
        match_reasoning = ""

        if self.theme_repository:
            matched_theme, match_score, match_reasoning = await self._match_theme(
                context, product_area
            )

        # Step 5: Decide LINK vs CREATE action
        action, action_reasoning = self._decide_action(
            matched_theme, match_score
        )

        # Step 6: Build full reasoning
        reasoning = self._build_reasoning(
            disambiguation_signals=disambiguation_signals,
            compliance_signals=compliance_signals,
            product_area=product_area,
            area_confidence=area_confidence,
            area_reasoning=area_reasoning,
            match_score=match_score,
            match_reasoning=match_reasoning,
            action=action,
            action_reasoning=action_reasoning,
        )

        # Build result metadata
        metadata = {
            "product_area": product_area,
            "area_confidence": area_confidence,
            "is_compliance": len(compliance_signals) > 0,
            "compliance_regulations": [s["regulation"] for s in compliance_signals],
            "disambiguation_matches": len(disambiguation_signals),
            "action": action,
            "matched_theme_id": str(matched_theme.id) if matched_theme else None,
            "matched_theme_name": matched_theme.name_en if matched_theme else None,
            "match_score": match_score,
            "reasoning": reasoning,
        }

        # Update context
        context.product_area = product_area
        if compliance_signals:
            context.compliance_tags = [s["regulation"] for s in compliance_signals]

        return AgentResult(
            agent_name=self.name,
            status=AgentStatus.SUCCESS,
            tags_added=[f"action:{action}", f"scope:{product_area}"],
            confidence_scores={"product_area": area_confidence, "theme_match": match_score},
            metadata=metadata,
        )

    def _apply_disambiguation(self, context: AgentContext) -> List[Dict]:
        """
        Apply disambiguation rules to resolve ambiguous terms.

        Args:
            context: Agent context with feedback text

        Returns:
            List of disambiguation matches
        """
        matches = self.rule_engine.apply_disambiguation_rules(
            text=context.raw_text,
            language=context.language
        )

        if matches:
            self.logger.debug(
                f"Disambiguation found {len(matches)} matches",
                extra={"correlation_id": context.correlation_id}
            )

        return matches

    def _detect_compliance(self, context: AgentContext) -> List[Dict]:
        """
        Detect compliance/regulatory terms.

        Args:
            context: Agent context with feedback text

        Returns:
            List of compliance matches
        """
        matches = self.rule_engine.detect_compliance_terms(
            text=context.raw_text,
            language=context.language
        )

        if matches:
            self.logger.info(
                f"Compliance detected: {len(matches)} regulations",
                extra={"correlation_id": context.correlation_id}
            )

        return matches

    def _determine_product_area(
        self,
        context: AgentContext,
        disambiguation_signals: List[Dict],
        compliance_signals: List[Dict],
    ) -> Tuple[str, float, str]:
        """
        Determine product area (L1 scope) with confidence score.

        Priority:
        1. Disambiguation signals (highest confidence)
        2. Scope keyword matching
        3. Fallback to "Other / Unclassified"

        Args:
            context: Agent context
            disambiguation_signals: Disambiguation matches
            compliance_signals: Compliance matches

        Returns:
            Tuple of (product_area, confidence, reasoning)
        """
        # Priority 1: Use disambiguation signal if available
        if disambiguation_signals:
            # Take first match (highest priority in YAML)
            first_match = disambiguation_signals[0]
            scope = first_match.get("scope")
            if scope:
                confidence = first_match.get("confidence", 1.0)
                reasoning = f"Disambiguated '{first_match['term']}' to {first_match['variant']}"
                return scope, confidence, reasoning

        # Priority 2: Use scope keyword matching
        scope_matches = self.rule_engine.match_scope_keywords(
            text=context.raw_text,
            language=context.language
        )

        if scope_matches:
            top_match = scope_matches[0]
            scope = top_match["scope"]
            score = top_match["score"]
            # Normalize score to 0-1 range (cap at 5 keywords = 1.0)
            confidence = min(score / 5.0, 1.0)
            reasoning = f"Matched {score} keywords for {scope}"
            return scope, confidence, reasoning

        # Priority 3: Fallback
        return "Other / Unclassified", 0.1, "No scope keywords matched"

    async def _match_theme(
        self,
        context: AgentContext,
        product_area: str,
    ) -> Tuple[Optional[Theme], float, str]:
        """
        Match feedback against existing themes using keyword-based similarity.

        Uses Jaccard similarity on keywords extracted from feedback and theme names.

        Args:
            context: Agent context with feedback text
            product_area: Determined product area

        Returns:
            Tuple of (matched_theme, similarity_score, reasoning)
        """
        if not self.theme_repository:
            return None, 0.0, "Theme repository not available"

        # Get active themes
        active_themes = await self.theme_repository.get_active_themes()

        if not active_themes:
            return None, 0.0, "No active themes to match against"

        # Extract keywords from feedback
        feedback_keywords = self._extract_keywords(context.raw_text)

        if not feedback_keywords:
            return None, 0.0, "No keywords extracted from feedback"

        # Find best matching theme using Jaccard similarity
        best_theme = None
        best_score = 0.0

        threshold = self.config.get("theme_match_threshold", 0.70)

        for theme in active_themes:
            # Extract keywords from theme name and description
            theme_text = theme.name_en
            if theme.description_en:
                theme_text += " " + theme.description_en

            theme_keywords = self._extract_keywords(theme_text)

            if not theme_keywords:
                continue

            # Calculate Jaccard similarity
            similarity = self._jaccard_similarity(feedback_keywords, theme_keywords)

            if similarity > best_score:
                best_score = similarity
                best_theme = theme

        if best_theme and best_score >= threshold:
            reasoning = f"Matched theme '{best_theme.name_en}' with {best_score:.1%} similarity"
            return best_theme, best_score, reasoning
        elif best_theme:
            reasoning = f"Best match '{best_theme.name_en}' at {best_score:.1%} below threshold ({threshold:.0%})"
            return None, best_score, reasoning
        else:
            return None, 0.0, "No similar themes found"

    def _extract_keywords(self, text: str) -> Set[str]:
        """
        Extract keywords from text.

        Simple keyword extraction:
        - Lowercase
        - Remove stopwords
        - Keep words 3+ characters
        - Remove punctuation

        Args:
            text: Text to extract keywords from

        Returns:
            Set of keywords
        """
        # Simple stopwords (extend as needed)
        stopwords = {
            "the", "is", "at", "which", "on", "a", "an", "and", "or", "but",
            "in", "with", "to", "for", "of", "as", "by", "from", "this", "that",
            "are", "was", "were", "been", "be", "have", "has", "had", "do", "does",
            "did", "will", "would", "should", "could", "can", "may", "might",
        }

        # Lowercase and split
        text_lower = text.lower()

        # Remove punctuation and split
        words = re.findall(r'\b\w+\b', text_lower)

        # Filter: length >= 3, not stopword
        keywords = {
            word for word in words
            if len(word) >= 3 and word not in stopwords
        }

        return keywords

    def _jaccard_similarity(self, set1: Set[str], set2: Set[str]) -> float:
        """
        Calculate Jaccard similarity between two sets.

        Jaccard = |intersection| / |union|

        Args:
            set1: First set
            set2: Second set

        Returns:
            Similarity score (0.0 to 1.0)
        """
        if not set1 or not set2:
            return 0.0

        intersection = set1.intersection(set2)
        union = set1.union(set2)

        return len(intersection) / len(union)

    def _decide_action(
        self,
        matched_theme: Optional[Theme],
        match_score: float,
    ) -> Tuple[str, str]:
        """
        Decide LINK vs CREATE action based on match score.

        Args:
            matched_theme: Matched theme (if any)
            match_score: Theme similarity score

        Returns:
            Tuple of (action, reasoning)
        """
        threshold = self.config.get("theme_match_threshold", 0.70)

        if matched_theme and match_score >= threshold:
            action = "LINK"
            reasoning = f"Match score {match_score:.1%} exceeds threshold ({threshold:.0%})"
        else:
            action = "CREATE"
            if match_score > 0:
                reasoning = f"Match score {match_score:.1%} below threshold ({threshold:.0%})"
            else:
                reasoning = "No suitable theme found"

        return action, reasoning

    def _build_reasoning(
        self,
        disambiguation_signals: List[Dict],
        compliance_signals: List[Dict],
        product_area: str,
        area_confidence: float,
        area_reasoning: str,
        match_score: float,
        match_reasoning: str,
        action: str,
        action_reasoning: str,
    ) -> str:
        """
        Build human-readable reasoning text explaining the triage decision.

        Args:
            disambiguation_signals: Disambiguation matches
            compliance_signals: Compliance matches
            product_area: Determined product area
            area_confidence: Area confidence score
            area_reasoning: Area determination reasoning
            match_score: Theme match score
            match_reasoning: Theme match reasoning
            action: LINK or CREATE
            action_reasoning: Action decision reasoning

        Returns:
            Formatted reasoning text
        """
        parts = []

        # Disambiguation
        if disambiguation_signals:
            terms = [f"'{s['term']}' → {s['variant']}" for s in disambiguation_signals]
            parts.append(f"🔍 Disambiguation: {', '.join(terms)}")

        # Compliance
        if compliance_signals:
            regulations = [s["regulation"] for s in compliance_signals]
            parts.append(f"⚖️ Compliance: {', '.join(regulations)} (HIGH PRIORITY)")

        # Product Area
        parts.append(f"📦 Product Area: {product_area} ({area_confidence:.0%} confidence)")
        parts.append(f"   Reason: {area_reasoning}")

        # Theme Matching
        if match_score > 0:
            parts.append(f"🎯 Theme Match: {match_score:.1%} similarity")
        parts.append(f"   {match_reasoning}")

        # Action
        parts.append(f"✅ Decision: {action}")
        parts.append(f"   {action_reasoning}")

        return "\n".join(parts)
