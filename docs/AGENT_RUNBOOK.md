# Agent System Operations Runbook

**Audience**: DevOps, SRE, On-Call Engineers
**Purpose**: Monitor health, troubleshoot issues, tune performance
**Last Updated**: 2026-07-01

---

## Table of Contents

1. [Quick Reference](#quick-reference)
2. [Monitoring Agent Health](#monitoring-agent-health)
3. [Common Errors and Fixes](#common-errors-and-fixes)
4. [Rolling Back Bad Rules](#rolling-back-bad-rules)
5. [Performance Tuning](#performance-tuning)
6. [When to Add vs Tune Agents](#when-to-add-vs-tune-agents)
7. [Escalation Procedures](#escalation-procedures)

---

## Quick Reference

### Health Check Commands

```bash
# Check overall system health
curl https://api.jisrvoc.com/api/v1/readyz | jq

# Check agent orchestrator status
curl https://api.jisrvoc.com/api/v1/readyz | jq '.agent_pipeline'

# Check rule engine status
curl https://api.jisrvoc.com/api/v1/readyz | jq '.rule_engine'

# Get rollout metrics
curl https://api.jisrvoc.com/api/v1/readyz | jq '.agent_pipeline.metrics'
```

### Emergency Actions

```bash
# Disable agent pipeline immediately
export AGENT_ROLLOUT_PERCENTAGE=0
systemctl restart jisrvoc-api

# Rollback to old LLM pipeline
export AGENT_ENRICHMENT_ENABLED=false
systemctl restart jisrvoc-api

# Reload rules after fix
curl -X POST https://api.jisrvoc.com/api/v1/feedback/admin/reload-rules
```

### Log Locations

```bash
# Application logs
tail -f /var/log/jisrvoc/app.log

# Agent execution logs
grep "Agent execution" /var/log/jisrvoc/app.log

# Error logs
grep "ERROR" /var/log/jisrvoc/app.log | grep -i agent

# Performance logs
grep "execution_time_ms" /var/log/jisrvoc/app.log
```

---

## Monitoring Agent Health

### Health Check Endpoint

**Endpoint**: `GET /api/v1/readyz`

**Healthy Response**:

```json
{
  "status": "ready",
  "environment": "production",
  "checks": {
    "database": "ok",
    "redis": "ok",
    "agent_orchestrator": {
      "status": "ok",
      "agent_count": 3,
      "agents": ["triage", "llm", "embedding"]
    }
  },
  "agent_pipeline": {
    "enabled": true,
    "rollout_percentage": 100,
    "metrics": {
      "total_requests": 10000,
      "agent_requests": 10000,
      "old_pipeline_requests": 0,
      "agent_percentage": 100.0,
      "agent_success_rate": 0.96,
      "agent_error_count": 400,
      "agent_avg_execution_time_ms": 142.5,
      "old_avg_execution_time_ms": 0.0,
      "speedup_factor": 0.0,
      "uptime_seconds": 86400
    }
  },
  "rule_engine": {
    "status": "ok",
    "disambiguation_rules": 45,
    "compliance_regulations": 13,
    "l1_scopes": 18,
    "last_loaded": "2026-07-01T10:00:00Z"
  }
}
```

### Key Metrics to Monitor

| Metric | Healthy Range | Alert Threshold | Action |
|--------|---------------|-----------------|--------|
| `agent_success_rate` | >0.95 | <0.90 | Investigate errors |
| `agent_error_count` | <5% of total | >10% | Check logs, possibly rollback |
| `agent_avg_execution_time_ms` | <200ms | >500ms | Performance tuning needed |
| `rule_engine.status` | "ok" | "error" | Fix YAML syntax |
| `agent_orchestrator.status` | "ok" | "error" | Check agent initialization |

### Monitoring Dashboards

#### 1. Request Volume Dashboard

**Query**: Track agent vs old pipeline traffic

```bash
# Prometheus query
sum(rate(agent_requests_total[5m])) by (pipeline_type)
```

**Expected**:
- At 100% rollout: All traffic to agent pipeline
- At 50% rollout: Roughly equal split

#### 2. Error Rate Dashboard

**Query**: Track agent error rate

```bash
# Prometheus query
sum(rate(agent_errors_total[5m])) / sum(rate(agent_requests_total[5m]))
```

**Alert Rule**:
```yaml
- alert: HighAgentErrorRate
  expr: agent_error_rate > 0.10
  for: 5m
  annotations:
    summary: "Agent error rate >10% for 5 minutes"
    description: "Check logs: grep ERROR /var/log/jisrvoc/app.log | grep agent"
```

#### 3. Latency Dashboard

**Query**: Track p50, p95, p99 latencies

```bash
# Prometheus query
histogram_quantile(0.95, sum(rate(agent_execution_time_ms_bucket[5m])) by (le, agent_name))
```

**Alert Rule**:
```yaml
- alert: SlowAgentPipeline
  expr: agent_execution_time_p95 > 500
  for: 10m
  annotations:
    summary: "Agent pipeline p95 latency >500ms"
    description: "Check performance: grep execution_time_ms /var/log/jisrvoc/app.log"
```

---

## Common Errors and Fixes

### Error 1: Agent Orchestrator Not Initialized

**Symptoms**:

```json
{
  "checks": {
    "agent_orchestrator": "not_initialized"
  },
  "status": "degraded"
}
```

**Logs**:

```
ERROR Failed to initialize agent orchestrator: No module named 'app.agents'
```

**Root Cause**: Agent code not deployed or import error

**Fix**:

1. Check agent modules exist:
   ```bash
   ls -l /app/agents/
   # Should see: __init__.py, base_agent.py, orchestrator.py, triage_agent.py, llm_agent.py, embedding_agent.py
   ```

2. Check Python imports:
   ```bash
   python -c "from app.agents.orchestrator import AgentOrchestrator"
   ```

3. Restart application:
   ```bash
   systemctl restart jisrvoc-api
   ```

4. Verify health:
   ```bash
   curl https://api.jisrvoc.com/api/v1/readyz | jq '.checks.agent_orchestrator'
   ```

### Error 2: Rule Engine Failed to Load

**Symptoms**:

```json
{
  "rule_engine": {
    "error": "YAML syntax error: mapping values are not allowed here"
  },
  "status": "degraded"
}
```

**Logs**:

```
ERROR Failed to load rules: YAML syntax error at line 23
```

**Root Cause**: Invalid YAML syntax in rules file

**Fix**:

1. Validate YAML syntax:
   ```bash
   python -c "import yaml; yaml.safe_load(open('app/agents/rules/disambiguation.yaml'))"
   ```

2. Common YAML errors:
   - Missing colon: `keywords_en` instead of `keywords_en:`
   - Incorrect indentation (use 2 spaces, not tabs)
   - Missing quotes around special characters

3. Rollback to last known good version:
   ```bash
   git checkout HEAD~1 -- app/agents/rules/
   curl -X POST https://api.jisrvoc.com/api/v1/feedback/admin/reload-rules
   ```

4. Verify reload:
   ```bash
   curl https://api.jisrvoc.com/api/v1/readyz | jq '.rule_engine.status'
   # Should return: "ok"
   ```

### Error 3: High Agent Error Rate

**Symptoms**:

```json
{
  "agent_pipeline": {
    "metrics": {
      "agent_success_rate": 0.72,
      "agent_error_count": 2800
    }
  }
}
```

**Logs**:

```
ERROR Agent llm failed: OpenAI API error: Rate limit exceeded
```

**Root Cause**: OpenAI API rate limit or outage

**Fix**:

1. Check OpenAI status:
   ```bash
   curl https://status.openai.com/api/v2/status.json
   ```

2. If OpenAI is down, **rollback to 0%** immediately:
   ```bash
   export AGENT_ROLLOUT_PERCENTAGE=0
   systemctl restart jisrvoc-api
   ```

3. If rate limited, increase timeout or add retry logic:
   ```bash
   # In deployment config
   OPENAI_REQUEST_TIMEOUT=60
   OPENAI_MAX_RETRIES=3
   ```

4. Monitor recovery:
   ```bash
   watch -n 5 'curl -s https://api.jisrvoc.com/api/v1/readyz | jq ".agent_pipeline.metrics.agent_success_rate"'
   ```

### Error 4: Database Connection Timeout

**Symptoms**:

```json
{
  "checks": {
    "database": "error: connection timeout"
  },
  "status": "degraded"
}
```

**Logs**:

```
ERROR Agent embedding failed: asyncpg.exceptions.ConnectionTimeoutError
```

**Root Cause**: PostgreSQL overloaded or network issue

**Fix**:

1. Check database health:
   ```bash
   psql -h db.jisrvoc.com -U jisrvoc -c "SELECT COUNT(*) FROM feedback;"
   ```

2. Check connection pool:
   ```bash
   psql -h db.jisrvoc.com -U jisrvoc -c "SELECT * FROM pg_stat_activity WHERE datname='jisrvoc';"
   ```

3. Increase pool size if needed:
   ```bash
   # In deployment config
   DATABASE_POOL_SIZE=20  # Increase from 10
   DATABASE_MAX_OVERFLOW=40  # Increase from 20
   ```

4. Add read replica for embedding agent:
   ```bash
   # In deployment config
   DATABASE_READ_REPLICA_URL=postgresql://user:pass@read-replica.jisrvoc.com/jisrvoc
   ```

### Error 5: Theme Embedding Search Timeout

**Symptoms**:

```
Agent embedding execution time: 2500ms (p95)
```

**Logs**:

```
WARN Agent embedding slow: theme search took 2.3s
```

**Root Cause**: Missing pgvector index or too many themes

**Fix**:

1. Check if index exists:
   ```sql
   SELECT indexname, indexdef
   FROM pg_indexes
   WHERE tablename = 'themes'
   AND indexname LIKE '%embedding%';
   ```

2. Create index if missing:
   ```sql
   CREATE INDEX idx_themes_embedding ON themes USING ivfflat (embedding vector_cosine_ops)
   WITH (lists = 100);
   ```

3. Tune index parameters:
   ```sql
   -- For 10,000 themes
   ALTER INDEX idx_themes_embedding SET (lists = 100);

   -- For 100,000 themes
   ALTER INDEX idx_themes_embedding SET (lists = 1000);
   ```

4. Add caching layer:
   ```bash
   # In deployment config
   ENABLE_EMBEDDING_CACHE=true
   EMBEDDING_CACHE_TTL=3600  # 1 hour
   ```

---

## Rolling Back Bad Rules

### Scenario: Rules Causing Misclassification

**Example**: Added keyword "leave" to Business Trip scope, now Leave Management feedback is miscategorized.

#### Step 1: Identify Bad Rule

Check recent changes:

```bash
git log --oneline app/agents/rules/
git diff HEAD~1 app/agents/rules/disambiguation.yaml
```

#### Step 2: Rollback Specific File

```bash
# Rollback single file
git checkout HEAD~1 -- app/agents/rules/disambiguation.yaml

# Verify change
git diff app/agents/rules/disambiguation.yaml
```

#### Step 3: Hot-Reload Rules

```bash
curl -X POST https://api.jisrvoc.com/api/v1/feedback/admin/reload-rules
```

Expected response:

```json
{
  "success": true,
  "message": "Rules reloaded successfully",
  "agent_status": {
    "rule_engine": {
      "disambiguation_rules": 45,
      "last_loaded": "2026-07-01T15:45:00Z"
    }
  }
}
```

#### Step 4: Verify Fix

Test with affected feedback:

```bash
curl -X POST "https://api.jisrvoc.com/api/v1/feedback/enrich?feedback_id=12345" | jq '.enrichment.product_area'
```

Check logs for correct classification:

```bash
grep "feedback_id.*12345" /var/log/jisrvoc/app.log | grep "product_area"
```

#### Step 5: Commit Rollback

```bash
git add app/agents/rules/disambiguation.yaml
git commit -m "Rollback: Remove 'leave' from business_trip scope"
git push origin main
```

### Scenario: Complete Rule Disaster

If multiple rules are broken and causing widespread issues:

#### Emergency Rollback to Previous Version

```bash
# Rollback all rule files
git checkout HEAD~5 -- app/agents/rules/

# Reload rules
curl -X POST https://api.jisrvoc.com/api/v1/feedback/admin/reload-rules

# Verify health
curl https://api.jisrvoc.com/api/v1/readyz | jq '.rule_engine'
```

#### If Rollback Fails, Disable Agent Pipeline

```bash
# Immediate: Set rollout to 0%
export AGENT_ROLLOUT_PERCENTAGE=0
systemctl restart jisrvoc-api

# Verify old pipeline active
curl https://api.jisrvoc.com/api/v1/readyz | jq '.agent_pipeline.rollout_percentage'
# Should return: 0
```

---

## Performance Tuning

### Identifying Performance Bottlenecks

#### 1. Check Per-Agent Timing

```bash
# Grep logs for execution times
grep "execution_time_ms" /var/log/jisrvoc/app.log | awk '{print $NF}' | sort -n | tail -20
```

Look for outliers (>1000ms).

#### 2. Profile Slow Requests

```bash
# Find slow enrichment requests
grep "enrich_feedback" /var/log/jisrvoc/app.log | grep -E "duration_ms\":[5-9][0-9]{2,}" | head -10
```

Get feedback IDs of slow requests, then test individually:

```bash
time curl -X POST "https://api.jisrvoc.com/api/v1/feedback/enrich?feedback_id=SLOW_ID" | jq '.agent_results[].execution_time_ms'
```

### Tuning LLM Agent (Slowest Component)

**Current**: ~180ms average

**Optimization 1**: Use Faster Model

```bash
# In deployment config
OPENAI_MODEL=gpt-3.5-turbo  # Switch from gpt-4 (faster, cheaper, slightly less accurate)
```

**Before**:
- Model: GPT-4
- Latency: ~180ms
- Cost: $0.01/request

**After**:
- Model: GPT-3.5 Turbo
- Latency: ~80ms
- Cost: $0.002/request

**Optimization 2**: Reduce Prompt Size

```python
# app/agents/llm_agent.py

# Before (long prompt)
prompt = f"""
Analyze this feedback in detail. Consider sentiment, urgency, category...
[Long instructions, 500 tokens]
Feedback: {raw_text}
"""

# After (short prompt)
prompt = f"""
Classify: sentiment, urgency, category.
Feedback: {raw_text}
"""
```

**Optimization 3**: Add Prompt Caching (Anthropic only)

```python
# If using Claude via Anthropic API
completion = await anthropic.messages.create(
    model="claude-3-5-sonnet-20241022",
    max_tokens=1024,
    system=[{
        "type": "text",
        "text": "<system prompt>",
        "cache_control": {"type": "ephemeral"}  # Cache system prompt
    }],
    messages=[{"role": "user", "content": feedback_text}],
)
```

### Tuning Embedding Agent

**Current**: ~60ms average

**Optimization 1**: Add Redis Caching

```python
# app/agents/embedding_agent.py

from app.core.cache import get_redis
import json

async def _get_similar_themes(self, embedding):
    """Cache theme search results."""
    cache_key = f"embedding:themes:{hash(tuple(embedding))}"

    # Check cache
    cached = get_redis().get(cache_key)
    if cached:
        return json.loads(cached)

    # Query database
    themes = await self.theme_repository.search_similar(embedding)

    # Cache for 1 hour
    get_redis().setex(cache_key, 3600, json.dumps(themes))

    return themes
```

**Before**: 60ms average (every request hits database)
**After**: 5ms cached, 60ms miss (90% hit rate = 10ms average)

**Optimization 2**: Optimize pgvector Index

```sql
-- Check current index configuration
SELECT * FROM pg_indexes WHERE indexname = 'idx_themes_embedding';

-- Tune for better performance (trade-off: slightly lower recall)
DROP INDEX idx_themes_embedding;
CREATE INDEX idx_themes_embedding ON themes USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 200);  -- Increase lists for better performance

-- Set probes for faster search
SET ivfflat.probes = 5;  -- Lower probes = faster but less accurate
```

### Tuning Rule Engine

**Current**: ~5ms average

**Optimization**: Pre-compile Regex Patterns

```python
# app/services/rule_engine.py

import re

class RuleEngine:
    def __init__(self):
        # Compile patterns once at startup
        self._keyword_patterns = {}

        for scope in self.l1_scopes:
            patterns = []
            for keyword in scope.keywords_en:
                # Compile regex for word boundary matching
                patterns.append(re.compile(rf'\b{re.escape(keyword)}\b', re.IGNORECASE))

            self._keyword_patterns[scope.scope] = patterns

    def match_l1_scope(self, text: str, language: str):
        """Use pre-compiled patterns."""
        for scope, patterns in self._keyword_patterns.items():
            for pattern in patterns:
                if pattern.search(text):
                    # Match found
                    ...
```

**Before**: 5ms (compile regex every time)
**After**: 2ms (pre-compiled patterns)

### Scaling Horizontally

If single instance can't handle load:

```bash
# Add more API instances behind load balancer
docker-compose scale api=3

# Or Kubernetes
kubectl scale deployment jisrvoc-api --replicas=5
```

**Agent System is Stateless**: Safe to scale horizontally.

---

## When to Add vs Tune Agents

### Add New Agent When:

1. **New Responsibility**: Extracting data that no existing agent handles
   - Example: "Extract pricing objections" → Add PricingAgent

2. **Specialized Processing**: Complex logic that doesn't fit existing agents
   - Example: "Detect customer churn risk" → Add ChurnAgent

3. **External Integration**: Need to call external API
   - Example: "Enrich with Salesforce data" → Add SalesforceAgent

4. **Performance**: Existing agent is doing too much
   - Example: LLMAgent is slow → Split into SentimentAgent + CategoryAgent

### Tune Existing Agent When:

1. **Accuracy Issues**: Classifications are wrong
   - Example: "Payroll feedback classified as Finance" → Update Triage rules

2. **Coverage Gaps**: Missing keywords for certain topics
   - Example: "ZATCA not detected" → Add to compliance regulations

3. **Confidence Too Low**: Agent is uncertain
   - Example: "Confidence <0.5 for most feedback" → Add more keywords, increase boost

4. **Performance Degradation**: Agent is slower than before
   - Example: "LLM agent taking 500ms" → Optimize prompt, cache results

### Decision Tree

```
Is this a NEW responsibility?
├─ YES → Add new agent
└─ NO → Is accuracy the problem?
    ├─ YES → Update rules/prompts
    └─ NO → Is performance the problem?
        ├─ YES → Optimize existing agent
        └─ NO → Is agent doing too much?
            ├─ YES → Split into 2 agents
            └─ NO → Tune existing agent
```

---

## Escalation Procedures

### Severity Levels

| Severity | Impact | Response Time | Escalation |
|----------|--------|---------------|------------|
| **P0 - Critical** | Entire agent pipeline down | <15 min | Immediate page on-call engineer |
| **P1 - High** | >20% error rate | <1 hour | Page on-call engineer |
| **P2 - Medium** | 5-20% error rate | <4 hours | Create ticket, notify team |
| **P3 - Low** | Performance degradation | <1 day | Create ticket |

### P0: Critical - Agent Pipeline Down

**Symptoms**:
- `agent_orchestrator.status = "error"`
- `agent_success_rate = 0.0`
- All enrichment requests failing

**Immediate Actions**:

1. **Page on-call engineer** immediately

2. **Rollback to old pipeline** (1 minute):
   ```bash
   export AGENT_ENRICHMENT_ENABLED=false
   systemctl restart jisrvoc-api
   ```

3. **Verify fallback working**:
   ```bash
   curl https://api.jisrvoc.com/api/v1/readyz | jq '.checks'
   ```

4. **Check logs for root cause**:
   ```bash
   tail -100 /var/log/jisrvoc/app.log | grep ERROR
   ```

5. **Create incident channel**: `#incident-agent-pipeline-down`

6. **Update status page**: "Experiencing issues with enrichment"

### P1: High Error Rate

**Symptoms**:
- `agent_success_rate < 0.80`
- `agent_error_count > 20%` of requests

**Actions**:

1. **Page on-call engineer**

2. **Reduce rollout percentage** (don't disable completely):
   ```bash
   export AGENT_ROLLOUT_PERCENTAGE=10
   systemctl restart jisrvoc-api
   ```

3. **Identify failing agent**:
   ```bash
   grep "Agent.*failed" /var/log/jisrvoc/app.log | awk '{print $5}' | sort | uniq -c | sort -rn
   ```

4. **Check external dependencies**:
   - OpenAI status: https://status.openai.com
   - Database: `psql -h db.jisrvoc.com -U jisrvoc -c "SELECT 1;"`
   - Redis: `redis-cli ping`

5. **If external service down, wait for recovery**. If code bug, rollback to 0%.

### P2: Moderate Issues

**Symptoms**:
- `agent_success_rate = 0.80-0.95`
- Performance degradation (>500ms p95)

**Actions**:

1. **Create ticket**: "Agent pipeline error rate elevated"

2. **Notify #engineering-agents** channel

3. **Collect diagnostics**:
   ```bash
   # Error logs
   grep ERROR /var/log/jisrvoc/app.log | grep agent > /tmp/agent-errors.log

   # Performance logs
   grep execution_time_ms /var/log/jisrvoc/app.log > /tmp/agent-perf.log
   ```

4. **Analyze patterns**:
   - Is error rate increasing over time?
   - Is specific feedback type causing errors?
   - Is performance issue in specific agent?

5. **Schedule fix** within 4 hours

### P3: Low Priority

**Symptoms**:
- Single feedback misclassified
- Minor performance degradation (<10% slower)

**Actions**:

1. **Create ticket**: "Agent classification accuracy improvement"

2. **Gather examples** of misclassifications

3. **Schedule rule tuning** session with PM

4. **Test fixes in staging** before deploying

---

## Runbook Checklist

### Daily Health Check

- [ ] Check health endpoint: `agent_success_rate > 0.95`
- [ ] Review error logs: `<100 errors/day`
- [ ] Monitor latency: `p95 < 300ms`
- [ ] Verify rule engine loaded: `status = "ok"`

### Weekly Review

- [ ] Review agent accuracy metrics
- [ ] Check for slow queries (>1s)
- [ ] Review classification corrections from PMs
- [ ] Update rules based on feedback

### Monthly Optimization

- [ ] Analyze per-agent performance trends
- [ ] Review and archive old themes
- [ ] Optimize database indexes
- [ ] Review and remove unused rules

---

## Additional Resources

- **[Architecture](AGENT_ARCHITECTURE.md)**: System design and agent flow
- **[PM Guide](PM_GUIDE_TO_AGENTS.md)**: How to update rules
- **[Developer Guide](DEVELOPER_GUIDE_AGENTS.md)**: How to build agents
- **[Rollout Plan](ROLLOUT_PLAN.md)**: Production rollout procedures

---

**On-Call Contact**: Check #on-call-schedule Slack channel
**Escalation**: Page via PagerDuty or call VP Engineering

**Document Status**: Complete
**Last Updated**: 2026-07-01
**Maintainer**: DevOps Team
