# PM Guide to Agent System

**Audience**: Product Managers, Customer Success, Business Analysts
**Purpose**: Understand agent reasoning, update rules, and interpret results
**Last Updated**: 2026-07-01

---

## Table of Contents

1. [What Are Agents?](#what-are-agents)
2. [Reading Agent Reasoning Logs](#reading-agent-reasoning-logs)
3. [Updating Classification Rules](#updating-classification-rules)
4. [Testing Rule Changes](#testing-rule-changes)
5. [Understanding Confidence Scores](#understanding-confidence-scores)
6. [Common Classification Patterns](#common-classification-patterns)
7. [When to Escalate](#when-to-escalate)

---

## What Are Agents?

### Simple Explanation

Think of the agent system as a **team of specialists** that review each piece of customer feedback:

1. **Triage Agent** (The Sorter): Reads keywords and assigns to product area
   - Like a mail sorter: "This mentions GOSI → goes to Payroll team"
   - Fast: <10ms, rule-based

2. **LLM Agent** (The Analyst): Understands context and sentiment
   - Like a customer success analyst: "Customer is frustrated, this is urgent"
   - Slower: ~180ms, AI-powered

3. **Embedding Agent** (The Librarian): Finds similar past issues
   - Like a librarian: "We've seen this problem 15 times before → Theme #23"
   - Medium: ~60ms, similarity search

### Why This Matters to You

**Better Classification**:
- More accurate product area assignments
- Automatic compliance flagging (GOSI, WPS, PDPL)
- Consistent results (same feedback → same classification)

**Better Insights**:
- Every classification includes **reasoning** explaining the decision
- You can see which keywords triggered which classification
- You can track themes and patterns over time

**You Can Improve It**:
- Update rules in YAML files (no coding required)
- Test changes instantly (no deployment needed)
- See impact immediately in agent logs

---

## Reading Agent Reasoning Logs

### Where to Find Logs

**Option 1: Enrichment API Response**

When you call the enrichment endpoint, you get detailed reasoning:

```bash
curl -X POST https://api.jisrvoc.com/api/v1/feedback/enrich?feedback_id=12345
```

Response includes:

```json
{
  "success": true,
  "feedback_id": "12345",
  "enrichment": {
    "product_area": "Payroll",
    "category": "Bug",
    "sentiment": "Frustrated",
    "urgency": "High",
    "compliance_tags": ["GOSI"],
    "theme_id": "23"
  },
  "agent_results": [
    {
      "agent_name": "triage",
      "status": "success",
      "tags_added": ["product_area:payroll"],
      "confidence_scores": {"product_area": 0.95},
      "metadata": {
        "matched_keywords": ["GOSI", "salary"],
        "reasoning": "Matched GOSI keyword → Payroll scope (95% confidence)"
      },
      "execution_time_ms": 5.2
    },
    ...
  ]
}
```

**Option 2: Application Logs**

Check server logs for detailed reasoning:

```bash
grep "Agent execution" /var/log/jisrvoc/app.log
```

### Interpreting Triage Agent Logs

**Example Log**:

```json
{
  "agent_name": "triage",
  "status": "success",
  "tags_added": ["product_area:payroll", "compliance:GOSI"],
  "confidence_scores": {"product_area": 0.95},
  "metadata": {
    "product_area": "Payroll",
    "l1_scope": "payroll",
    "matched_keywords": ["GOSI", "salary", "WPS"],
    "compliance_tags": ["GOSI"],
    "reasoning": "Matched 3 payroll keywords: GOSI, salary, WPS → Payroll (95% confidence). Compliance flag: GOSI regulation detected."
  },
  "execution_time_ms": 5.2
}
```

**What This Tells You**:

| Field | Meaning | Action |
|-------|---------|--------|
| `status: success` | Agent completed successfully | ✅ No action needed |
| `product_area: Payroll` | Classified as Payroll | ✅ Check if correct |
| `matched_keywords: [GOSI, salary, WPS]` | These words triggered classification | 📝 If wrong, update keywords |
| `confidence_scores: 0.95` | 95% confident in classification | ✅ High confidence is good |
| `compliance_tags: [GOSI]` | Regulatory flag detected | ⚠️ Route to compliance team |
| `execution_time_ms: 5.2` | Took 5ms to complete | ✅ Fast response |

### Interpreting LLM Agent Logs

**Example Log**:

```json
{
  "agent_name": "llm",
  "status": "success",
  "tags_added": ["sentiment:frustrated", "urgency:high", "category:bug"],
  "confidence_scores": {
    "sentiment": 0.85,
    "urgency": 0.90,
    "category": 0.92
  },
  "metadata": {
    "sentiment": "Frustrated",
    "sentiment_score": -0.7,
    "urgency": "High",
    "category": "Bug",
    "summary": "GOSI integration failure blocking payroll processing",
    "reasoning": "Customer reports integration broken (Bug). High urgency due to payroll impact. Frustrated tone detected."
  },
  "execution_time_ms": 185.3
}
```

**What This Tells You**:

| Field | Meaning | Action |
|-------|---------|--------|
| `sentiment: Frustrated` | Customer is unhappy | 😡 Prioritize response |
| `sentiment_score: -0.7` | -1.0 (very negative) to +1.0 (very positive) | Scale of frustration |
| `urgency: High` | Needs immediate attention | 🚨 High priority |
| `category: Bug` | System is broken (not feature request) | 🐛 Route to engineering |
| `summary` | AI-generated 1-line summary | 📋 Use in reports |

### Interpreting Embedding Agent Logs

**Example Log**:

```json
{
  "agent_name": "embedding",
  "status": "success",
  "tags_added": ["theme:23"],
  "confidence_scores": {"theme_similarity": 0.92},
  "metadata": {
    "theme_id": "23",
    "theme_name": "GOSI Integration Issues",
    "theme_similarity": 0.92,
    "theme_decision": "MERGE",
    "reasoning": "High similarity (92%) to existing theme #23: 'GOSI Integration Issues' (15 items, active discussion). Decision: MERGE"
  },
  "execution_time_ms": 58.7
}
```

**Theme Decisions**:

| Decision | Meaning | What Happens |
|----------|---------|--------------|
| `MERGE` | Very similar to existing theme (>85%) | Add to existing theme #23 |
| `CREATE` | No similar theme found (<85%) | Create new theme |
| `SPLIT` | Feedback addresses multiple themes | Create multiple items |

**What This Tells You**:

- **High similarity (>90%)**: Duplicate issue, likely already being tracked
- **Medium similarity (70-85%)**: Related but potentially new angle
- **Low similarity (<70%)**: New issue, create new theme

---

## Updating Classification Rules

### Overview

You can update classification rules by editing YAML files. No coding required!

**Rule Files**:
1. **Disambiguation rules**: `app/agents/rules/disambiguation.yaml`
2. **Compliance regulations**: `app/agents/rules/compliance_regulations.yaml`
3. **Product areas (L1 scopes)**: `app/agents/rules/l1_scopes.yaml`

### Use Case 1: Add New Product Area Keyword

**Scenario**: Customers are mentioning "end of service" but it's not being classified correctly.

**Step 1**: Open the L1 scopes file

```bash
vim app/agents/rules/l1_scopes.yaml
```

**Step 2**: Find the relevant product area

```yaml
- scope: payroll
  keywords_en:
    - payroll
    - salary
    - wage
    - pay slip
    - GOSI
    - WPS
    - end of service        # ← ADD THIS
    - EOS benefits           # ← ADD THIS
  keywords_ar:
    - الرواتب
    - الأجور
    - مكافأة نهاية الخدمة   # ← ADD THIS
  confidence_boost: 0.15
  notes: "Payroll processing and compliance"
```

**Step 3**: Save and reload rules (see next section)

### Use Case 2: Add New Compliance Regulation

**Scenario**: Need to flag PDPL (data privacy) mentions.

**Step 1**: Open compliance file

```bash
vim app/agents/rules/compliance_regulations.yaml
```

**Step 2**: Add new regulation

```yaml
- name_en: Personal Data Protection Law
  name_ar: نظام حماية البيانات الشخصية
  keywords_en:
    - PDPL
    - personal data
    - data privacy
    - data protection
    - privacy law
  keywords_ar:
    - حماية البيانات
    - الخصوصية
  severity: high
  notes: "Saudi data privacy regulation (PDPL)"
```

**Step 3**: Save and reload rules

### Use Case 3: Disambiguate Ambiguous Term

**Scenario**: "Leave" is being confused with "Business Trip"

**Step 1**: Open disambiguation file

```bash
vim app/agents/rules/disambiguation.yaml
```

**Step 2**: Add or update rule

```yaml
- term: leave
  variants:
    - time off
    - vacation
    - absence
    - annual leave
    - sick leave
  scope: attendance
  confidence: high
  notes: "Leave management (NOT business travel)"

- term: trip
  variants:
    - business trip
    - travel request
    - trip approval
  scope: business_trip
  confidence: high
  notes: "Business travel (NOT leave/absence)"
```

**Step 3**: Save and reload rules

### Best Practices for Rule Updates

**DO**:
- ✅ Add notes explaining why the keyword belongs in this category
- ✅ Include both English and Arabic keywords
- ✅ Test with real feedback examples before deploying
- ✅ Add multiple variants of the same concept
- ✅ Review existing rules before adding duplicates

**DON'T**:
- ❌ Add generic keywords that could match multiple areas (e.g., "system", "issue")
- ❌ Forget to test after making changes
- ❌ Remove keywords without consulting the team
- ❌ Add keywords in wrong language section
- ❌ Use special characters (stick to alphanumeric)

---

## Testing Rule Changes

### Step-by-Step Testing Process

#### Step 1: Update YAML File Locally

Make your changes in the rule file:

```bash
vim app/agents/rules/l1_scopes.yaml
# ... make changes ...
# Save file (ESC :wq)
```

#### Step 2: Reload Rules (Instant)

**No restart required!** Use the reload endpoint:

```bash
curl -X POST https://api.jisrvoc.com/api/v1/feedback/admin/reload-rules
```

Response:

```json
{
  "success": true,
  "message": "Rules reloaded successfully",
  "agent_status": {
    "agent_count": 3,
    "agents": ["triage", "llm", "embedding"],
    "rule_engine": {
      "disambiguation_rules": 45,
      "compliance_regulations": 13,
      "l1_scopes": 18,
      "last_loaded": "2026-07-01T15:30:00Z"
    }
  }
}
```

#### Step 3: Test with Real Feedback

Pick a feedback item that should match your new keyword:

```bash
curl -X POST "https://api.jisrvoc.com/api/v1/feedback/enrich?feedback_id=12345"
```

Check the `agent_results` → `triage` → `metadata` → `matched_keywords` to see if your keyword matched.

#### Step 4: Verify in Logs

Check application logs for reasoning:

```bash
grep "matched_keywords" /var/log/jisrvoc/app.log | tail -10
```

Look for your new keyword in the matched list.

#### Step 5: Rollback if Needed

If your changes caused issues:

```bash
# Revert YAML file to previous version
git checkout HEAD -- app/agents/rules/l1_scopes.yaml

# Reload rules
curl -X POST https://api.jisrvoc.com/api/v1/feedback/admin/reload-rules
```

### Testing Checklist

Before deploying rule changes to production:

- [ ] Rules reload successfully (no YAML syntax errors)
- [ ] New keyword matches target feedback items
- [ ] New keyword doesn't cause false positives on other items
- [ ] Confidence scores are reasonable (0.7-1.0 for good matches)
- [ ] Both English and Arabic keywords added (if applicable)
- [ ] Notes field explains the reasoning
- [ ] Tested with at least 3 real feedback examples
- [ ] Reviewed by another PM or engineer

---

## Understanding Confidence Scores

### What is a Confidence Score?

A **confidence score** (0.0 to 1.0) indicates how certain the agent is about its classification.

**Scale**:
- **0.9-1.0**: Very confident (near certain)
- **0.7-0.9**: Confident (good match)
- **0.5-0.7**: Moderate confidence (possible match)
- **0.0-0.5**: Low confidence (guessing)

### How Confidence is Calculated

#### Triage Agent Confidence

```
confidence = (num_matched_keywords / total_keywords) + confidence_boost
```

**Example**:

```yaml
# Payroll scope has 8 keywords
scope: payroll
keywords_en: [payroll, salary, wage, GOSI, WPS, EOS, pay slip, compensation]
confidence_boost: 0.15
```

**Feedback**: "Our GOSI and WPS integration is broken"

**Calculation**:
- Matched keywords: `GOSI`, `WPS` (2 out of 8)
- Base score: 2 / 8 = 0.25
- With boost: 0.25 + 0.15 = **0.40 (low confidence)**

**Feedback**: "GOSI integration for payroll salary calculations is broken, WPS not working"

**Calculation**:
- Matched keywords: `GOSI`, `payroll`, `salary`, `WPS` (4 out of 8)
- Base score: 4 / 8 = 0.50
- With boost: 0.50 + 0.15 = **0.65 (moderate confidence)**

#### LLM Agent Confidence

The LLM agent provides its own confidence based on context:

```json
{
  "sentiment": "Frustrated",
  "confidence_scores": {
    "sentiment": 0.85,    // 85% confident it's frustration
    "urgency": 0.90,      // 90% confident it's high urgency
    "category": 0.92      // 92% confident it's a bug
  }
}
```

LLM confidence is based on:
- Clarity of feedback text
- Strength of sentiment signals
- Consistency with context

#### Embedding Agent Confidence

```
confidence = cosine_similarity(feedback_embedding, theme_embedding)
```

**Scale**:
- **0.95-1.0**: Nearly identical feedback
- **0.85-0.95**: Very similar (MERGE recommended)
- **0.70-0.85**: Related but different angle
- **0.0-0.70**: Different topic (CREATE new theme)

### When to Trust Confidence Scores

| Confidence | Trust Level | Action |
|------------|-------------|--------|
| **0.9-1.0** | ✅ Trust it | Accept classification |
| **0.7-0.9** | ✅ Mostly trust | Review if seems wrong |
| **0.5-0.7** | ⚠️ Review | Verify manually |
| **0.0-0.5** | ❌ Don't trust | Manually classify |

### Improving Low Confidence

**If confidence is consistently low (<0.7)**:

1. **Add more keywords** to relevant product area
2. **Add disambiguation rules** for ambiguous terms
3. **Increase confidence boost** in L1 scopes (max: 0.3)
4. **Split overly broad categories** into subcategories

**Example Fix**:

```yaml
# Before: Low confidence (0.4-0.6)
- scope: hr
  keywords_en:
    - HR
    - human resources
  confidence_boost: 0.0

# After: Higher confidence (0.6-0.9)
- scope: hr
  keywords_en:
    - HR
    - human resources
    - onboarding
    - offboarding
    - employee records
    - personnel file
    - org chart
    - organization structure
  confidence_boost: 0.15
```

---

## Common Classification Patterns

### Pattern 1: Compliance Flags

**What You See**:

```json
{
  "product_area": "Payroll",
  "compliance_tags": ["GOSI", "WPS"],
  "urgency": "High"
}
```

**What It Means**:
- Customer is discussing regulatory requirements
- This feedback might need legal/compliance review
- Route to both product team AND compliance team

**Actions**:
1. Flag for compliance review
2. Check if regulatory deadline is approaching
3. Prioritize for legal review before implementation

### Pattern 2: Duplicate Issues (High Theme Similarity)

**What You See**:

```json
{
  "theme_id": "23",
  "theme_similarity": 0.94,
  "theme_decision": "MERGE",
  "theme_name": "GOSI Integration Issues"
}
```

**What It Means**:
- This is the 16th report of the same issue
- Theme #23 already exists with 15 similar reports
- Don't create duplicate ticket

**Actions**:
1. Add +1 to existing theme vote count
2. Check if issue is being worked on
3. Update customer: "Known issue, in progress"

### Pattern 3: Ambiguous Classification (Low Confidence)

**What You See**:

```json
{
  "product_area": "Other / Unclassified",
  "confidence": 0.35,
  "matched_keywords": [],
  "reasoning": "No scope keywords matched"
}
```

**What It Means**:
- Feedback doesn't match any known patterns
- Might be new feature area
- Might be poorly written feedback

**Actions**:
1. **Manually review** the raw feedback text
2. **If valid feedback**: Add missing keywords to rules
3. **If spam/unclear**: Mark as unclassified
4. **If new area**: Create new product scope in YAML

### Pattern 4: Multi-Topic Feedback

**What You See**:

```json
{
  "product_area": "Payroll",
  "matched_keywords": ["salary", "leave", "attendance"],
  "theme_decision": "SPLIT",
  "reasoning": "Multiple topics detected: Payroll + Attendance"
}
```

**What It Means**:
- Feedback discusses multiple product areas
- Should be split into separate tickets

**Actions**:
1. **Create separate tickets** for Payroll and Attendance
2. Link tickets as related
3. Update customer: "Split into 2 items for tracking"

### Pattern 5: Urgent Bug with High Impact

**What You See**:

```json
{
  "category": "Bug",
  "urgency": "High",
  "sentiment": "Frustrated",
  "sentiment_score": -0.8,
  "compliance_tags": ["WPS"],
  "matched_keywords": ["payroll", "WPS", "broken"]
}
```

**What It Means**:
- Critical bug blocking compliance-required functionality
- Customer is very frustrated
- Needs immediate attention

**Actions**:
1. **Create P0 ticket** (highest priority)
2. **Escalate to engineering** immediately
3. **Notify customer** within 1 hour
4. **Track for SLA compliance**

---

## When to Escalate

### Escalate to Engineering When:

1. **Agent Errors**:
   ```json
   {
     "agent_name": "triage",
     "status": "error",
     "error_message": "Failed to load rules: YAML syntax error"
   }
   ```
   → Rules have syntax error, need engineer to fix

2. **Consistently Low Confidence** (<0.5 for most feedback):
   → Rules need retuning by engineer

3. **High Disagreement Rate** (agent vs manual classification >30%):
   → Agent logic needs adjustment

4. **Performance Degradation** (>500ms average):
   → System performance issue

### Escalate to Compliance/Legal When:

1. **New Compliance Keyword** detected that's not in rules:
   ```json
   {
     "matched_keywords": ["ZATCA", "e-invoicing"],
     "compliance_tags": []
   }
   ```
   → New regulation mentioned, needs review

2. **High Severity Compliance Issue**:
   ```json
   {
     "compliance_tags": ["GOSI"],
     "urgency": "High",
     "category": "Bug"
   }
   ```
   → Regulatory requirement not working

### Do NOT Escalate When:

1. **Single feedback misclassified**: Manually correct and move on
2. **Confidence score is moderate** (0.6-0.8): This is normal
3. **Theme decision is CREATE** for genuinely new issues: Working as intended
4. **Feedback is spam/unclear**: Mark as such, don't blame agent

---

## FAQ

### Q: Can I update rules in production directly?

**A**: Yes! Use the reload endpoint:
```bash
curl -X POST https://api.jisrvoc.com/api/v1/feedback/admin/reload-rules
```

Rules reload without restarting the application. However, **test in staging first** if making major changes.

### Q: What if I break the rules file?

**A**: The reload endpoint will return an error:
```json
{
  "success": false,
  "message": "Failed to reload rules. Check logs for details."
}
```

Check logs:
```bash
grep "Failed to reload rules" /var/log/jisrvoc/app.log
```

Fix the YAML syntax error and try again. Old rules remain active until reload succeeds.

### Q: How do I see all current rules?

**A**: Check the health endpoint:
```bash
curl https://api.jisrvoc.com/api/v1/readyz | jq '.rule_engine'
```

Response:
```json
{
  "status": "ok",
  "disambiguation_rules": 45,
  "compliance_regulations": 13,
  "l1_scopes": 18,
  "last_loaded": "2026-07-01T15:30:00Z"
}
```

### Q: Why is the same feedback getting different classifications?

**A**: This **shouldn't happen** with the agent system! Unlike the old LLM-only pipeline, agents use consistent hash-based rules.

If you see inconsistent results:
1. Check if rules were reloaded between attempts
2. Check if feedback text was modified
3. If truly inconsistent, escalate to engineering (possible bug)

### Q: How do I compare agent classification vs old pipeline?

**A**: Run the comparison script:
```bash
python scripts/compare_pipelines.py --limit 100 --show-disagreements
```

This will show you where the agent and old LLM pipeline disagree, helping you validate rule accuracy.

### Q: Can I disable specific agents?

**A**: Currently, all agents run in sequence. You can't disable individual agents without code changes.

If an agent is causing issues, escalate to engineering to investigate.

### Q: How do I track agent accuracy over time?

**A**: Query the analytics endpoint:
```bash
curl https://api.jisrvoc.com/api/v1/analytics/classification-accuracy | jq
```

This shows:
- Total agent classifications
- PM correction rate
- Accuracy trend over time

---

## Additional Resources

- **[Architecture Overview](AGENT_ARCHITECTURE.md)**: Technical architecture details
- **[Developer Guide](DEVELOPER_GUIDE_AGENTS.md)**: How engineers build agents
- **[Operations Runbook](AGENT_RUNBOOK.md)**: Troubleshooting and monitoring
- **[Rollout Plan](ROLLOUT_PLAN.md)**: Production rollout schedule

---

**Questions?** Ask in #product-voc or #engineering-agents Slack channels.

**Document Status**: Complete
**Last Updated**: 2026-07-01
**Maintainer**: Product Team
