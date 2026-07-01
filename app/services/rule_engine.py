"""
Rule engine for loading and applying YAML-based classification rules.

The rule engine is a singleton service that loads rules from YAML files
at startup and provides methods for:
- Disambiguation (Section 2 rules)
- Compliance detection (Section 3 lexicon)
- Scope keyword matching (Section 1 taxonomy)

Rules can be hot-reloaded via the reload() method without restarting the app.
"""

import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Set
import yaml

logger = logging.getLogger("rule_engine")


class RuleEngine:
    """
    Singleton rule engine for YAML-based classification rules.

    Loads rules from app/config/rules/ at initialization.
    Provides methods for applying disambiguation, compliance, and taxonomy rules.
    """

    def __init__(self, config_dir: Optional[Path] = None):
        """
        Initialize rule engine and load rules from YAML files.

        Args:
            config_dir: Path to config directory (defaults to app/config/rules/)
        """
        if config_dir is None:
            # Default to app/config/rules/ relative to this file
            config_dir = Path(__file__).parent.parent / "config" / "rules"

        self.config_dir = Path(config_dir)
        self.disambiguation_rules: Dict = {}
        self.compliance_lexicon: Dict = {}
        self.taxonomy: Dict = {}

        self._load_all_rules()

    def _load_all_rules(self):
        """Load all rule files from the config directory."""
        logger.info(f"Loading rules from {self.config_dir}")

        try:
            # Load disambiguation rules (Section 2)
            disambiguation_path = self.config_dir / "disambiguation.yaml"
            if disambiguation_path.exists():
                with open(disambiguation_path, "r", encoding="utf-8") as f:
                    self.disambiguation_rules = yaml.safe_load(f) or {}
                logger.info(f"Loaded {len(self.disambiguation_rules.get('rules', []))} disambiguation rules")
            else:
                logger.warning(f"Disambiguation rules not found: {disambiguation_path}")

            # Load compliance lexicon (Section 3)
            compliance_path = self.config_dir / "compliance_lexicon.yaml"
            if compliance_path.exists():
                with open(compliance_path, "r", encoding="utf-8") as f:
                    self.compliance_lexicon = yaml.safe_load(f) or {}
                logger.info(f"Loaded {len(self.compliance_lexicon.get('regulations', []))} compliance regulations")
            else:
                logger.warning(f"Compliance lexicon not found: {compliance_path}")

            # Load taxonomy (Section 1)
            taxonomy_path = self.config_dir / "taxonomy.yaml"
            if taxonomy_path.exists():
                with open(taxonomy_path, "r", encoding="utf-8") as f:
                    self.taxonomy = yaml.safe_load(f) or {}
                logger.info(f"Loaded {len(self.taxonomy.get('scopes', []))} L1 scopes")
            else:
                logger.warning(f"Taxonomy not found: {taxonomy_path}")

        except Exception as e:
            logger.error(f"Error loading rules: {e}", exc_info=True)
            raise

    def reload(self):
        """
        Hot-reload all rules from YAML files.

        This can be called from an admin endpoint to update rules
        without restarting the application.
        """
        logger.info("Hot-reloading rules")
        self._load_all_rules()

    def apply_disambiguation_rules(
        self,
        text: str,
        language: str = "EN"
    ) -> List[Dict[str, any]]:
        """
        Apply disambiguation rules from Section 2.

        Disambiguates terms like "Settlement", "Approval", "Integration"
        based on surrounding context (noun before term, workflow described).

        Args:
            text: Raw feedback text
            language: Language code ("EN", "AR", "Mixed")

        Returns:
            List of matched rules with scope and confidence
        """
        matches = []
        text_lower = text.lower()

        for rule in self.disambiguation_rules.get("rules", []):
            term = rule.get("term", "").lower()
            variants = rule.get("variants", [])

            # Check if term appears in text
            if term not in text_lower:
                continue

            # Try to match specific variants based on context
            for variant in variants:
                patterns = variant.get("context_patterns", [])
                scope = variant.get("scope")
                cross_tag = variant.get("cross_tag")

                # Check if any context pattern matches
                for pattern in patterns:
                    if re.search(pattern, text_lower, re.IGNORECASE):
                        match = {
                            "term": term,
                            "variant": variant.get("name"),
                            "scope": scope,
                            "confidence": variant.get("confidence", 1.0),
                        }
                        if cross_tag:
                            match["cross_tag"] = cross_tag

                        matches.append(match)
                        logger.debug(f"Disambiguation match: {match}")
                        break  # Only match once per variant

        return matches

    def detect_compliance_terms(
        self,
        text: str,
        language: str = "EN"
    ) -> List[Dict[str, any]]:
        """
        Detect compliance/regulatory terms from Section 3.

        Any feedback matching terms in the compliance lexicon should be
        classified as Compliance/Legal - the highest Business Impact level.

        Args:
            text: Raw feedback text
            language: Language code

        Returns:
            List of matched regulations with confidence
        """
        matches = []
        text_lower = text.lower()

        for regulation in self.compliance_lexicon.get("regulations", []):
            name = regulation.get("name")
            country = regulation.get("country")
            key_terms = regulation.get("key_terms", [])
            confidence = regulation.get("confidence", "High")

            # Count matching terms
            matched_terms = []
            for term in key_terms:
                if term.lower() in text_lower:
                    matched_terms.append(term)

            # If any term matches, flag as compliance
            if matched_terms:
                match = {
                    "regulation": name,
                    "country": country,
                    "matched_terms": matched_terms,
                    "term_count": len(matched_terms),
                    "confidence": confidence,
                }
                matches.append(match)
                logger.debug(f"Compliance match: {match}")

        # Check additional trigger phrases
        trigger_phrases = self.compliance_lexicon.get("trigger_phrases", [])
        for phrase in trigger_phrases:
            if phrase.lower() in text_lower:
                if not any(m.get("regulation") == "Trigger Phrase" for m in matches):
                    matches.append({
                        "regulation": "Trigger Phrase",
                        "matched_terms": [phrase],
                        "confidence": "High",
                    })

        return matches

    def match_scope_keywords(
        self,
        text: str,
        language: str = "EN"
    ) -> List[Dict[str, any]]:
        """
        Match L1 scope keywords from Section 1 taxonomy.

        Returns ranked list of scopes based on keyword matches.

        Args:
            text: Raw feedback text
            language: Language code

        Returns:
            List of scope matches with scores
        """
        matches = []
        text_lower = text.lower()

        for scope in self.taxonomy.get("scopes", []):
            scope_name = scope.get("name")
            keywords = scope.get("keywords", [])
            mental_model_terms = scope.get("mental_model_terms", [])

            # Count keyword matches
            matched_keywords = []
            for keyword in keywords:
                if keyword.lower() in text_lower:
                    matched_keywords.append(keyword)

            # Count mental model term matches
            matched_mental_model = []
            for term in mental_model_terms:
                if term.lower() in text_lower:
                    matched_mental_model.append(term)

            # If any matches, add to results
            total_matches = len(matched_keywords) + len(matched_mental_model)
            if total_matches > 0:
                match = {
                    "scope": scope_name,
                    "matched_keywords": matched_keywords,
                    "matched_mental_model": matched_mental_model,
                    "score": total_matches,
                    "tribe": scope.get("tribe"),
                }
                matches.append(match)

        # Sort by score descending
        matches.sort(key=lambda x: x["score"], reverse=True)

        if matches:
            logger.debug(f"Scope matches: {[m['scope'] for m in matches]}")

        return matches

    def get_scope_by_name(self, scope_name: str) -> Optional[Dict]:
        """
        Get scope details by name.

        Args:
            scope_name: Name of the L1 scope

        Returns:
            Scope dict or None if not found
        """
        for scope in self.taxonomy.get("scopes", []):
            if scope.get("name") == scope_name:
                return scope
        return None

    def is_valid_scope(self, scope_name: str) -> bool:
        """
        Check if a scope name is valid.

        Args:
            scope_name: Scope name to validate

        Returns:
            True if valid, False otherwise
        """
        return self.get_scope_by_name(scope_name) is not None

    def get_invalid_scope_names(self) -> Set[str]:
        """
        Get set of invalid/legacy scope names from taxonomy.

        Returns:
            Set of invalid scope names
        """
        return set(self.taxonomy.get("invalid_scope_names", []))


# Singleton instance
_rule_engine_instance: Optional[RuleEngine] = None


def get_rule_engine() -> RuleEngine:
    """
    Get singleton rule engine instance.

    Lazily initializes the rule engine on first access.

    Returns:
        Shared RuleEngine instance
    """
    global _rule_engine_instance
    if _rule_engine_instance is None:
        _rule_engine_instance = RuleEngine()
    return _rule_engine_instance
