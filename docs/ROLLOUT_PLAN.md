# Agent Pipeline Rollout Playbook

**Purpose**: Gradual rollout plan for agent-based feedback enrichment pipeline with zero-downtime deployment and instant rollback capability.

**Timeline**: 7-day rollout (can be accelerated if metrics are excellent)

**Owner**: Engineering + Product Management

---

## Prerequisites

Before starting rollout:

- [ ] All Phase 5 code deployed to production
- [ ] Agent orchestrator initialized successfully (check `/api/v1/readyz`)
- [ ] Rule engine loaded with latest YAML rules
- [ ] Sentry monitoring configured and alerting
- [ ] Rollback procedure tested in staging
- [ ] Team has access to production environment variables
- [ ] On-call engineer assigned for rollout week

---

## Rollout Schedule

### **Day 1: Deploy to Production (Agents Disabled)**

**Goal**: Deploy new code with feature flag OFF to verify no regressions.

**Actions**:
1. Deploy latest code to production
2. Verify environment variables:
   ```bash
   AGENT_ENRICHMENT_ENABLED=false
   AGENT_ROLLOUT_PERCENTAGE=0
   ```
3. Check health endpoint:
   ```bash
   curl https://api.jisrvoc.com/api/v1/readyz | jq '.agent_pipeline'
   ```
   Expected:
   ```json
   {
     "enabled": false,
     "rollout_percentage": 0,
     "metrics": {
       "agent_requests": 0,
       "old_pipeline_requests": 0
     }
   }
   ```

**Monitoring**:
- Monitor error rates in Sentry (should be unchanged)
- Check `/api/v1/readyz` returns "ready"
- Verify old LLM pipeline still working normally

**Success Criteria**:
- ✅ Zero increase in error rate
- ✅ No deployment-related incidents
- ✅ All enrichment requests use old pipeline (100%)

**Rollback**: If deployment causes issues, rollback to previous version.

---

### **Day 2: Enable 10% Rollout**

**Goal**: Route 10% of feedback enrichment traffic to agent pipeline.

**Actions**:
1. Update environment variables (no code deployment needed):
   ```bash
   AGENT_ENRICHMENT_ENABLED=true
   AGENT_ROLLOUT_PERCENTAGE=10
   ```
2. Restart application to pick up new environment variables
3. Verify rollout metrics:
   ```bash
   curl https://api.jisrvoc.com/api/v1/readyz | jq '.agent_pipeline'
   ```
   Expected after ~100 requests:
   ```json
   {
     "enabled": true,
     "rollout_percentage": 10,
     "metrics": {
       "agent_percentage": 9.5,  // Should be close to 10%
       "agent_success_rate": 0.95,  // Should be >90%
       "agent_error_count": 0
     }
   }
   ```

**Monitoring** (every 2 hours for first 24h):
- Agent success rate (target: >90%)
- Agent error count (target: <5% of agent requests)
- Agent avg execution time (target: <200ms)
- Old pipeline avg execution time (baseline comparison)
- Sentry error logs for new exceptions
- Check for any agent-specific errors in logs:
  ```bash
  grep "Agent pipeline error" /var/log/jisrvoc/app.log
  ```

**Success Criteria** (after 24 hours):
- ✅ Agent success rate ≥90%
- ✅ Agent error rate <5%
- ✅ No new Sentry alerts
- ✅ Actual traffic split within ±2% of target (8-12%)
- ✅ Agent execution time <200ms p95
- ✅ Zero customer complaints related to enrichment quality

**Rollback**: See "Emergency Rollback Procedure" below.

---

### **Day 3: Increase to 25% Rollout**

**Goal**: Expand to 25% traffic if Day 2 metrics were healthy.

**Pre-flight Check**:
- Review Day 2 metrics dashboard
- Confirm no outstanding incidents
- Get PM sign-off on enrichment quality

**Actions**:
1. Update environment variable:
   ```bash
   AGENT_ROLLOUT_PERCENTAGE=25
   ```
2. Restart application
3. Verify new rollout percentage in `/api/v1/readyz`

**Monitoring** (every 4 hours):
- Same metrics as Day 2
- Compare agent classifications vs PM corrections (if any manual corrections were made):
  ```bash
  curl https://api.jisrvoc.com/api/v1/analytics/classification-accuracy | jq
  ```

**Success Criteria** (after 24 hours):
- ✅ Agent success rate ≥92% (increased threshold)
- ✅ Agent error rate <3%
- ✅ Actual traffic split 23-27%
- ✅ PM feedback on classification quality is positive
- ✅ No increase in customer support tickets

**Rollback**: See "Emergency Rollback Procedure" below.

---

### **Day 5: Increase to 50% Rollout**

**Goal**: Expand to 50% traffic (majority still on old pipeline for safety).

**Pre-flight Check**:
- Review Days 2-4 metrics
- Analyze any PM corrections to agent classifications
- Check rule engine stats for unused rules:
  ```bash
  curl https://api.jisrvoc.com/api/v1/analytics/rule-usage-stats | jq
  ```

**Actions**:
1. Update environment variable:
   ```bash
   AGENT_ROLLOUT_PERCENTAGE=50
   ```
2. Restart application
3. Monitor increased load on agent pipeline

**Monitoring** (every 4 hours):
- Same metrics as Day 3
- Monitor for any performance degradation under increased load
- Check disagreement rate between agent and old pipeline:
  ```bash
  curl https://api.jisrvoc.com/api/v1/analytics/disagreement-rate | jq
  ```

**Success Criteria** (after 48 hours):
- ✅ Agent success rate ≥95%
- ✅ Agent error rate <2%
- ✅ Actual traffic split 48-52%
- ✅ Agent avg execution time still <200ms (no performance degradation)
- ✅ Disagreement rate with old pipeline <20% (indicates consistency)
- ✅ No rollbacks or incidents

**Rollback**: See "Emergency Rollback Procedure" below.

---

### **Day 7: Increase to 100% Rollout**

**Goal**: Full migration to agent pipeline, old pipeline remains as emergency fallback.

**Pre-flight Check**:
- Review Days 5-6 metrics
- Get final PM sign-off on enrichment quality
- Confirm team confidence in agent pipeline stability
- Review any customer feedback from past week

**Actions**:
1. Update environment variable:
   ```bash
   AGENT_ROLLOUT_PERCENTAGE=100
   ```
2. Restart application
3. Verify all traffic now on agent pipeline

**Monitoring** (every 2 hours for first 24h, then daily):
- Same metrics as Day 5
- Monitor full production load on agent pipeline
- Track any spike in errors or latency
- Review classification accuracy over 7-day window

**Success Criteria** (after 7 days at 100%):
- ✅ Agent success rate ≥95%
- ✅ Agent error rate <2%
- ✅ Actual traffic split 100%
- ✅ No increase in customer complaints
- ✅ PM classification correction rate <5%
- ✅ Cost savings from reduced LLM API usage confirmed

**Final Decision**: After 7 days at 100%, if all criteria met:
- Schedule old pipeline code removal for 2 weeks later
- Update monitoring dashboards to remove old pipeline metrics
- Document any rule refinements discovered during rollout

---

## Emergency Rollback Procedure

**Trigger Conditions** (any of these warrant immediate rollback):
- Agent success rate drops below 85%
- Agent error rate exceeds 10%
- Spike in Sentry alerts (>10 new errors/hour)
- Customer complaints about enrichment quality
- Agent execution time p95 exceeds 500ms
- PM identifies systematic classification errors
- Any production incident attributed to agent pipeline

**Rollback Steps** (5 minutes):

1. **Immediate**: Set rollout to 0%
   ```bash
   # SSH to production server
   ssh production-server

   # Update environment variable
   export AGENT_ROLLOUT_PERCENTAGE=0

   # Restart application (or update via your deployment tool)
   systemctl restart jisrvoc-api
   ```

2. **Verify rollback** (within 1 minute):
   ```bash
   curl https://api.jisrvoc.com/api/v1/readyz | jq '.agent_pipeline.rollout_percentage'
   # Should return: 0
   ```

3. **Monitor recovery**:
   - Check error rate returns to baseline (within 5 minutes)
   - Verify old pipeline handling 100% traffic
   - Confirm Sentry alerts stop

4. **Post-incident**:
   - Create incident report with root cause
   - Review logs for specific failure patterns:
     ```bash
     grep "Agent pipeline error" /var/log/jisrvoc/app.log | tail -100
     ```
   - Identify which agent caused issues (triage, LLM, embedding)
   - Fix root cause before re-attempting rollout
   - Consider restarting rollout at lower percentage (5%)

**Alternative: Partial Rollback**

If issues affect only certain types of feedback, you can:
1. Reduce rollout percentage instead of disabling completely:
   ```bash
   AGENT_ROLLOUT_PERCENTAGE=5  # Drop to 5% while investigating
   ```
2. Investigate affected feedback items
3. Fix rule engine or agent logic
4. Hot-reload rules without restarting:
   ```bash
   curl -X POST https://api.jisrvoc.com/api/v1/feedback/admin/reload-rules
   ```

---

## Monitoring Dashboard

**Key Metrics to Track**:

### 1. **Rollout Health** (`/api/v1/readyz`)
```json
{
  "agent_pipeline": {
    "enabled": true,
    "rollout_percentage": 50,
    "metrics": {
      "total_requests": 1000,
      "agent_requests": 485,
      "old_pipeline_requests": 515,
      "agent_percentage": 48.5,
      "agent_success_rate": 0.96,
      "agent_error_count": 19,
      "agent_avg_execution_time_ms": 145.23,
      "old_avg_execution_time_ms": 892.45,
      "speedup_factor": 6.15
    }
  },
  "rule_engine": {
    "status": "ok",
    "disambiguation_rules": 45,
    "compliance_regulations": 12,
    "l1_scopes": 18,
    "last_loaded": "2026-07-01T10:30:00Z"
  }
}
```

### 2. **Agent Performance** (custom queries)
- Agent success rate trend over time
- Error count by agent (triage, LLM, embedding)
- Execution time percentiles (p50, p90, p95, p99)
- Rule match frequency (which rules fire most often)

### 3. **Classification Quality** (PM feedback)
- PM correction rate (manual edits to agent classifications)
- Disagreement rate with old pipeline
- Customer complaints related to enrichment

### 4. **Cost Savings**
- Reduction in OpenAI API costs (old pipeline uses GPT-4)
- Agent pipeline uses LLM only for complex cases
- Track API call reduction percentage

---

## Checkpoints and Decision Gates

At each rollout stage, confirm:

| Checkpoint | Decision Gate | Action if Failed |
|------------|---------------|------------------|
| Day 1 | Deployment successful, no regressions | Rollback deployment |
| Day 2 (10%) | Agent success rate ≥90% | Stay at 10% for another 24h |
| Day 3 (25%) | Agent success rate ≥92% | Rollback to 10% |
| Day 5 (50%) | Agent success rate ≥95%, no performance degradation | Rollback to 25% |
| Day 7 (100%) | Agent success rate ≥95%, PM sign-off | Rollback to 50%, investigate |

**Acceleration**: If metrics are significantly better than targets (e.g., 99% success rate at 10%), you can accelerate the schedule:
- Skip to 50% after Day 2
- Skip to 100% after Day 4

**Deceleration**: If metrics are borderline, slow down:
- Stay at current percentage for extra 24-48h
- Add intermediate stages (e.g., 10% → 15% → 20%)

---

## Communication Plan

### Internal Updates

**Daily Standup**: Share rollout status with engineering team
- Current rollout percentage
- Key metrics (success rate, error count)
- Any issues or concerns

**Slack Channel**: Post updates in #engineering-rollout:
- Day 1: "🚀 Agent pipeline deployed to production (disabled)"
- Day 2: "📊 Agent pipeline at 10%, monitoring closely"
- Day 3: "📈 Increased to 25%, metrics healthy"
- Day 5: "✅ At 50%, agent pipeline outperforming expectations"
- Day 7: "🎉 Full rollout complete! Agent pipeline handling 100% traffic"

### PM/Stakeholder Updates

**Weekly Email**: Summary of rollout progress
- Classification quality feedback
- Cost savings achieved
- Any adjustments to rules or logic
- Timeline for old pipeline removal

### Customer Communication

**If Issues Occur**: Prepare customer-facing message:
> "We're temporarily experiencing slower enrichment times while we optimize our classification pipeline. Your feedback is still being processed, and there's no data loss. We expect to resolve this within 1 hour."

---

## Post-Rollout (Day 14+)

After 7 days at 100% with stable metrics:

1. **Code Cleanup**: Remove old LLM pipeline code
   - Delete `ClassificationPipeline` class
   - Remove old prompt templates
   - Keep `should_use_agents()` for future A/B tests

2. **Documentation**: Update architecture docs
   - Document new agent-based approach
   - Add rule authoring guide for PMs
   - Create troubleshooting guide for common issues

3. **Monitoring**: Switch to long-term monitoring
   - Reduce alert frequency (daily instead of hourly)
   - Set up weekly classification accuracy reports
   - Track rule usage over time to identify obsolete rules

4. **Cost Analysis**: Calculate actual savings
   - Compare OpenAI API costs before/after
   - Factor in reduced execution time (faster UX)
   - Report ROI to leadership

---

## Troubleshooting Guide

### Issue: Agent success rate below target

**Symptoms**: `agent_success_rate < 0.90` in metrics

**Investigation**:
1. Check which agent is failing:
   ```bash
   grep "Agent pipeline error" /var/log/jisrvoc/app.log | grep -oP 'agent_name": "\K[^"]+' | sort | uniq -c
   ```
2. Review Sentry for specific exceptions
3. Check if issue is language-specific (Arabic vs English)

**Solutions**:
- If triage agent failing: Review L1 scope keywords
- If LLM agent failing: Check OpenAI API status, increase timeout
- If embedding agent failing: Verify theme embedding cache
- If rule engine failing: Hot-reload rules with fixes

### Issue: High disagreement with old pipeline

**Symptoms**: `disagreement_rate > 0.30` (>30% classifications differ)

**Investigation**:
1. Query disagreement patterns:
   ```bash
   curl https://api.jisrvoc.com/api/v1/analytics/disagreement-rate | jq '.disagreement_patterns'
   ```
2. Review specific feedback items where pipelines disagree
3. Determine if agent is more accurate (consult PM)

**Solutions**:
- Refine disambiguation rules for ambiguous cases
- Add new product area keywords to L1 scopes
- Adjust confidence thresholds in agents

### Issue: Agent slower than expected

**Symptoms**: `agent_avg_execution_time_ms > 300ms`

**Investigation**:
1. Check per-agent execution times in logs
2. Identify bottleneck (triage, LLM, embedding)
3. Check database query performance for theme matching

**Solutions**:
- Add Redis caching for theme embeddings
- Optimize rule engine keyword matching
- Consider async parallel agent execution
- Scale up server resources if needed

---

## Success Definition

The rollout is considered successful when:

✅ **Day 7+**: Agent pipeline handling 100% of enrichment traffic

✅ **Performance**: Agent success rate ≥95%, error rate <2%

✅ **Speed**: Average execution time <200ms (5-10x faster than old pipeline)

✅ **Quality**: PM classification correction rate <5%

✅ **Stability**: Zero production incidents attributed to agent pipeline

✅ **Cost**: Reduced OpenAI API costs by >50%

✅ **Team Confidence**: Engineering and PM teams confident in new pipeline

Once these criteria are met for 7 consecutive days, the rollout is complete and old pipeline code can be removed.

---

## Contact

**Rollout Lead**: [Engineering Lead Name]

**On-Call Engineer**: Check #on-call-schedule

**Escalation**: If critical issues arise, escalate immediately to:
- Engineering Lead
- VP Engineering
- Product Manager (for classification quality issues)

**Rollback Authority**: Any engineer can initiate rollback if trigger conditions are met. No approval needed in emergency.
