# Agent Pipeline Validation Scripts

This directory contains scripts for validating and benchmarking the agent-based classification pipeline against the existing LLM-based pipeline.

## Scripts Overview

### 1. `compare_pipelines.py` - Pipeline Comparison

Compares old LLM pipeline with new agent pipeline on real feedback data.

**What it does**:
- Fetches N recent feedback items from database
- Runs both old and new pipelines on each item
- Compares product area classifications
- Measures execution time differences
- Identifies disagreement patterns

**Usage**:
```bash
# Compare 100 feedback items
python scripts/compare_pipelines.py --limit 100

# Compare 50 items with custom output path
python scripts/compare_pipelines.py --limit 50 --output reports/my_comparison.csv
```

**Output**:
- CSV file with detailed comparison for each item
- Console summary with metrics:
  - Product area agreement rate (target: >95%)
  - Average confidence difference
  - Execution time comparison (speedup factor)
  - Compliance detection rate
  - Top disagreement patterns

**Example output**:
```
================================================================================
PIPELINE COMPARISON METRICS
================================================================================
Total Comparisons: 100
Product Area Agreement Rate: 92.0% (target: >95%)
  - Matches: 92
  - Disagreements: 8

Average Confidence Difference (Agent - Old): +0.156

Execution Time Comparison:
  - Old Pipeline: 1847.3ms
  - Agent Pipeline: 245.1ms
  - Speedup Factor: 7.54x

Compliance Detection (Agent-only feature):
  - Detected: 23 items (23.0%)

Top Disagreement Patterns:
  - billing → Finance: 3 times
  - api → Integrations: 2 times
  - leave → Attendance & Leaves: 2 times
================================================================================
```

---

### 2. `test_agent_accuracy.py` - Accuracy Testing

Tests agent pipeline accuracy against human-labeled ground truth data.

**What it does**:
- Loads labeled test dataset (CSV with ground truth)
- Runs agent pipeline on each test case
- Calculates accuracy, precision, recall, F1 per product area
- Identifies which rules/areas have lowest accuracy

**Usage**:

**Step 1: Create label template**
```bash
# Generate template CSV with 50 feedback items for human labeling
python scripts/test_agent_accuracy.py --create-labels --limit 50
```

This creates `data/test_labels_template_YYYY-MM-DD.csv` with columns:
- `feedback_id`
- `raw_text`
- `expected_product_area` (empty - you fill this)
- `expected_compliance` (empty - you fill this)
- `expected_compliance_tags` (empty - you fill this)
- `notes` (optional)

**Step 2: Label the data**

Open the template CSV and fill in the expected values based on your domain knowledge.

**Step 3: Run accuracy test**
```bash
# Test accuracy against labeled data
python scripts/test_agent_accuracy.py --test-data data/my_labeled_data.csv
```

**Output**:
- CSV file with detailed results for each test case
- Per-area metrics (precision, recall, F1)
- Console summary identifying lowest-accuracy areas

**Example output**:
```
================================================================================
AGENT ACCURACY METRICS
================================================================================
Total Test Cases: 50
Overall Accuracy: 88.0% (44/50 correct)
Compliance Detection Accuracy: 94.0% (47/50 correct)

Per Product Area:
Area                           Precision    Recall       F1 Score
--------------------------------------------------------------------------------
Payroll                        95.0%        95.0%        0.950
Attendance & Leaves            90.0%        85.0%        0.875
Finance                        85.0%        90.0%        0.874
Integrations                   80.0%        80.0%        0.800
Employee Lifecycle             75.0%        70.0%        0.724

Lowest Accuracy Areas (potential rule improvements needed):
  - Other / Unclassified: F1=0.500 (Precision=60.0%, Recall=50.0%)
  - Mobile: F1=0.667 (Precision=66.7%, Recall=66.7%)
================================================================================
```

---

### 3. `benchmark_agents.py` - Performance Benchmark

Benchmarks agent pipeline performance (latency, throughput).

**What it does**:
- Runs agent pipeline on N feedback items
- Measures execution time for each (p50, p95, p99)
- Calculates throughput (items/second)
- Tests hot-reload impact on performance

**Usage**:
```bash
# Basic benchmark (1000 items)
python scripts/benchmark_agents.py --items 1000

# Benchmark with reload test
python scripts/benchmark_agents.py --items 100 --test-reload
```

**Output**:
- Markdown report with latency percentiles
- Throughput metrics
- Performance target validation (p50 < 300ms, p95 < 500ms, p99 < 1000ms)
- Hot-reload impact (if tested)

**Example output**:
```
================================================================================
AGENT PIPELINE PERFORMANCE BENCHMARK
================================================================================
Items Processed: 1000
Total Time: 245.3s
Throughput: 4.08 items/second

Latency Statistics (milliseconds):
  Min:         123.4ms
  p50:         238.7ms
  Mean:        245.3ms
  Median:      239.1ms
  p95:         412.3ms
  p99:         678.9ms
  Max:         892.1ms
  StdDev:       89.2ms

Performance Targets:
  p50 < 300ms:  ✓ PASS
  p95 < 500ms:  ✓ PASS
  p99 < 1000ms: ✓ PASS
================================================================================
```

---

### 4. `generate_validation_report.py` - PM-Facing Report

Generates a human-readable markdown report for Product Managers.

**What it does**:
- Analyzes sample feedback items with both pipelines
- Groups examples into categories:
  - Agreement cases (both pipelines agree)
  - Disagreement cases (pipelines differ)
  - Compliance detection examples
  - Theme matching examples
- Provides detailed reasoning for each classification
- Highlights agent advantages (transparency, compliance, speed)

**Usage**:
```bash
# Generate report with 20 samples
python scripts/generate_validation_report.py --samples 20

# Custom output path
python scripts/generate_validation_report.py --samples 30 --output docs/my_report.md
```

**Output**:
- Markdown report with:
  - Executive summary
  - Sample classifications with reasoning
  - Disagreement analysis
  - Compliance detection examples
  - Theme matching quality
  - Recommendations

**Report sections**:
1. **Executive Summary**: Key improvements of agent pipeline
2. **Agreement Cases**: Examples where both pipelines agree
3. **Disagreement Cases**: Examples with detailed reasoning for differences
4. **Compliance Detection**: Agent-only feature examples
5. **Theme Matching Examples**: LINK vs CREATE decisions
6. **Recommendations**: Next steps based on validation results

---

## Prerequisites

1. **Database**: PostgreSQL with feedback and themes tables
2. **Environment Variables**: Set in `.env`:
   ```bash
   DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/jisrvoc
   OPENAI_API_KEY=sk-...  # For old pipeline comparison
   AGENT_ENRICHMENT_ENABLED=true
   ```
3. **Python Dependencies**: Install from `requirements.txt`

---

## Common Workflows

### Workflow 1: Initial Validation (Before Production)

```bash
# Step 1: Compare pipelines on recent data
python scripts/compare_pipelines.py --limit 100

# Step 2: Generate PM-facing report
python scripts/generate_validation_report.py --samples 20

# Step 3: Run performance benchmark
python scripts/benchmark_agents.py --items 1000

# Review outputs:
# - reports/comparison_YYYY-MM-DD.csv
# - docs/validation_report_YYYY-MM-DD.md
# - reports/benchmark_YYYY-MM-DD.md
```

### Workflow 2: Rule Refinement Testing

After updating YAML rules in `app/config/rules/`:

```bash
# Step 1: Create labeled test set (one-time)
python scripts/test_agent_accuracy.py --create-labels --limit 50
# (Fill in expected values manually)

# Step 2: Test accuracy
python scripts/test_agent_accuracy.py --test-data data/my_labels.csv

# Step 3: Iterate on rules based on low-accuracy areas
# Edit app/config/rules/*.yaml

# Step 4: Retest
python scripts/test_agent_accuracy.py --test-data data/my_labels.csv

# Compare accuracy improvements
```

### Workflow 3: Performance Regression Testing

After code changes:

```bash
# Benchmark current performance
python scripts/benchmark_agents.py --items 1000 --output reports/benchmark_before.md

# Make code changes...

# Benchmark again
python scripts/benchmark_agents.py --items 1000 --output reports/benchmark_after.md

# Compare reports to ensure no regression
```

---

## Output Directories

Scripts create the following directories for outputs:

- `reports/` - CSV and markdown benchmark reports
- `docs/` - PM-facing validation reports
- `data/` - Labeled test datasets

---

## Troubleshooting

### Error: "No module named 'app'"

Make sure you're running from the project root:
```bash
cd /Users/jisr4/Desktop/JisrVoC/jisrvoc-backend
python scripts/compare_pipelines.py
```

### Error: "Database connection failed"

Check your `.env` file has correct `DATABASE_URL`:
```bash
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/jisrvoc
```

Test connection:
```bash
psql -h localhost -U user -d jisrvoc
```

### Error: "Old pipeline failed: API key not found"

The old pipeline needs OpenAI API key for LLM calls:
```bash
# In .env
OPENAI_API_KEY=sk-...
```

### Error: "Not enough feedback items"

The database needs feedback data. Check:
```bash
python -c "
from app.db.session import get_db_session
from app.repositories.feedback import FeedbackRepository
import asyncio

async def check():
    async with get_db_session() as session:
        repo = FeedbackRepository(session)
        items, total = await repo.list_all(limit=10, offset=0)
        print(f'Found {total} feedback items')

asyncio.run(check())
"
```

### Mock Data Mode

If `USE_MOCK_DATA=true`, scripts will work but with limited data. For production validation, use real database:
```bash
USE_MOCK_DATA=false
```

---

## Performance Targets

The agent pipeline should meet these targets:

- **Accuracy**: >95% product area agreement with old pipeline
- **Latency**:
  - p50 < 300ms
  - p95 < 500ms
  - p99 < 1000ms
- **Throughput**: >3 items/second (on typical hardware)
- **Hot-Reload Impact**: <5% performance degradation

---

## Notes

1. **LLM Costs**: `compare_pipelines.py` makes LLM API calls for the old pipeline. Be aware of API costs when running on large datasets.

2. **Execution Time**: Benchmarking 1000 items takes ~5-10 minutes depending on hardware and database performance.

3. **Sampling**: Validation report uses random sampling. Run multiple times for different perspectives.

4. **Ground Truth**: Accuracy testing requires human-labeled data. Invest time in creating high-quality labels for best results.

---

## Advanced Usage

### Custom Product Area Mapping

Edit the `PRODUCT_AREA_MAPPING` dictionary in each script to adjust how old pipeline areas map to new taxonomy:

```python
PRODUCT_AREA_MAPPING = {
    "billing": "Finance",
    "custom_area": "Your New Area",
    # ...
}
```

### Filtering by Source

Modify scripts to filter by feedback source:

```python
# In compare_pipelines.py
feedback_items, total = await self.feedback_repo.list_all(
    limit=limit,
    offset=0,
    source="zendesk",  # Add this parameter
)
```

### Parallel Execution

For faster benchmarking, modify `benchmark_agents.py` to process items in parallel using `asyncio.gather()`.

---

## Questions?

See documentation:
- `docs/agent_orchestrator_integration.md` - Agent pipeline architecture
- `docs/validation_report_*.md` - Sample validation reports
- `app/config/rules/*.yaml` - Classification rules

Or check logs:
```bash
tail -f logs/jisrvoc.log
```
