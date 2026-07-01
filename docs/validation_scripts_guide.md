# Agent Pipeline Validation Scripts - Complete Guide

## Overview

This guide documents the validation and testing infrastructure for the agent-based classification pipeline. These scripts enable comprehensive comparison with the existing LLM pipeline, accuracy testing, performance benchmarking, and PM-facing reporting.

## Scripts Summary

| Script | Purpose | Output | Runtime |
|--------|---------|--------|---------|
| `compare_pipelines.py` | Compare old vs new pipeline | CSV + metrics | ~5-10 min (100 items) |
| `test_agent_accuracy.py` | Test against labeled data | CSV + accuracy report | ~2-5 min (50 items) |
| `benchmark_agents.py` | Performance benchmarking | Markdown report | ~5-15 min (1000 items) |
| `generate_validation_report.py` | PM-facing report | Markdown report | ~3-7 min (20 samples) |

---

## 1. compare_pipelines.py

### Purpose
Compare the old LLM-based classification pipeline with the new agent-based pipeline on real production feedback data.

### Key Features
- **Side-by-side comparison**: Runs both pipelines on the same feedback items
- **Product area mapping**: Normalizes old free-form areas to new structured taxonomy
- **Execution time tracking**: Measures and compares latency for each pipeline
- **Disagreement analysis**: Identifies patterns where pipelines classify differently
- **Compliance detection**: Shows agent-only feature (old pipeline doesn't detect compliance)

### Usage

**Basic usage** (100 items):
```bash
python scripts/compare_pipelines.py --limit 100
```

**Custom output**:
```bash
python scripts/compare_pipelines.py --limit 50 --output reports/my_comparison_$(date +%Y-%m-%d).csv
```

### Output Files

**CSV Report** (`reports/comparison_YYYY-MM-DD.csv`):
- One row per feedback item
- Columns:
  - `feedback_id` - Unique identifier
  - `raw_text_preview` - First 200 chars of feedback
  - `old_product_area` - Old pipeline classification
  - `old_confidence` - Old pipeline confidence (0-1)
  - `old_time_ms` - Old pipeline execution time
  - `agent_product_area` - Agent pipeline classification
  - `agent_confidence` - Agent confidence (0-1)
  - `agent_time_ms` - Agent execution time
  - `normalized_old_area` - Old area mapped to new taxonomy
  - `areas_match` - YES/NO if both agree
  - `agent_action` - LINK or CREATE (theme matching)
  - `agent_compliance` - YES/NO if compliance detected
  - `agent_compliance_tags` - Comma-separated compliance tags
  - `agent_matched_theme` - Matched theme name (if LINK)
  - `agent_reasoning` - Full reasoning text

**Console Output**:
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
  - Old Pipeline: 1847.3ms (LLM API call)
  - Agent Pipeline: 245.1ms (rule-based)
  - Speedup Factor: 7.54x

Compliance Detection (Agent-only feature):
  - Detected: 23 items (23.0%)

Top Disagreement Patterns:
  - billing → Finance: 3 times
  - api → Integrations: 2 times
  - leave → Attendance & Leaves: 2 times
================================================================================
```

### Product Area Mapping

The script includes a mapping dictionary to normalize old free-form areas:

```python
PRODUCT_AREA_MAPPING = {
    "billing": "Finance",
    "payroll": "Payroll",
    "attendance": "Attendance & Leaves",
    "integration": "Integrations",
    "api": "Integrations",
    "mobile": "Mobile",
    "report": "Reports & Analytics",
    # ... etc
}
```

### Interpretation Guide

**Agreement Rate >95%**: ✅ Excellent - Agent pipeline is production-ready

**Agreement Rate 85-95%**: ⚠️ Good - Review disagreements, may need minor rule adjustments

**Agreement Rate <85%**: ⛔ Needs work - Significant rule refinement required

**Speedup Factor >5x**: ✅ Agent pipeline is significantly faster

**Compliance Detection >20%**: ✅ Agent successfully catches regulatory requirements

### Common Disagreement Patterns

1. **Old "api" → New "Integrations"**: Expected - mapping works correctly
2. **Old "billing" → New "Finance"**: Expected - taxonomy difference
3. **Old null → New "Payroll"**: Agent detects area when LLM couldn't
4. **Low agent confidence (<0.5)**: May indicate need for rule refinement

---

## 2. test_agent_accuracy.py

### Purpose
Test agent pipeline accuracy against human-labeled ground truth data. This is the gold standard for validation.

### Two-Stage Process

#### Stage 1: Create Label Template

Generate a CSV template for human labeling:

```bash
python scripts/test_agent_accuracy.py --create-labels --limit 50
```

**Output**: `data/test_labels_template_YYYY-MM-DD.csv`

**Template columns**:
- `feedback_id` - Pre-filled
- `raw_text` - Pre-filled
- `expected_product_area` - **YOU FILL THIS** (e.g., "Payroll")
- `expected_compliance` - **YOU FILL THIS** (true/false)
- `expected_compliance_tags` - **YOU FILL THIS** (e.g., "GOSI,WPS")
- `notes` - **OPTIONAL** (any observations)

#### Stage 2: Run Accuracy Test

After filling in expected values:

```bash
python scripts/test_agent_accuracy.py --test-data data/my_labeled_data.csv
```

### Output Files

**CSV Report** (`reports/accuracy_YYYY-MM-DD.csv`):

**Part 1: Individual Results**
- One row per test case
- Shows expected vs predicted
- Indicates if correct
- Includes agent reasoning

**Part 2: Metrics by Product Area**
- Precision, Recall, F1 for each area
- True positives, false positives, false negatives

**Console Output**:
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

### Metrics Explained

- **Precision**: Of all items classified as Area X, what % were actually Area X?
- **Recall**: Of all items that should be Area X, what % did we correctly identify?
- **F1 Score**: Harmonic mean of precision and recall (0-1, higher is better)

### Labeling Guidelines

When creating ground truth labels:

1. **Use exact taxonomy names** from `app/config/rules/taxonomy.yaml`:
   - "Payroll"
   - "Attendance & Leaves"
   - "Finance"
   - "Employee Lifecycle"
   - "Integrations"
   - "Mobile"
   - "Reports & Analytics"
   - "Security & Access Control"
   - "Compliance & Localization"
   - "Platform & Issues"
   - "PMS (Performance Management)"
   - "Document Management"
   - "Other / Unclassified"

2. **Compliance detection**:
   - Set `expected_compliance` = `true` if feedback mentions:
     - GOSI, WPS, PDPL, Mudad, Qiwa, Sehhaty
     - Social insurance, wage protection, data privacy
   - Set `expected_compliance_tags` = comma-separated list (e.g., "GOSI,WPS")

3. **Edge cases**:
   - If truly ambiguous, pick the most dominant area
   - Document reasoning in `notes` column
   - Multiple areas? Pick primary one

### Iterative Refinement Workflow

```bash
# 1. Create labels (one-time)
python scripts/test_agent_accuracy.py --create-labels --limit 50
# Fill in expected values...

# 2. Test current accuracy
python scripts/test_agent_accuracy.py --test-data data/my_labels.csv

# 3. Identify low-accuracy areas from report
# Example: "Mobile: F1=0.667"

# 4. Refine rules
# Edit app/config/rules/taxonomy.yaml - add more keywords for "Mobile"

# 5. Retest
python scripts/test_agent_accuracy.py --test-data data/my_labels.csv

# 6. Compare F1 scores - did they improve?
```

---

## 3. benchmark_agents.py

### Purpose
Measure agent pipeline performance characteristics (latency, throughput) and test hot-reload impact.

### Usage

**Basic benchmark** (1000 items):
```bash
python scripts/benchmark_agents.py --items 1000
```

**With hot-reload test**:
```bash
python scripts/benchmark_agents.py --items 100 --test-reload --reload-sample-size 10
```

### Output Files

**Markdown Report** (`reports/benchmark_YYYY-MM-DD.md`):
- Latency percentiles (p50, p95, p99)
- Throughput (items/second)
- Performance target validation
- Hot-reload impact (if tested)

**Console Output**:
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

### Performance Targets

| Metric | Target | Rationale |
|--------|--------|-----------|
| p50 | < 300ms | Most requests complete quickly |
| p95 | < 500ms | 95% of requests under 0.5s |
| p99 | < 1000ms | Even worst cases under 1s |
| Throughput | > 3 items/sec | Can process backlog efficiently |

### Hot-Reload Impact Test

```
================================================================================
HOT-RELOAD PERFORMANCE IMPACT
================================================================================
Reload Time: 45.3ms
Execution Time Impact:
  Before Reload (mean): 238.7ms
  After Reload (mean):  242.1ms
  Difference:           +3.4ms (+1.4%)

✓ Hot-reload has minimal performance impact (<5%)
================================================================================
```

**Interpretation**:
- **<5% impact**: ✅ Excellent - hot-reload is production-safe
- **5-10% impact**: ⚠️ Acceptable - monitor in production
- **>10% impact**: ⛔ Investigate - rule loading may need optimization

### Regression Testing

Use benchmarking to detect performance regressions after code changes:

```bash
# Before changes
python scripts/benchmark_agents.py --items 1000 --output reports/bench_before.md

# Make code changes...

# After changes
python scripts/benchmark_agents.py --items 1000 --output reports/bench_after.md

# Compare p50/p95/p99 values
diff reports/bench_before.md reports/bench_after.md
```

---

## 4. generate_validation_report.py

### Purpose
Generate a PM-friendly markdown report with real examples and reasoning. Designed for non-technical stakeholders.

### Usage

**Generate report with 20 samples**:
```bash
python scripts/generate_validation_report.py --samples 20
```

**Custom output path**:
```bash
python scripts/generate_validation_report.py --samples 30 --output docs/validation_$(date +%Y-%m-%d).md
```

### Output Files

**Markdown Report** (`docs/validation_report_YYYY-MM-DD.md`):

**Structure**:
1. **Executive Summary**: Key improvements and capabilities
2. **Agreement Cases**: 5 examples where both pipelines agree
3. **Disagreement Cases**: 5 examples with detailed reasoning
4. **Compliance Detection**: 5 examples of compliance flagging
5. **Theme Matching**: 5 examples of LINK vs CREATE decisions
6. **Recommendations**: Next steps based on results

### Report Sections Explained

#### 1. Executive Summary
- High-level overview of agent advantages
- Key features: reasoning, compliance, theme matching, speed, cost

#### 2. Agreement Cases
- Shows where both pipelines produce same result
- Highlights agent reasoning provides additional context
- Demonstrates compliance detection even when areas match

**Example**:
```markdown
### Example 1: Payroll

**Feedback**: Employee salary calculation is incorrect after recent deduction changes...

**Old Pipeline**: payroll (category: bug)

**Agent Pipeline**: Payroll (confidence: 95.0%)

**🚨 Compliance Detected**: GOSI

**Agent Reasoning**:
```
📦 Product Area: Payroll (95% confidence)
- Keywords matched: salary, calculation, deduction
- Disambiguation: "salary calculation" → Payroll (not Finance)

✅ Compliance: GOSI detected
- Terms found: "social insurance contribution"

🎯 Decision: CREATE (no strong theme match)
```
```

#### 3. Disagreement Cases
- Shows where pipelines differ
- Agent reasoning explains why classification differs
- Often reveals agent is more accurate due to rule-based logic

**Example**:
```markdown
### Example 2: Old vs New

**Feedback**: API integration with external payroll system is failing...

**Old Pipeline**: api → Integrations (normalized)

**Agent Pipeline**: Integrations (confidence: 88.0%)

**Agent Reasoning**:
```
📦 Product Area: Integrations (88% confidence)
- Keywords: API, integration, external system
- Mental model: Connects to third-party systems

🎯 Decision: LINK to "API Integration Issues" theme
- Match score: 0.85 (above 0.70 threshold)
```

**Analysis**: Agent correctly classified with high confidence. Old pipeline used generic "api" term which maps to same area.
```

#### 4. Compliance Detection
- Agent-only feature examples
- Shows regulatory/legal requirements detection
- Critical for prioritization

#### 5. Theme Matching
- LINK examples: Agent found strong match with existing theme
- CREATE examples: Agent suggests new theme needed
- Helps consolidate feedback and identify trends

### Using the Report

**For Product Managers**:
1. Review executive summary for high-level understanding
2. Read disagreement cases to spot potential issues
3. Check compliance detection accuracy
4. Use recommendations section for next steps

**For Engineering**:
1. Review disagreement cases for rule refinement opportunities
2. Check theme matching quality
3. Validate reasoning is clear and correct
4. Identify edge cases for test coverage

**For Leadership**:
1. Executive summary shows business value
2. Performance improvements (speed, cost)
3. New capabilities (compliance, reasoning)
4. Production readiness assessment

---

## Common Workflows

### Workflow 1: Pre-Production Validation

**Goal**: Validate agent pipeline before enabling in production

```bash
# Step 1: Compare with old pipeline
python scripts/compare_pipelines.py --limit 100

# Review CSV for agreement rate >95%

# Step 2: Generate PM report
python scripts/generate_validation_report.py --samples 20

# Share docs/validation_report_*.md with PM team

# Step 3: Benchmark performance
python scripts/benchmark_agents.py --items 1000

# Verify targets met (p50 < 300ms, p95 < 500ms)

# Step 4: Create accuracy test set
python scripts/test_agent_accuracy.py --create-labels --limit 50

# Have PM team fill in expected values

# Step 5: Test accuracy
python scripts/test_agent_accuracy.py --test-data data/pm_labels.csv

# Verify >90% accuracy

# ✓ Production-ready if all checks pass
```

### Workflow 2: Rule Refinement

**Goal**: Improve accuracy in specific product areas

```bash
# Step 1: Create labeled test set (one-time)
python scripts/test_agent_accuracy.py --create-labels --limit 50
# Fill in expected values...

# Step 2: Baseline accuracy
python scripts/test_agent_accuracy.py --test-data data/test_labels.csv
# Note F1 scores per area

# Step 3: Identify low-accuracy area
# Example: "Mobile: F1=0.667"

# Step 4: Refine rules
# Edit app/config/rules/taxonomy.yaml:
#   - name: "Mobile"
#     keywords: ["mobile", "app", "ios", "android"]
#     # Add more keywords:
#     keywords: ["mobile", "app", "ios", "android", "smartphone", "tablet", "mobile app"]

# Step 5: Retest
python scripts/test_agent_accuracy.py --test-data data/test_labels.csv

# Step 6: Compare F1 scores
# Did "Mobile" F1 improve?

# Iterate until F1 >0.85 for all critical areas
```

### Workflow 3: Performance Regression Testing

**Goal**: Ensure code changes don't degrade performance

```bash
# Before changes
python scripts/benchmark_agents.py --items 1000 --output reports/bench_v1.md

# Make code changes...

# After changes
python scripts/benchmark_agents.py --items 1000 --output reports/bench_v2.md

# Compare reports
cat reports/bench_v1.md | grep "p50:"
# p50: 238.7ms

cat reports/bench_v2.md | grep "p50:"
# p50: 242.1ms

# Difference: +3.4ms (+1.4%) ✓ Acceptable
```

### Workflow 4: Continuous Monitoring

**Goal**: Monitor accuracy and performance over time

```bash
# Weekly accuracy check
python scripts/test_agent_accuracy.py --test-data data/golden_test_set.csv --output reports/accuracy_$(date +%Y-%m-%d).csv

# Monthly performance benchmark
python scripts/benchmark_agents.py --items 1000 --output reports/benchmark_$(date +%Y-%m-%d).md

# Track metrics over time:
# - Overall accuracy trend
# - Per-area F1 scores
# - p95 latency trend
# - Compliance detection rate
```

---

## Troubleshooting

### Error: "Database connection failed"

**Symptom**:
```
ERROR - Database connection failed: connection refused
```

**Solution**:
```bash
# Check PostgreSQL is running
psql -h localhost -U jisrvoc -d jisrvoc

# Check .env has correct DATABASE_URL
cat .env | grep DATABASE_URL
# DATABASE_URL=postgresql+asyncpg://jisrvoc:jisrvoc@localhost:5432/jisrvoc

# Test connection from Python
python -c "
from app.db.session import get_db_session
import asyncio

async def test():
    async with get_db_session() as session:
        print('✓ Database connection OK')

asyncio.run(test())
"
```

### Error: "Old pipeline failed: API key not found"

**Symptom**:
```
ERROR - Old pipeline failed for feedback 123: API key not found
```

**Solution**:
```bash
# Add OpenAI API key to .env
echo "OPENAI_API_KEY=sk-..." >> .env

# Verify
cat .env | grep OPENAI_API_KEY
```

### Error: "Agent enrichment not enabled"

**Symptom**:
```
ERROR - Agent enrichment is not enabled
```

**Solution**:
```bash
# Enable in .env
echo "AGENT_ENRICHMENT_ENABLED=true" >> .env

# Restart application to load orchestrator
```

### Error: "Not enough feedback items"

**Symptom**:
```
WARNING - Only 10 feedback items available (requested 100)
```

**Solution**:
```bash
# Check database has data
python -c "
from app.db.session import get_db_session
from app.repositories.feedback import FeedbackRepository
import asyncio

async def check():
    async with get_db_session() as session:
        repo = FeedbackRepository(session)
        items, total = await repo.list_all(limit=10, offset=0)
        print(f'Found {total} feedback items in database')

asyncio.run(check())
"

# If needed, seed database
python scripts/seed_phase2_data.py
```

### Performance: Scripts running very slowly

**Symptom**:
- Comparison script taking >30 minutes for 100 items
- Benchmark showing p50 > 1000ms

**Possible causes**:
1. **Database slow**: Check database performance, add indexes
2. **LLM API latency**: Old pipeline makes API calls, can be slow
3. **Network issues**: Check database connection latency

**Solutions**:
```bash
# 1. Check database query performance
# Add index on feedback.created_at if missing

# 2. Skip old pipeline for faster testing
# Modify scripts to skip old pipeline (agent-only testing)

# 3. Test with smaller sample sizes first
python scripts/benchmark_agents.py --items 100  # Instead of 1000
```

---

## Best Practices

### 1. Labeling Quality
- **Use 2+ labelers**: Inter-rater reliability check
- **Document edge cases**: Create labeling guidelines
- **Iterative refinement**: Add new test cases when errors found

### 2. Sample Selection
- **Representative mix**: Include all product areas
- **Include edge cases**: Ambiguous, multi-area feedback
- **Recent data**: Use latest feedback patterns

### 3. Report Interpretation
- **Agreement rate >95%**: Production-ready
- **F1 score >0.85**: Area is well-classified
- **Compliance detection**: Critical for legal/regulatory

### 4. Continuous Validation
- **Weekly accuracy tests**: Track trends over time
- **Monthly benchmarks**: Detect performance regressions
- **Quarterly PM reports**: Keep stakeholders informed

---

## Advanced Topics

### Custom Product Area Mapping

Edit mapping in scripts if your taxonomy changes:

```python
# In compare_pipelines.py and generate_validation_report.py
PRODUCT_AREA_MAPPING = {
    "your_old_area": "Your New Area",
    "another_old": "Another New Area",
    # ...
}
```

### Filtering by Feedback Source

Test specific connectors:

```python
# In any script's fetch logic
feedback_items, total = await self.feedback_repo.list_all(
    limit=limit,
    offset=0,
    source="zendesk",  # Only Zendesk feedback
)
```

### Parallel Execution

Speed up benchmarking with parallel processing:

```python
# In benchmark_agents.py
async def benchmark_batch_parallel(self, item_count: int):
    # Use asyncio.gather() for parallel execution
    tasks = [
        self.benchmark_single_item(f.id, f.content)
        for f in feedback_items
    ]
    results = await asyncio.gather(*tasks)
```

---

## Questions & Support

**Documentation**:
- `docs/agent_orchestrator_integration.md` - Architecture details
- `app/config/rules/*.yaml` - Classification rules
- `scripts/README.md` - Quick reference

**Logs**:
```bash
# Application logs
tail -f logs/jisrvoc.log

# Script logs (console output)
python scripts/compare_pipelines.py 2>&1 | tee comparison.log
```

**Issues**:
- Check database connection
- Verify environment variables (`.env`)
- Review error messages in console output
