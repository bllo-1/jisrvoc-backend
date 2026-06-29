---
name: implement-verify-iterate-loop
description: Autonomous implement-verify-iterate loops for JisrVoC backend tasks with sub-agent verification and self-correction until success
---

# Loop Engineering for JisrVoC Backend

## What is Loop Engineering?

**Loop Engineering** = Autonomous agent cycles that implement → verify → iterate until a goal is achieved or human intervention is needed.

Instead of you manually prompting "now fix that error" repeatedly, the loop prompts itself until success.

## When to Use This Skill

Use loops for:
- ✅ Implementing connectors with API integration tests
- ✅ Building AI pipeline with classification validation
- ✅ Creating database migrations with up/down testing
- ✅ Deploying changes with health check verification
- ✅ Any multi-step task where verification determines next action

**Don't use for**:
- ❌ Simple one-shot tasks (just do them directly)
- ❌ Tasks requiring human judgment at each step
- ❌ Exploratory work without clear success criteria

## Core Loop Pattern

```
1. IMPLEMENT
   ↓
2. VERIFY (tests/checks)
   ↓
3. DECISION
   ├─ Success → DONE
   ├─ Fixable Error → ITERATE (back to step 1)
   └─ Blocked → ESCALATE to human
```

## Loop Anatomy for JisrVoC

### Pattern 1: Connector Implementation Loop

**Goal**: Build HubSpot connector that successfully fetches and syncs data

```yaml
Loop: HubSpot Connector
├─ Implement: Create app/connectors/hubspot.py
├─ Verify: Run integration tests against HubSpot sandbox
├─ Iterate if:
│   ├─ Rate limit errors → Add retry logic
│   ├─ Auth failures → Fix OAuth flow
│   ├─ Data transform errors → Update schema mapping
├─ Success: All tests pass + real data syncs
└─ Escalate: If blocked by missing credentials or API access
```

**Implementation**:
```markdown
LOOP START: Implement HubSpot Connector

ITERATION 1:
- Implement: Create connector following connector-development skill
- Verify: Run `pytest tests/connectors/test_hubspot.py`
- Result: 3 tests fail (auth, pagination, rate limit)

ITERATION 2:
- Implement: Fix auth by adding token refresh
- Verify: Run tests again
- Result: 2 tests fail (pagination, rate limit)

ITERATION 3:
- Implement: Fix pagination logic
- Verify: Run tests
- Result: 1 test fails (rate limit)

ITERATION 4:
- Implement: Add rate limiter with exponential backoff
- Verify: Run full test suite
- Result: ✅ ALL TESTS PASS

LOOP COMPLETE: Connector ready for production
```

### Pattern 2: AI Classification Loop

**Goal**: Classify feedback with >85% accuracy

```yaml
Loop: AI Classification
├─ Implement: Create classification prompt and pipeline
├─ Verify: Test on validation set, measure accuracy
├─ Iterate if:
│   ├─ Accuracy < 85% → Refine prompt
│   ├─ Timeout errors → Optimize batch size
│   ├─ Cost too high → Switch to cheaper model
├─ Success: Accuracy ≥ 85% + cost within budget
└─ Escalate: If fundamentally wrong approach
```

### Pattern 3: Deployment Loop

**Goal**: Deploy to Railway with healthy status

```yaml
Loop: Deploy Backend
├─ Implement: Push code to GitHub
├─ Verify: Check Railway deployment status + health endpoint
├─ Iterate if:
│   ├─ Build fails → Fix dependencies/code
│   ├─ Runtime crashes → Check logs, fix errors
│   ├─ Health check fails → Debug database/config
├─ Success: Deployment status=success + healthz returns 200
└─ Escalate: If Railway infrastructure issue
```

## How to Execute Loops

### Manual Loop (You Guide)

You orchestrate the loop:

```
You: "Implement HubSpot connector using loop pattern"

Claude: [Iteration 1]
- Created app/connectors/hubspot.py
- Running tests...
- Result: 3 failures (auth, pagination, rate limit)

You: "Continue loop"

Claude: [Iteration 2]
- Fixed auth issue
- Running tests...
- Result: 2 failures (pagination, rate limit)

You: "Continue"

Claude: [Iteration 3]
- Fixed pagination
- Running tests...
- Result: 1 failure (rate limit)

You: "Continue"

Claude: [Iteration 4]
- Added rate limiter
- Running tests...
- Result: ✅ All pass
- LOOP COMPLETE
```

### Autonomous Loop (Future: Claude Agents SDK)

Agent runs loop autonomously:

```python
# Future: Autonomous loop with Claude Agents SDK
agent = ClaudeAgent(goal="Implement HubSpot connector")

agent.loop(
    implement_fn=create_connector,
    verify_fn=run_integration_tests,
    max_iterations=10,
    escalate_on=["missing_credentials", "api_unavailable"]
)

# Agent iterates until success or escalation
```

## Verification Strategies

### 1. Test-Based Verification
```bash
# Run tests to verify implementation
pytest tests/connectors/test_hubspot.py -v

# Success criteria: All tests pass
# Iterate if: Any test fails
```

### 2. Integration Verification
```bash
# Trigger actual API call
python -m app.scripts.test_hubspot_sync

# Success criteria: Data syncs successfully
# Iterate if: API errors, timeouts, data validation fails
```

### 3. Deployment Verification
```bash
# Check Railway deployment
railway status

# Check health endpoint
curl https://jisrvoc-backend-production.up.railway.app/api/v1/healthz

# Success criteria: Status=success + healthz=200
# Iterate if: Build fails, crashes, health check fails
```

### 4. Quality Verification
```bash
# Run AI classification on validation set
python -m app.scripts.validate_classification

# Success criteria: Accuracy ≥ 85%
# Iterate if: Below threshold
```

## State Management (Loop Memory)

Track loop state to maintain context across iterations:

```yaml
# .loop-state.yml
task: "Implement HubSpot Connector"
iteration: 4
status: in_progress
history:
  - iteration: 1
    action: "Created connector base"
    result: "3 test failures"
  - iteration: 2
    action: "Fixed auth"
    result: "2 test failures"
  - iteration: 3
    action: "Fixed pagination"
    result: "1 test failure"
  - iteration: 4
    action: "Added rate limiter"
    result: "Testing..."
success_criteria:
  - "All integration tests pass"
  - "Syncs 100 tickets successfully"
  - "No rate limit errors"
```

## Escalation Criteria

Stop loop and escalate to human when:

1. **Blocked by External Dependency**
   - Missing API credentials
   - Service unavailable
   - Quota exceeded

2. **Fundamental Design Issue**
   - Wrong approach chosen
   - Architecture change needed
   - Requirements unclear

3. **Iteration Limit Reached**
   - Max iterations exceeded (usually 5-10)
   - No progress being made

4. **Safety Concern**
   - Risk of data loss
   - Production impact possible
   - Security implications

## Loop Templates

### Template 1: Feature Implementation Loop

```
Goal: Implement [feature name]

Success Criteria:
- [ ] Code follows architecture patterns
- [ ] Unit tests pass (>80% coverage)
- [ ] Integration tests pass
- [ ] Manual testing confirms functionality
- [ ] Documentation updated

Iteration Limit: 8
Escalate If: Design change needed, blocked by dependency

LOOP START
```

### Template 2: Bug Fix Loop

```
Goal: Fix [bug description]

Success Criteria:
- [ ] Bug no longer reproduces
- [ ] Regression tests added
- [ ] Related tests still pass
- [ ] Root cause documented

Iteration Limit: 5
Escalate If: Root cause unknown, requires architecture change

LOOP START
```

### Template 3: Optimization Loop

```
Goal: Optimize [component] for [metric]

Success Criteria:
- [ ] [Metric] improved by [target]%
- [ ] No functionality regression
- [ ] Performance tests pass
- [ ] Resource usage acceptable

Iteration Limit: 10
Escalate If: Fundamental bottleneck, requires infrastructure change

LOOP START
```

## Example: Real Loop for Phase 1

Let's use a loop to implement the OpenAI classification pipeline:

```
TASK: Implement OpenAI classification for feedback

SUCCESS CRITERIA:
- Classification endpoint works
- Accuracy ≥ 85% on validation set
- Latency < 2 seconds
- Cost < $0.01 per classification
- Error handling for rate limits

MAX ITERATIONS: 8
ESCALATE IF: OpenAI API unavailable, accuracy fundamentally low

--- ITERATION 1 ---
IMPLEMENT:
- Created app/ai/classification.py
- Implemented FeedbackClassifier class
- Added classification prompt

VERIFY:
$ python -m app.scripts.test_classification
Result: 76% accuracy (below threshold)
Issue: Prompt too vague, misclassifies feature requests

DECISION: Iterate (refine prompt)

--- ITERATION 2 ---
IMPLEMENT:
- Refined prompt with examples
- Added category definitions
- Improved instruction clarity

VERIFY:
$ python -m app.scripts.test_classification
Result: 88% accuracy (above threshold!)
Latency: 3.2 seconds (above threshold)

DECISION: Iterate (optimize latency)

--- ITERATION 3 ---
IMPLEMENT:
- Switched to gpt-4o-mini (faster model)
- Reduced max_tokens from 500 to 200
- Added caching for repeated text

VERIFY:
$ python -m app.scripts.test_classification
Result: 87% accuracy (✓)
Latency: 1.4 seconds (✓)
Cost: $0.008 per call (✓)

DECISION: Success! All criteria met.

--- LOOP COMPLETE ---
Ready for production deployment.
```

## Best Practices

1. **Clear Success Criteria**
   - Define objective, measurable goals
   - Document acceptance criteria upfront

2. **Fast Verification**
   - Keep verify step under 1 minute when possible
   - Use unit tests before integration tests

3. **Incremental Progress**
   - Fix one issue per iteration
   - Don't try to fix everything at once

4. **State Tracking**
   - Document what was tried
   - Track iteration count
   - Note remaining issues

5. **Know When to Escalate**
   - Don't iterate endlessly
   - Recognize fundamental blockers
   - Ask for human judgment when stuck

## Integration with Existing Skills

Loops work best when combined with skills:

```
Loop: Implement HubSpot Connector
├─ Use: connector-development skill (patterns)
├─ Use: project-context skill (architecture)
├─ Use: railway-deployment skill (when deploying)
└─ Verify: Run tests, deploy to Railway, check logs
```

## Future: Autonomous Loops

Phase 2-3 will add fully autonomous loops:
- Scheduled loops (daily sync checks)
- CI/CD loops (deploy → test → rollback if fail)
- Monitoring loops (detect issues → auto-fix)

For now, we use **manual loops** where you guide iterations.

## Related Skills

- `project-context` - Architecture for loop implementations
- `connector-development` - Verification patterns for connectors
- `ai-pipeline` - Verification patterns for AI quality
- `railway-deployment` - Verification patterns for deployments

## Quick Start

Try a simple loop:

```
You: "Use loop pattern to add alembic migration for embeddings column"

Claude:
LOOP START: Add Embeddings Migration

ITERATION 1:
- Created migration file
- Verify: alembic upgrade head
- Result: Success ✓

LOOP COMPLETE (1 iteration)
```

Then graduate to complex loops:

```
You: "Use loop pattern to implement HubSpot connector with full test coverage"

Claude:
[Runs 5-6 iterations fixing auth, pagination, rate limits, tests]

LOOP COMPLETE: Connector production-ready
```

---

**Remember**: Loops amplify judgment. Stay engaged as the engineer, not just the person who presses go.
