#!/usr/bin/env python3
"""
Agent Accuracy Test Script

Tests agent pipeline accuracy against labeled test dataset.

Usage:
    python scripts/test_agent_accuracy.py --test-data data/test_labels.csv
    python scripts/test_agent_accuracy.py --create-labels --limit 50
"""

import asyncio
import argparse
import csv
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from collections import defaultdict

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.core.config import settings
from app.repositories.feedback import FeedbackRepository
from app.repositories.theme import ThemeRepository
from app.agents.orchestrator import AgentOrchestrator
from app.services.rule_engine import get_rule_engine

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TestCase:
    """Single test case with labeled ground truth."""

    def __init__(
        self,
        feedback_id: int,
        raw_text: str,
        expected_product_area: str,
        expected_compliance: bool = False,
        expected_compliance_tags: Optional[List[str]] = None,
        notes: str = "",
    ):
        self.feedback_id = feedback_id
        self.raw_text = raw_text
        self.expected_product_area = expected_product_area
        self.expected_compliance = expected_compliance
        self.expected_compliance_tags = expected_compliance_tags or []
        self.notes = notes

        # Will be populated after running agent
        self.predicted_product_area: Optional[str] = None
        self.predicted_compliance: bool = False
        self.predicted_compliance_tags: List[str] = []
        self.agent_confidence: float = 0.0
        self.agent_reasoning: str = ""


class AccuracyMetrics:
    """Accuracy metrics for classification."""

    def __init__(self, product_area: str):
        self.product_area = product_area
        self.true_positives = 0  # Correctly predicted this area
        self.false_positives = 0  # Incorrectly predicted this area
        self.false_negatives = 0  # Failed to predict this area when expected
        self.true_negatives = 0  # Correctly didn't predict this area

    @property
    def precision(self) -> float:
        """Precision = TP / (TP + FP)"""
        denominator = self.true_positives + self.false_positives
        return self.true_positives / denominator if denominator > 0 else 0.0

    @property
    def recall(self) -> float:
        """Recall = TP / (TP + FN)"""
        denominator = self.true_positives + self.false_negatives
        return self.true_positives / denominator if denominator > 0 else 0.0

    @property
    def f1_score(self) -> float:
        """F1 = 2 * (Precision * Recall) / (Precision + Recall)"""
        p = self.precision
        r = self.recall
        return 2 * (p * r) / (p + r) if (p + r) > 0 else 0.0


class AgentAccuracyTester:
    """Tests agent pipeline accuracy against labeled data."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.feedback_repo = FeedbackRepository(session)
        self.theme_repo = ThemeRepository(session)

        # Initialize agent pipeline
        self.rule_engine = get_rule_engine()
        self.orchestrator = AgentOrchestrator(
            rule_engine=self.rule_engine,
            theme_repository=self.theme_repo,
        )

    async def test_single_case(self, test_case: TestCase):
        """Run agent pipeline on a single test case."""
        logger.info(f"Testing feedback {test_case.feedback_id}")

        try:
            success, enrichment, agent_results = await self.orchestrator.enrich_feedback(
                feedback_id=str(test_case.feedback_id),
                raw_text=test_case.raw_text,
                language="EN",
            )

            test_case.predicted_product_area = enrichment.get("product_area")
            test_case.predicted_compliance = enrichment.get("is_compliance", False)
            test_case.predicted_compliance_tags = enrichment.get("compliance_tags", [])
            test_case.agent_confidence = enrichment.get("area_confidence", 0.0)
            test_case.agent_reasoning = enrichment.get("reasoning", "")

        except Exception as e:
            logger.error(f"Agent failed for test case {test_case.feedback_id}: {e}")
            test_case.predicted_product_area = None
            test_case.agent_reasoning = f"ERROR: {str(e)}"

    async def test_batch(self, test_cases: List[TestCase]):
        """Run agent pipeline on all test cases."""
        logger.info(f"Testing {len(test_cases)} test cases")

        for i, test_case in enumerate(test_cases, 1):
            logger.info(f"Testing {i}/{len(test_cases)}")
            await self.test_single_case(test_case)

    def calculate_metrics(
        self,
        test_cases: List[TestCase],
    ) -> Dict[str, AccuracyMetrics]:
        """Calculate accuracy metrics per product area."""
        # Get unique product areas from test cases
        all_areas = set(tc.expected_product_area for tc in test_cases)
        all_areas.update(tc.predicted_product_area for tc in test_cases if tc.predicted_product_area)

        # Initialize metrics for each area
        metrics = {area: AccuracyMetrics(area) for area in all_areas}

        # Calculate confusion matrix values
        for tc in test_cases:
            expected = tc.expected_product_area
            predicted = tc.predicted_product_area

            if predicted == expected:
                # True positive for this area
                metrics[expected].true_positives += 1

                # True negative for all other areas
                for area in all_areas:
                    if area != expected:
                        metrics[area].true_negatives += 1
            else:
                # False negative for expected area
                metrics[expected].false_negatives += 1

                # False positive for predicted area (if any)
                if predicted and predicted in metrics:
                    metrics[predicted].false_positives += 1

                # True negative for all other areas
                for area in all_areas:
                    if area not in {expected, predicted}:
                        metrics[area].true_negatives += 1

        return metrics


def load_test_cases_from_csv(csv_path: Path) -> List[TestCase]:
    """Load test cases from CSV file."""
    logger.info(f"Loading test cases from {csv_path}")

    test_cases = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)

        for row in reader:
            test_case = TestCase(
                feedback_id=int(row['feedback_id']),
                raw_text=row['raw_text'],
                expected_product_area=row['expected_product_area'],
                expected_compliance=row.get('expected_compliance', '').lower() == 'true',
                expected_compliance_tags=row.get('expected_compliance_tags', '').split(',') if row.get('expected_compliance_tags') else [],
                notes=row.get('notes', ''),
            )
            test_cases.append(test_case)

    logger.info(f"Loaded {len(test_cases)} test cases")
    return test_cases


async def create_label_template(limit: int, output_path: Path):
    """Create a CSV template for human labeling."""
    logger.info(f"Creating label template for {limit} feedback items")

    async with get_db_session() as session:
        feedback_repo = FeedbackRepository(session)
        feedback_items, total = await feedback_repo.list_all(limit=limit, offset=0)

    logger.info(f"Fetched {len(feedback_items)} feedback items")

    # Write template CSV
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)

        # Header
        writer.writerow([
            "feedback_id",
            "raw_text",
            "expected_product_area",
            "expected_compliance",
            "expected_compliance_tags",
            "notes"
        ])

        # Rows (empty expected values for human to fill)
        for feedback in feedback_items:
            writer.writerow([
                feedback.id,
                feedback.content,
                "",  # Human fills this
                "",  # Human fills this
                "",  # Human fills this
                ""   # Human fills this
            ])

    logger.info(f"Label template created at {output_path}")
    print(f"\n✓ Created label template: {output_path}")
    print(f"Please fill in the expected values and save as a new file for testing.\n")


def write_accuracy_report(
    test_cases: List[TestCase],
    metrics: Dict[str, AccuracyMetrics],
    output_path: Path,
):
    """Write accuracy report to CSV."""
    logger.info(f"Writing accuracy report to {output_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)

        # Test case results
        writer.writerow([
            "feedback_id",
            "raw_text_preview",
            "expected_product_area",
            "predicted_product_area",
            "correct",
            "expected_compliance",
            "predicted_compliance",
            "compliance_correct",
            "agent_confidence",
            "agent_reasoning",
            "notes"
        ])

        for tc in test_cases:
            writer.writerow([
                tc.feedback_id,
                tc.raw_text[:200],
                tc.expected_product_area,
                tc.predicted_product_area,
                "YES" if tc.predicted_product_area == tc.expected_product_area else "NO",
                "YES" if tc.expected_compliance else "NO",
                "YES" if tc.predicted_compliance else "NO",
                "YES" if tc.predicted_compliance == tc.expected_compliance else "NO",
                f"{tc.agent_confidence:.3f}",
                tc.agent_reasoning,
                tc.notes,
            ])

        # Separator
        writer.writerow([])
        writer.writerow(["METRICS BY PRODUCT AREA"])
        writer.writerow([
            "product_area",
            "precision",
            "recall",
            "f1_score",
            "true_positives",
            "false_positives",
            "false_negatives"
        ])

        for area, metric in sorted(metrics.items()):
            writer.writerow([
                area,
                f"{metric.precision:.3f}",
                f"{metric.recall:.3f}",
                f"{metric.f1_score:.3f}",
                metric.true_positives,
                metric.false_positives,
                metric.false_negatives,
            ])

    logger.info("Accuracy report written successfully")


def print_accuracy_summary(
    test_cases: List[TestCase],
    metrics: Dict[str, AccuracyMetrics],
):
    """Print accuracy summary to console."""
    total = len(test_cases)
    correct = sum(1 for tc in test_cases if tc.predicted_product_area == tc.expected_product_area)
    accuracy = correct / total if total > 0 else 0.0

    # Compliance accuracy
    compliance_correct = sum(
        1 for tc in test_cases
        if tc.predicted_compliance == tc.expected_compliance
    )
    compliance_accuracy = compliance_correct / total if total > 0 else 0.0

    print("\n" + "="*80)
    print("AGENT ACCURACY METRICS")
    print("="*80)
    print(f"Total Test Cases: {total}")
    print(f"Overall Accuracy: {accuracy:.1%} ({correct}/{total} correct)")
    print(f"Compliance Detection Accuracy: {compliance_accuracy:.1%} ({compliance_correct}/{total} correct)")
    print()
    print("Per Product Area:")
    print(f"{'Area':<30} {'Precision':<12} {'Recall':<12} {'F1 Score':<12}")
    print("-" * 80)

    for area, metric in sorted(metrics.items(), key=lambda x: x[1].f1_score, reverse=True):
        print(f"{area:<30} {metric.precision:<12.1%} {metric.recall:<12.1%} {metric.f1_score:<12.3f}")

    print()
    print("Lowest Accuracy Areas (potential rule improvements needed):")
    lowest = sorted(metrics.items(), key=lambda x: x[1].f1_score)[:5]
    for area, metric in lowest:
        print(f"  - {area}: F1={metric.f1_score:.3f} (Precision={metric.precision:.1%}, Recall={metric.recall:.1%})")

    print("="*80 + "\n")


async def main():
    """Main accuracy test script."""
    parser = argparse.ArgumentParser(
        description="Test agent pipeline accuracy against labeled data"
    )
    parser.add_argument(
        "--test-data",
        type=str,
        help="Path to labeled test data CSV"
    )
    parser.add_argument(
        "--create-labels",
        action="store_true",
        help="Create a label template CSV for human labeling"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Number of items to include in label template (default: 50)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=f"reports/accuracy_{datetime.now().strftime('%Y-%m-%d')}.csv",
        help="Output accuracy report path"
    )

    args = parser.parse_args()

    # Mode 1: Create label template
    if args.create_labels:
        template_path = Path(f"data/test_labels_template_{datetime.now().strftime('%Y-%m-%d')}.csv")
        await create_label_template(args.limit, template_path)
        return

    # Mode 2: Test accuracy
    if not args.test_data:
        print("Error: Must provide --test-data or use --create-labels")
        sys.exit(1)

    test_data_path = Path(args.test_data)
    if not test_data_path.exists():
        print(f"Error: Test data file not found: {test_data_path}")
        sys.exit(1)

    logger.info("Starting agent accuracy test")

    # Load test cases
    test_cases = load_test_cases_from_csv(test_data_path)

    # Run agent pipeline on all test cases
    async with get_db_session() as session:
        tester = AgentAccuracyTester(session)
        await tester.test_batch(test_cases)

        # Calculate metrics
        metrics = tester.calculate_metrics(test_cases)

    # Write report
    output_path = Path(args.output)
    write_accuracy_report(test_cases, metrics, output_path)

    # Print summary
    print_accuracy_summary(test_cases, metrics)

    logger.info(f"Accuracy test complete. Report saved to {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
