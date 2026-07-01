#!/usr/bin/env python3
"""
Agent Performance Benchmark Script

Benchmarks agent pipeline performance (latency, throughput).

Usage:
    python scripts/benchmark_agents.py --items 1000
    python scripts/benchmark_agents.py --items 100 --test-reload
"""

import asyncio
import argparse
import logging
import sys
import time
import statistics
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

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
    level=logging.WARNING,  # Reduce noise during benchmarking
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
# Set benchmark logger to INFO
benchmark_logger = logging.getLogger("benchmark")
benchmark_logger.setLevel(logging.INFO)


class BenchmarkResult:
    """Result from benchmarking agent pipeline."""

    def __init__(self, execution_times_ms: List[float]):
        self.execution_times_ms = execution_times_ms
        self.count = len(execution_times_ms)

        if self.count > 0:
            self.min = min(execution_times_ms)
            self.max = max(execution_times_ms)
            self.mean = statistics.mean(execution_times_ms)
            self.median = statistics.median(execution_times_ms)
            self.stdev = statistics.stdev(execution_times_ms) if self.count > 1 else 0.0

            # Calculate percentiles
            sorted_times = sorted(execution_times_ms)
            self.p50 = sorted_times[int(0.50 * self.count)]
            self.p95 = sorted_times[int(0.95 * self.count)] if self.count > 1 else self.max
            self.p99 = sorted_times[int(0.99 * self.count)] if self.count > 1 else self.max
        else:
            self.min = self.max = self.mean = self.median = self.stdev = 0.0
            self.p50 = self.p95 = self.p99 = 0.0


class AgentBenchmark:
    """Benchmarks agent pipeline performance."""

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

    async def benchmark_single_item(
        self,
        feedback_id: int,
        raw_text: str,
    ) -> float:
        """Benchmark a single feedback item enrichment."""
        start_time = time.time()

        try:
            success, enrichment, agent_results = await self.orchestrator.enrich_feedback(
                feedback_id=str(feedback_id),
                raw_text=raw_text,
                language="EN",
            )
        except Exception as e:
            benchmark_logger.warning(f"Agent failed for feedback {feedback_id}: {e}")

        execution_time_ms = (time.time() - start_time) * 1000
        return execution_time_ms

    async def benchmark_batch(
        self,
        item_count: int,
    ) -> BenchmarkResult:
        """Benchmark a batch of feedback items."""
        benchmark_logger.info(f"Fetching {item_count} feedback items for benchmarking")

        # Fetch feedback items
        feedback_items, total = await self.feedback_repo.list_all(
            limit=item_count,
            offset=0,
        )

        if len(feedback_items) < item_count:
            benchmark_logger.warning(
                f"Only {len(feedback_items)} feedback items available (requested {item_count})"
            )

        benchmark_logger.info(f"Starting benchmark on {len(feedback_items)} items")

        execution_times = []
        start_batch = time.time()

        for i, feedback in enumerate(feedback_items, 1):
            if i % 100 == 0:
                benchmark_logger.info(f"Progress: {i}/{len(feedback_items)}")

            execution_time = await self.benchmark_single_item(
                feedback_id=feedback.id,
                raw_text=feedback.content,
            )
            execution_times.append(execution_time)

        total_batch_time = time.time() - start_batch

        benchmark_logger.info(f"Benchmark complete. Total time: {total_batch_time:.1f}s")

        return BenchmarkResult(execution_times), total_batch_time

    async def benchmark_reload_impact(
        self,
        sample_size: int = 10,
    ) -> Dict[str, Any]:
        """Benchmark impact of rule hot-reload on performance."""
        benchmark_logger.info(f"Benchmarking rule reload impact (sample size: {sample_size})")

        # Fetch sample feedback
        feedback_items, total = await self.feedback_repo.list_all(
            limit=sample_size,
            offset=0,
        )

        if len(feedback_items) < sample_size:
            benchmark_logger.warning(
                f"Only {len(feedback_items)} feedback items available (requested {sample_size})"
            )

        # Benchmark before reload
        benchmark_logger.info("Running benchmark BEFORE reload")
        before_times = []
        for feedback in feedback_items:
            execution_time = await self.benchmark_single_item(
                feedback_id=feedback.id,
                raw_text=feedback.content,
            )
            before_times.append(execution_time)

        before_result = BenchmarkResult(before_times)

        # Hot-reload rules
        benchmark_logger.info("Performing hot-reload")
        reload_start = time.time()
        success = self.orchestrator.reload_rules()
        reload_time_ms = (time.time() - reload_start) * 1000

        if not success:
            benchmark_logger.error("Rule reload failed")
            return {}

        benchmark_logger.info(f"Rules reloaded in {reload_time_ms:.1f}ms")

        # Benchmark after reload
        benchmark_logger.info("Running benchmark AFTER reload")
        after_times = []
        for feedback in feedback_items:
            execution_time = await self.benchmark_single_item(
                feedback_id=feedback.id,
                raw_text=feedback.content,
            )
            after_times.append(execution_time)

        after_result = BenchmarkResult(after_times)

        return {
            "reload_time_ms": reload_time_ms,
            "before_mean_ms": before_result.mean,
            "after_mean_ms": after_result.mean,
            "mean_diff_ms": after_result.mean - before_result.mean,
            "mean_diff_pct": ((after_result.mean - before_result.mean) / before_result.mean * 100) if before_result.mean > 0 else 0.0,
        }


def print_benchmark_summary(
    result: BenchmarkResult,
    total_time: float,
):
    """Print benchmark summary to console."""
    throughput = result.count / total_time if total_time > 0 else 0.0

    print("\n" + "="*80)
    print("AGENT PIPELINE PERFORMANCE BENCHMARK")
    print("="*80)
    print(f"Items Processed: {result.count}")
    print(f"Total Time: {total_time:.1f}s")
    print(f"Throughput: {throughput:.2f} items/second")
    print()
    print("Latency Statistics (milliseconds):")
    print(f"  Min:      {result.min:>8.1f}ms")
    print(f"  p50:      {result.p50:>8.1f}ms")
    print(f"  Mean:     {result.mean:>8.1f}ms")
    print(f"  Median:   {result.median:>8.1f}ms")
    print(f"  p95:      {result.p95:>8.1f}ms")
    print(f"  p99:      {result.p99:>8.1f}ms")
    print(f"  Max:      {result.max:>8.1f}ms")
    print(f"  StdDev:   {result.stdev:>8.1f}ms")
    print()
    print("Performance Targets:")
    print(f"  p50 < 300ms:  {'✓ PASS' if result.p50 < 300 else '✗ FAIL'}")
    print(f"  p95 < 500ms:  {'✓ PASS' if result.p95 < 500 else '✗ FAIL'}")
    print(f"  p99 < 1000ms: {'✓ PASS' if result.p99 < 1000 else '✗ FAIL'}")
    print("="*80 + "\n")


def print_reload_impact_summary(reload_metrics: Dict[str, Any]):
    """Print reload impact summary."""
    print("\n" + "="*80)
    print("HOT-RELOAD PERFORMANCE IMPACT")
    print("="*80)
    print(f"Reload Time: {reload_metrics['reload_time_ms']:.1f}ms")
    print()
    print("Execution Time Impact:")
    print(f"  Before Reload (mean): {reload_metrics['before_mean_ms']:.1f}ms")
    print(f"  After Reload (mean):  {reload_metrics['after_mean_ms']:.1f}ms")
    print(f"  Difference:           {reload_metrics['mean_diff_ms']:+.1f}ms ({reload_metrics['mean_diff_pct']:+.1f}%)")
    print()

    if abs(reload_metrics['mean_diff_pct']) < 5.0:
        print("✓ Hot-reload has minimal performance impact (<5%)")
    elif reload_metrics['mean_diff_pct'] < 10.0:
        print("⚠ Hot-reload has moderate performance impact (5-10%)")
    else:
        print("✗ Hot-reload has significant performance impact (>10%)")

    print("="*80 + "\n")


def write_benchmark_report(
    result: BenchmarkResult,
    total_time: float,
    reload_metrics: Optional[Dict[str, Any]],
    output_path: Path,
):
    """Write benchmark report to file."""
    benchmark_logger.info(f"Writing benchmark report to {output_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    throughput = result.count / total_time if total_time > 0 else 0.0

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("# Agent Pipeline Performance Benchmark\n\n")
        f.write(f"**Date**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

        f.write("## Summary\n\n")
        f.write(f"- Items Processed: {result.count}\n")
        f.write(f"- Total Time: {total_time:.1f}s\n")
        f.write(f"- Throughput: {throughput:.2f} items/second\n\n")

        f.write("## Latency Statistics\n\n")
        f.write("| Metric | Value (ms) |\n")
        f.write("|--------|------------|\n")
        f.write(f"| Min | {result.min:.1f} |\n")
        f.write(f"| p50 | {result.p50:.1f} |\n")
        f.write(f"| Mean | {result.mean:.1f} |\n")
        f.write(f"| Median | {result.median:.1f} |\n")
        f.write(f"| p95 | {result.p95:.1f} |\n")
        f.write(f"| p99 | {result.p99:.1f} |\n")
        f.write(f"| Max | {result.max:.1f} |\n")
        f.write(f"| StdDev | {result.stdev:.1f} |\n\n")

        f.write("## Performance Targets\n\n")
        f.write(f"- p50 < 300ms: {'✓ PASS' if result.p50 < 300 else '✗ FAIL'}\n")
        f.write(f"- p95 < 500ms: {'✓ PASS' if result.p95 < 500 else '✗ FAIL'}\n")
        f.write(f"- p99 < 1000ms: {'✓ PASS' if result.p99 < 1000 else '✗ FAIL'}\n\n")

        if reload_metrics:
            f.write("## Hot-Reload Impact\n\n")
            f.write(f"- Reload Time: {reload_metrics['reload_time_ms']:.1f}ms\n")
            f.write(f"- Before Reload (mean): {reload_metrics['before_mean_ms']:.1f}ms\n")
            f.write(f"- After Reload (mean): {reload_metrics['after_mean_ms']:.1f}ms\n")
            f.write(f"- Difference: {reload_metrics['mean_diff_ms']:+.1f}ms ({reload_metrics['mean_diff_pct']:+.1f}%)\n\n")

            if abs(reload_metrics['mean_diff_pct']) < 5.0:
                f.write("✓ Hot-reload has minimal performance impact (<5%)\n")
            elif reload_metrics['mean_diff_pct'] < 10.0:
                f.write("⚠ Hot-reload has moderate performance impact (5-10%)\n")
            else:
                f.write("✗ Hot-reload has significant performance impact (>10%)\n")

    benchmark_logger.info("Benchmark report written successfully")


async def main():
    """Main benchmark script."""
    parser = argparse.ArgumentParser(
        description="Benchmark agent pipeline performance"
    )
    parser.add_argument(
        "--items",
        type=int,
        default=1000,
        help="Number of feedback items to benchmark (default: 1000)"
    )
    parser.add_argument(
        "--test-reload",
        action="store_true",
        help="Test hot-reload performance impact"
    )
    parser.add_argument(
        "--reload-sample-size",
        type=int,
        default=10,
        help="Sample size for reload impact test (default: 10)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=f"reports/benchmark_{datetime.now().strftime('%Y-%m-%d')}.md",
        help="Output benchmark report path"
    )

    args = parser.parse_args()

    benchmark_logger.info("Starting agent pipeline benchmark")
    benchmark_logger.info(f"Items: {args.items}")
    benchmark_logger.info(f"Test Reload: {args.test_reload}")

    if settings.use_mock_data:
        benchmark_logger.warning("USE_MOCK_DATA=true - benchmark will use mock data")

    reload_metrics = None

    # Run main benchmark
    async with get_db_session() as session:
        benchmark = AgentBenchmark(session)

        # Main performance benchmark
        result, total_time = await benchmark.benchmark_batch(args.items)

        # Optional: Test reload impact
        if args.test_reload:
            reload_metrics = await benchmark.benchmark_reload_impact(
                sample_size=args.reload_sample_size
            )

    # Print summaries
    print_benchmark_summary(result, total_time)

    if reload_metrics:
        print_reload_impact_summary(reload_metrics)

    # Write report
    output_path = Path(args.output)
    write_benchmark_report(result, total_time, reload_metrics, output_path)

    benchmark_logger.info(f"Benchmark complete. Report saved to {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
