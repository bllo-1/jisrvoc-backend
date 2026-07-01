#!/usr/bin/env python3
"""
Pipeline Comparison Script

Compares old LLM-based classification pipeline with new agent-based pipeline.

Usage:
    python scripts/compare_pipelines.py --limit 100 --output reports/comparison_YYYY-MM-DD.csv
"""

import asyncio
import argparse
import csv
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.core.config import settings
from app.repositories.feedback import FeedbackRepository
from app.repositories.theme import ThemeRepository
from app.models.feedback import Feedback
from app.services.classification_pipeline import ClassificationPipeline
from app.ai.llm_provider import create_llm_provider, LLMProvider
from app.agents.orchestrator import AgentOrchestrator
from app.services.rule_engine import get_rule_engine

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Mapping from old pipeline product areas to new agent taxonomy
PRODUCT_AREA_MAPPING = {
    "billing": "Finance",
    "finance": "Finance",
    "payroll": "Payroll",
    "salary": "Payroll",
    "attendance": "Attendance & Leaves",
    "leave": "Attendance & Leaves",
    "vacation": "Attendance & Leaves",
    "employee": "Employee Lifecycle",
    "onboarding": "Employee Lifecycle",
    "offboarding": "Employee Lifecycle",
    "hr": "Employee Lifecycle",
    "integration": "Integrations",
    "api": "Integrations",
    "webhook": "Integrations",
    "sso": "Integrations",
    "ui": "Platform & Issues",
    "mobile": "Mobile",
    "app": "Mobile",
    "report": "Reports & Analytics",
    "analytics": "Reports & Analytics",
    "dashboard": "Reports & Analytics",
    "permission": "Security & Access Control",
    "access": "Security & Access Control",
    "auth": "Security & Access Control",
    "compliance": "Compliance & Localization",
    "gosi": "Compliance & Localization",
    "wps": "Compliance & Localization",
    "localization": "Compliance & Localization",
}


def normalize_product_area(area: Optional[str]) -> Optional[str]:
    """Normalize product area to agent taxonomy."""
    if not area:
        return None

    area_lower = area.lower().strip()

    # Direct mapping
    if area_lower in PRODUCT_AREA_MAPPING:
        return PRODUCT_AREA_MAPPING[area_lower]

    # Fuzzy matching - check if any key is substring
    for old_key, new_area in PRODUCT_AREA_MAPPING.items():
        if old_key in area_lower:
            return new_area

    return "Other / Unclassified"


class ComparisonResult:
    """Result of comparing old vs new pipeline for one feedback item."""

    def __init__(
        self,
        feedback_id: int,
        raw_text: str,
        old_product_area: Optional[str],
        old_confidence: float,
        old_execution_time_ms: float,
        agent_product_area: Optional[str],
        agent_confidence: float,
        agent_execution_time_ms: float,
        agent_action: Optional[str],
        agent_reasoning: Optional[str],
        agent_compliance: bool,
        agent_compliance_tags: List[str],
        agent_matched_theme: Optional[str],
    ):
        self.feedback_id = feedback_id
        self.raw_text = raw_text
        self.old_product_area = old_product_area
        self.old_confidence = old_confidence
        self.old_execution_time_ms = old_execution_time_ms
        self.agent_product_area = agent_product_area
        self.agent_confidence = agent_confidence
        self.agent_execution_time_ms = agent_execution_time_ms
        self.agent_action = agent_action
        self.agent_reasoning = agent_reasoning
        self.agent_compliance = agent_compliance
        self.agent_compliance_tags = agent_compliance_tags
        self.agent_matched_theme = agent_matched_theme

        # Normalize old area to agent taxonomy for comparison
        self.normalized_old_area = normalize_product_area(old_product_area)

        # Determine if areas match
        self.areas_match = (
            self.normalized_old_area == self.agent_product_area
            if self.normalized_old_area and self.agent_product_area
            else False
        )


class PipelineComparator:
    """Compares old LLM pipeline with new agent pipeline."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.feedback_repo = FeedbackRepository(session)
        self.theme_repo = ThemeRepository(session)

        # Initialize old pipeline
        provider_type = LLMProvider(settings.llm_provider)
        self.llm_provider = create_llm_provider(provider_type)
        self.old_pipeline = ClassificationPipeline(self.llm_provider)

        # Initialize new agent pipeline
        self.rule_engine = get_rule_engine()
        self.orchestrator = AgentOrchestrator(
            rule_engine=self.rule_engine,
            theme_repository=self.theme_repo,
        )

    async def compare_single_feedback(
        self,
        feedback: Feedback,
    ) -> ComparisonResult:
        """Compare old vs new pipeline for a single feedback item."""
        logger.info(f"Comparing feedback {feedback.id}")

        # Run old pipeline
        old_start = time.time()
        try:
            old_result = await self.old_pipeline.classify_feedback(
                title=feedback.title,
                content=feedback.content,
                source=feedback.source,
            )
            old_execution_time_ms = (time.time() - old_start) * 1000
            old_product_area = old_result.product_area
            old_confidence = old_result.category_confidence
        except Exception as e:
            logger.error(f"Old pipeline failed for feedback {feedback.id}: {e}")
            old_execution_time_ms = (time.time() - old_start) * 1000
            old_product_area = None
            old_confidence = 0.0

        # Run new agent pipeline
        agent_start = time.time()
        try:
            success, enrichment, agent_results = await self.orchestrator.enrich_feedback(
                feedback_id=str(feedback.id),
                raw_text=feedback.content,
                language="EN",  # TODO: Auto-detect
            )
            agent_execution_time_ms = (time.time() - agent_start) * 1000

            agent_product_area = enrichment.get("product_area")
            agent_confidence = enrichment.get("area_confidence", 0.0)
            agent_action = enrichment.get("action")
            agent_reasoning = enrichment.get("reasoning")
            agent_compliance = enrichment.get("is_compliance", False)
            agent_compliance_tags = enrichment.get("compliance_tags", [])
            agent_matched_theme = enrichment.get("matched_theme_name")
        except Exception as e:
            logger.error(f"Agent pipeline failed for feedback {feedback.id}: {e}")
            agent_execution_time_ms = (time.time() - agent_start) * 1000
            agent_product_area = None
            agent_confidence = 0.0
            agent_action = None
            agent_reasoning = str(e)
            agent_compliance = False
            agent_compliance_tags = []
            agent_matched_theme = None

            # Rollback transaction to recover from database errors
            try:
                await self.session.rollback()
            except Exception:
                pass  # Ignore rollback errors

        return ComparisonResult(
            feedback_id=feedback.id,
            raw_text=feedback.content[:200],  # Truncate for CSV
            old_product_area=old_product_area,
            old_confidence=old_confidence,
            old_execution_time_ms=old_execution_time_ms,
            agent_product_area=agent_product_area,
            agent_confidence=agent_confidence,
            agent_execution_time_ms=agent_execution_time_ms,
            agent_action=agent_action,
            agent_reasoning=agent_reasoning,
            agent_compliance=agent_compliance,
            agent_compliance_tags=agent_compliance_tags,
            agent_matched_theme=agent_matched_theme,
        )

    async def compare_batch(
        self,
        limit: int = 100,
    ) -> List[ComparisonResult]:
        """Compare pipelines on a batch of feedback items."""
        logger.info(f"Fetching {limit} recent feedback items")

        # Fetch recent feedback
        feedback_items, total = await self.feedback_repo.list_all(
            limit=limit,
            offset=0,
        )

        logger.info(f"Found {len(feedback_items)} feedback items, comparing...")

        results = []
        for i, feedback in enumerate(feedback_items, 1):
            logger.info(f"Processing {i}/{len(feedback_items)}: Feedback {feedback.id}")

            try:
                result = await self.compare_single_feedback(feedback)
                results.append(result)
            except Exception as e:
                logger.error(f"Error comparing feedback {feedback.id}: {e}", exc_info=True)
                continue

        return results


def calculate_metrics(results: List[ComparisonResult]) -> Dict[str, Any]:
    """Calculate comparison metrics from results."""
    total = len(results)
    if total == 0:
        return {}

    # Product area agreement rate
    matches = sum(1 for r in results if r.areas_match)
    agreement_rate = matches / total

    # Average confidence difference (agent - old)
    confidence_diffs = [
        r.agent_confidence - r.old_confidence
        for r in results
        if r.agent_confidence is not None and r.old_confidence is not None
    ]
    avg_confidence_diff = sum(confidence_diffs) / len(confidence_diffs) if confidence_diffs else 0.0

    # Execution time comparison
    old_times = [r.old_execution_time_ms for r in results if r.old_execution_time_ms > 0]
    agent_times = [r.agent_execution_time_ms for r in results if r.agent_execution_time_ms > 0]

    avg_old_time = sum(old_times) / len(old_times) if old_times else 0.0
    avg_agent_time = sum(agent_times) / len(agent_times) if agent_times else 0.0
    speedup = avg_old_time / avg_agent_time if avg_agent_time > 0 else 0.0

    # Compliance detection (only agents detect this)
    compliance_detected = sum(1 for r in results if r.agent_compliance)
    compliance_rate = compliance_detected / total

    # Disagreement patterns (which old areas map to which new areas most often)
    disagreements = [r for r in results if not r.areas_match]
    disagreement_patterns = {}
    for r in disagreements:
        key = f"{r.old_product_area} → {r.agent_product_area}"
        disagreement_patterns[key] = disagreement_patterns.get(key, 0) + 1

    return {
        "total_comparisons": total,
        "agreement_rate": agreement_rate,
        "matches": matches,
        "disagreements": total - matches,
        "avg_confidence_diff": avg_confidence_diff,
        "avg_old_execution_time_ms": avg_old_time,
        "avg_agent_execution_time_ms": avg_agent_time,
        "speedup_factor": speedup,
        "compliance_detected_count": compliance_detected,
        "compliance_detection_rate": compliance_rate,
        "disagreement_patterns": disagreement_patterns,
    }


def write_csv_report(
    results: List[ComparisonResult],
    output_path: Path,
):
    """Write comparison results to CSV file."""
    logger.info(f"Writing CSV report to {output_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)

        # Header
        writer.writerow([
            "feedback_id",
            "raw_text_preview",
            "old_product_area",
            "old_confidence",
            "old_time_ms",
            "agent_product_area",
            "agent_confidence",
            "agent_time_ms",
            "normalized_old_area",
            "areas_match",
            "agent_action",
            "agent_compliance",
            "agent_compliance_tags",
            "agent_matched_theme",
            "agent_reasoning",
        ])

        # Rows
        for r in results:
            writer.writerow([
                r.feedback_id,
                r.raw_text,
                r.old_product_area,
                f"{r.old_confidence:.3f}",
                f"{r.old_execution_time_ms:.1f}",
                r.agent_product_area,
                f"{r.agent_confidence:.3f}",
                f"{r.agent_execution_time_ms:.1f}",
                r.normalized_old_area,
                "YES" if r.areas_match else "NO",
                r.agent_action,
                "YES" if r.agent_compliance else "NO",
                ", ".join(r.agent_compliance_tags),
                r.agent_matched_theme or "",
                r.agent_reasoning or "",
            ])

    logger.info(f"CSV report written successfully")


def print_metrics_summary(metrics: Dict[str, Any]):
    """Print metrics summary to console."""
    print("\n" + "="*80)
    print("PIPELINE COMPARISON METRICS")
    print("="*80)
    print(f"Total Comparisons: {metrics['total_comparisons']}")
    print(f"Product Area Agreement Rate: {metrics['agreement_rate']:.1%} (target: >95%)")
    print(f"  - Matches: {metrics['matches']}")
    print(f"  - Disagreements: {metrics['disagreements']}")
    print()
    print(f"Average Confidence Difference (Agent - Old): {metrics['avg_confidence_diff']:+.3f}")
    print()
    print(f"Execution Time Comparison:")
    print(f"  - Old Pipeline: {metrics['avg_old_execution_time_ms']:.1f}ms")
    print(f"  - Agent Pipeline: {metrics['avg_agent_execution_time_ms']:.1f}ms")
    print(f"  - Speedup Factor: {metrics['speedup_factor']:.2f}x")
    print()
    print(f"Compliance Detection (Agent-only feature):")
    print(f"  - Detected: {metrics['compliance_detected_count']} items ({metrics['compliance_detection_rate']:.1%})")
    print()
    print("Top Disagreement Patterns:")
    patterns = sorted(
        metrics['disagreement_patterns'].items(),
        key=lambda x: x[1],
        reverse=True
    )[:10]
    for pattern, count in patterns:
        print(f"  - {pattern}: {count} times")
    print("="*80 + "\n")


async def main():
    """Main comparison script."""
    parser = argparse.ArgumentParser(
        description="Compare old LLM pipeline with new agent pipeline"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Number of feedback items to compare (default: 100)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=f"reports/comparison_{datetime.now().strftime('%Y-%m-%d')}.csv",
        help="Output CSV file path"
    )

    args = parser.parse_args()

    logger.info("Starting pipeline comparison")
    logger.info(f"Limit: {args.limit}")
    logger.info(f"Output: {args.output}")

    if settings.use_mock_data:
        logger.warning("USE_MOCK_DATA=true - comparison will use mock data")

    # Run comparison
    async with get_db_session() as session:
        comparator = PipelineComparator(session)
        results = await comparator.compare_batch(limit=args.limit)

    # Calculate metrics
    metrics = calculate_metrics(results)

    # Write CSV report
    output_path = Path(args.output)
    write_csv_report(results, output_path)

    # Print summary
    print_metrics_summary(metrics)

    logger.info(f"Comparison complete. Report saved to {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
