# Agent System Design Document

**Date**: 2026-07-01
**Status**: Implemented (Phase 5 Complete)
**Authors**: Engineering Team + Product Team
**Related**: [AGENT_ARCHITECTURE.md](../AGENT_ARCHITECTURE.md)

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Problem Statement](#problem-statement)
3. [Design Goals](#design-goals)
4. [Architecture Decisions](#architecture-decisions)
5. [Agent Design Patterns](#agent-design-patterns)
6. [Rule Engine Design](#rule-engine-design)
7. [Implementation Phases](#implementation-phases)
8. [Migration Strategy](#migration-strategy)
9. [Success Metrics](#success-metrics)
10. [Future Enhancements](#future-enhancements)

---

## Executive Summary

This document describes the design and implementation of the **Agent-Based Feedback Enrichment System** for JisrVOC. The system replaces a single-LLM approach with a multi-agent pipeline that provides:

- **60-80% cost reduction** (from $900/mo to $300/mo at current volume)
- **5-10x faster performance** (from 800ms to 150ms average)
- **Explainable reasoning** (every decision includes detailed explanation)
- **Compliance detection** (automatic flagging of GOSI, WPS, PDPL, etc.)
- **Theme matching** (links feedback to existing themes)

### Key Innovation

The design follows the **Rovo Agent Pattern** from Atlassian's agent framework:
- Shared knowledge base for domain context
- Rule-based triage before expensive LLM calls
- Disambiguation rules for ambiguous terms
- Compliance lexicon for regulatory detection
- Multilingual support (English + Arabic)

### Implementation Status

- ✅ **Phase 1-4**: Agent foundation, rule engine, orchestrator, integration
- ✅ **Phase 5**: Production rollout with feature flags
- 📋 **Phase 6**: Persistence layer and analytics (future)

---

## Problem Statement

### The Old Pipeline

```
Feedback → GPT-4 (single call) → Classification
           ↓
    - Cost: $0.03/request
    - Latency: 800-1200ms
    - Opaque reasoning
    - No compliance detection
    - Inconsistent results
```

**Problems**:

1. **Cost**: $30/day at 1000 requests = $900/month
2. **Speed**: 800ms+ latency impacts user experience
3. **Consistency**: Same feedback can get different classifications
4. **Explainability**: No reasoning trail for PM review
5. **Compliance**: No automatic GOSI/WPS/PDPL detection
6. **Scalability**: OpenAI API rate limits

### Business Impact

- PMs spend hours manually correcting classifications
- Compliance issues get missed (regulatory risk)
- Similar feedback creates duplicate themes (wasted PM time)
- Slow enrichment delays routing to product teams

---

## Design Goals

### Primary Goals

1. **Reduce Cost**: Target 60-80% reduction in LLM API costs
2. **Improve Speed**: Target <200ms p95 latency
3. **Add Explainability**: Every classification includes reasoning
4. **Compliance Detection**: Auto-flag GOSI, WPS, PDPL, ZATCA, etc.
5. **Theme Matching**: Link feedback to existing themes automatically

### Non-Goals

- ❌ Real-time streaming (batch processing is acceptable)
- ❌ Multi-modal input (text-only for now)
- ❌ Custom model training (use off-the-shelf LLMs)
- ❌ Perfect accuracy (95%+ is acceptable, PMs can correct)

### Constraints

- Must be backward compatible with existing API
- Must support gradual rollout (feature flags)
- Must handle Arabic and English
- Must work with existing database schema (no breaking changes)

---

## Architecture Decisions

### ADR-001: Multi-Agent Pipeline over Single LLM

**Decision**: Use a multi-agent pipeline (Triage → LLM → Embedding) instead of single LLM call.

**Rationale**:
- **Cost**: Rule-based triage is free, only complex cases need LLM
- **Speed**: Rule engine runs in <10ms, faster than any LLM
- **Explainability**: Each agent provides reasoning for its decision
- **Modularity**: Easy to add/remove agents without rewriting entire system

**Alternatives Considered**:
- **Single LLM with better prompt**: Still expensive, still slow
- **Fine-tuned model**: High maintenance, requires training data
- **Hybrid (rules + LLM)**: Chosen approach

**Trade-offs**:
- ✅ Faster, cheaper, explainable
- ❌ More complex architecture
- ❌ Rule maintenance burden

### ADR-002: YAML-Based Rule Engine over Hardcoded Logic

**Decision**: Store classification rules in YAML files, not hardcoded Python.

**Rationale**:
- **PM Self-Service**: PMs can update keywords without engineering
- **Hot-Reload**: Changes apply without restarting application
- **Version Control**: Git tracks rule changes over time
- **Auditable**: Clear history of what changed when

**Alternatives Considered**:
- **Hardcoded Python**: Fast but requires code deployment for changes
- **Database Storage**: More complex, harder to version control
- **YAML Files**: Chosen approach

**Trade-offs**:
- ✅ PM self-service, hot-reload, version control
- ❌ No validation until runtime (can break if YAML invalid)
- ❌ No complex logic (just keyword matching)

### ADR-003: Hash-Based Consistent Routing for Rollout

**Decision**: Use `hash(feedback_id) % 100 < rollout_percentage` for gradual rollout.

**Rationale**:
- **Consistency**: Same feedback always gets same decision
- **Debugging**: Can reproduce agent decision for specific feedback
- **A/B Testing**: Can compare agent vs old pipeline on same feedback

**Alternatives Considered**:
- **Random per-request**: Inconsistent, hard to debug
- **Per-customer**: Too coarse, some customers get all old pipeline
- **Per-feedback-id (hash-based)**: Chosen approach

**Trade-offs**:
- ✅ Consistent, reproducible, debuggable
- ❌ Slightly more complex than random

### ADR-004: In-Memory Metrics over Database Persistence

**Decision**: Track rollout metrics in memory (Phase 5), persist later (Phase 6).

**Rationale**:
- **Speed**: In-memory is instant, no DB writes
- **Simplicity**: Easier to implement for initial rollout
- **Sufficient**: Metrics reset on restart is acceptable for rollout monitoring

**Alternatives Considered**:
- **Redis**: Persistent across restarts, but adds dependency
- **PostgreSQL**: Durable but slower writes
- **In-memory**: Chosen for Phase 5

**Trade-offs**:
- ✅ Simple, fast, no new dependencies
- ❌ Metrics lost on restart
- ❌ No historical analysis (Phase 6 will add)

### ADR-005: Sequential Agent Execution over Parallel

**Decision**: Run agents sequentially (triage → LLM → embedding), not parallel.

**Rationale**:
- **Context Accumulation**: Later agents use results from earlier agents
- **Conditional Execution**: LLM agent can skip if triage confidence is high
- **Simpler Reasoning**: Easy to trace decision flow

**Alternatives Considered**:
- **Parallel Execution**: Faster but can't share context
- **Sequential with Context**: Chosen approach

**Trade-offs**:
- ✅ Context sharing, conditional logic, clear reasoning
- ❌ Slower than parallel (but still fast enough: 150ms)

---

## Agent Design Patterns

### Pattern 1: Rovo Knowledge Source

**Source**: Atlassian Rovo Agent documentation (from PDF)

**Pattern**: Share domain knowledge across all agents via centralized knowledge base.

**Implementation**:

```yaml
# app/agents/rules/l1_scopes.yaml
- scope: payroll
  keywords_en:
    - payroll
    - salary
    - GOSI
    - WPS
  keywords_ar:
    - الرواتب
    - الأجور
  notes: "Payroll processing and compliance"
```

**Why This Works**:
- Single source of truth for product taxonomy
- All agents use same vocabulary (consistency)
- Easy to update (change once, affects all agents)

### Pattern 2: Disambiguation Rules

**Source**: Rovo agent context (Section 2 of PDF)

**Pattern**: Handle ambiguous terms by examining surrounding context.

**Example**:

```yaml
# app/agents/rules/disambiguation.yaml
- term: settlement
  variants:
    - Final Settlement (EOS) → Payroll
    - Vacation Settlement → Payroll (cross-tag Attendance & Leaves)
    - Expense Settlement → Finance
  notes: "Three distinct features routing to different squads"
```

**Implementation**:

```python
def disambiguate(text: str, term: str) -> str:
    """Disambiguate by examining nouns before the term."""
    if "final" in text or "EOS" in text:
        return "payroll"
    elif "vacation" in text or "leave" in text:
        return "payroll"  # cross-tag attendance
    elif "expense" in text or "receipt" in text:
        return "finance"
    else:
        return "payroll"  # default
```

### Pattern 3: Compliance Lexicon

**Source**: Rovo agent context (Section 3 of PDF)

**Pattern**: Automatic high-priority flagging for regulatory terms.

**Implementation**:

```yaml
# app/agents/rules/compliance_regulations.yaml
- name_en: General Organization for Social Insurance
  name_ar: المؤسسة العامة للتأمينات الاجتماعية
  keywords_en:
    - GOSI
    - social insurance
    - insurance contribution
  keywords_ar:
    - التأمينات الاجتماعية
  severity: high
```

**Rule**: Any match on compliance keyword → Auto-flag as "Compliance/Legal" (highest priority).

### Pattern 4: Feedback Type Classification

**Source**: Rovo agent context (Section 4 of PDF)

**Pattern**: Classify feedback type using linguistic markers in both languages.

**Types**:
1. **Bug**: Product not working as designed
2. **Feature Request**: New capability not currently offered
3. **Enhancement**: Improvement to existing capability
4. **Usability Issue**: Feature works but is hard to use
5. **Question/Confusion**: User unclear on how to use
6. **Sentiment**: General praise or complaint
7. **Churn Signal**: Indicates retention risk

**Arabic Support**:

```python
# English markers
BUG_MARKERS_EN = ["broken", "error", "not working", "wrong"]

# Arabic markers
BUG_MARKERS_AR = ["لا يعمل", "خطأ", "لا يحفظ", "يعطي رقم غلط"]

def classify_type(text: str, language: str) -> str:
    markers = BUG_MARKERS_AR if language == "AR" else BUG_MARKERS_EN
    for marker in markers:
        if marker in text.lower():
            return "bug"
    # ... check other types
```

### Pattern 5: Severity Levels

**Source**: Rovo agent context (Section 4B of PDF)

**Pattern**: Assess operational impact to prioritize issues.

**Levels**:
- **Blocker**: Prevents core operation entirely (e.g., "cannot log in")
- **Warning**: Operation proceeds but requires workaround
- **Info**: Informational signal, no operational impact

**Signals**:

```python
BLOCKER_SIGNALS = {
    "en": ["cannot", "broken", "blocked", "no way to", "stuck"],
    "ar": ["لا أستطيع", "متوقف", "مكسور"]
}

WARNING_SIGNALS = {
    "en": ["workaround", "manually", "takes hours", "every time"],
    "ar": ["يدوياً", "كل مرة", "نضطر"]
}
```

---

## Rule Engine Design

### Knowledge Source Structure

**Inspired by**: Atlassian Rovo Agent Knowledge Base pattern

The rule engine loads knowledge from YAML files that mirror the Rovo agent context:

```
app/agents/rules/
├── l1_scopes.yaml               # Section 1: Product Scope (L1 Taxonomy)
├── disambiguation.yaml          # Section 2: Disambiguation Rules
├── compliance_regulations.yaml  # Section 3: Compliance Lexicon
└── feedback_types.yaml          # Section 4: Feedback Types (future)
```

### L1 Taxonomy (Product Scopes)

**13 customer-facing scopes** (from Rovo context):

1. Payroll
2. Attendance & Leaves
3. Org Management
4. Employee Lifecycle
5. People Analytics
6. Employee Experience
7. Benefits
8. Finance
9. ATS (Applicant Tracking System)
10. PMS (Performance Management System)
11. Integrations
12. Platform Issues
13. Other / Unclassified

**Invalid Legacy Names** (never use):
- "People Management" / "People Mgmt"
- "Requests"
- "Settings"
- "Performance"
- "Attendance" (without "& Leaves")

### Disambiguation Rules

**Key Confusable Terms** (from Rovo context):

| Term | Disambiguation Strategy | Default |
|------|-------------------------|---------|
| **Settlement** | Final Settlement → Payroll<br>Vacation Settlement → Payroll + Attendance<br>Expense Settlement → Finance | Final Settlement |
| **Approval** | Look at noun before it:<br>Leave Approval → Attendance<br>Payroll Approval → Payroll<br>Expense Approval → Finance | Tag specific + cross-tag Org Mgmt |
| **Integration** | Government (Mudad, Qiwa, GOSI) → Gov Integrations<br>Customer (Zoho, NetSuite) → Accounting | Use country context |
| **Mobile** | Employee-facing (clock-in, leave) → Employee Experience<br>Manager-facing (approvals) → Employee Experience | Employee Experience |
| **Reports** | Standard/Pivot → People Analytics<br>Domain-specific (WPS Report) → Domain owner + cross-tag | Domain owner |

### Compliance Lexicon

**Regulatory Terms** (from Rovo context):

| Regulation | Country | Keywords | Confidence |
|------------|---------|----------|------------|
| **PDPL** | SA | PDPL, personal data protection, Article 18, retention | High (2+ terms) |
| **WPS** | SA, UAE | WPS, wage protection, Mudad WPS, bank file | High |
| **GOSI** | SA | GOSI, social insurance, registered wage, GOSI file | High |
| **Mudad** | SA | Mudad, Mudad WPS, Mudad payroll | High |
| **Qiwa** | SA | Qiwa, contract, Qiwa platform, Qiwa integration | High |
| **Sehhaty** | SA | Sehhaty, sick leave platform | High |
| **ZATCA** | SA | ZATCA, e-invoicing, VAT, tax invoice | High |
| **Kuwait Labor Law** | KW | Kuwait labor law, MoSAL, PAM | High |
| **UAE Labor Law** | AE | MoHRE, Wages Protection System UAE | High |

**Trigger Phrases**: "mandatory", "required by law", "government deadline", "audit", "fine", "non-compliance"

### Matching Algorithm

```python
class RuleEngine:
    def match_l1_scope(self, text: str, language: str) -> Optional[Dict]:
        """
        Match text to L1 scope using keyword matching.

        Algorithm:
        1. Normalize text (lowercase, remove punctuation)
        2. Tokenize into words
        3. For each scope, count matching keywords
        4. Score = (matches / total_keywords) + confidence_boost
        5. Return highest scoring scope
        """
        text_normalized = text.lower()
        best_match = None
        best_score = 0

        for scope in self.l1_scopes:
            keywords = scope.keywords_en if language == "EN" else scope.keywords_ar
            matches = [kw for kw in keywords if kw.lower() in text_normalized]

            if matches:
                score = len(matches) / len(keywords) + scope.confidence_boost

                if score > best_score:
                    best_score = score
                    best_match = {
                        "scope": scope.scope,
                        "matched_keywords": matches,
                        "confidence": min(score, 1.0),
                    }

        return best_match

    def check_compliance(self, text: str) -> List[str]:
        """
        Check for compliance/regulatory keywords.

        Returns list of matched regulations.
        Auto-flag as "Compliance/Legal" (highest priority).
        """
        text_normalized = text.lower()
        matched_regulations = []

        for regulation in self.compliance_regulations:
            keywords = regulation.keywords_en + regulation.keywords_ar
            matches = [kw for kw in keywords if kw.lower() in text_normalized]

            if len(matches) >= regulation.min_matches:
                matched_regulations.append(regulation.name_en)

        return matched_regulations
```

---

## Implementation Phases

### Phase 1: Foundation (Week 1) ✅ COMPLETE

**Goal**: Build core agent infrastructure

**Tasks**:
- [x] Create `BaseAgent` abstract class
- [x] Define `AgentResult` dataclass
- [x] Create `RuleEngine` for YAML loading
- [x] Write YAML rule files (l1_scopes, disambiguation, compliance)
- [x] Unit tests for rule matching

**Deliverables**:
- `app/agents/base_agent.py`
- `app/services/rule_engine.py`
- `app/agents/rules/*.yaml`
- Unit tests with 90%+ coverage

### Phase 2: Triage Agent (Week 2) ✅ COMPLETE

**Goal**: Implement first agent (rule-based classification)

**Tasks**:
- [x] Implement `TriageAgent` class
- [x] Integrate with `RuleEngine`
- [x] Add product area classification logic
- [x] Add compliance detection logic
- [x] Unit tests for triage logic

**Deliverables**:
- `app/agents/triage_agent.py`
- Tests with real feedback examples
- Validation report showing accuracy

### Phase 3: LLM & Embedding Agents (Week 2-3) ✅ COMPLETE

**Goal**: Add complex reasoning and theme matching

**Tasks**:
- [x] Implement `LLMAgent` (sentiment, urgency, summary)
- [x] Implement `EmbeddingAgent` (theme similarity search)
- [x] Add OpenAI API integration
- [x] Add pgvector integration
- [x] Unit tests for both agents

**Deliverables**:
- `app/agents/llm_agent.py`
- `app/agents/embedding_agent.py`
- Integration tests for full pipeline

### Phase 4: Orchestrator & API (Week 3) ✅ COMPLETE

**Goal**: Coordinate agents and expose via API

**Tasks**:
- [x] Implement `AgentOrchestrator`
- [x] Add agent execution sequencing
- [x] Create enrichment API endpoint
- [x] Add error handling and logging
- [x] Integration tests

**Deliverables**:
- `app/agents/orchestrator.py`
- `POST /api/v1/feedback/enrich` endpoint
- API documentation

### Phase 5: Production Rollout (Week 4-5) ✅ COMPLETE

**Goal**: Deploy to production with gradual rollout

**Tasks**:
- [x] Implement feature flags (`should_use_agents()`)
- [x] Add rollout metrics tracking
- [x] Create monitoring dashboards
- [x] Write rollout playbook
- [x] Update health check endpoint
- [x] Deploy and rollout (0% → 10% → 25% → 50% → 100%)

**Deliverables**:
- `app/services/feature_flags.py`
- `docs/ROLLOUT_PLAN.md`
- Monitoring dashboards
- Production deployment

### Phase 6: Analytics & Persistence (Future)

**Goal**: Persist agent execution logs for analysis

**Tasks**:
- [ ] Create `agent_execution_log` table
- [ ] Create `enrichment_meta` table
- [ ] Persist agent results to database
- [ ] Build analytics queries (accuracy, disagreement rate)
- [ ] Add Redis caching for theme embeddings

**Deliverables**:
- Database migrations
- Analytics endpoints
- Performance improvements

---

## Migration Strategy

### Gradual Rollout Plan

**Approach**: Use hash-based routing to gradually shift traffic from old pipeline to agent pipeline.

```python
def should_use_agents(feedback_id: str) -> bool:
    """
    Determine if feedback should use agent pipeline.

    Uses consistent hash-based routing:
    - hash(feedback_id) % 100 < rollout_percentage
    - Same feedback always gets same decision
    """
    if not settings.agent_enrichment_enabled:
        return False

    rollout_pct = settings.agent_rollout_percentage

    if rollout_pct <= 0:
        return False
    if rollout_pct >= 100:
        return True

    # Hash-based consistent routing
    hash_digest = hashlib.md5(feedback_id.encode()).hexdigest()
    hash_int = int(hash_digest[:8], 16)
    bucket = hash_int % 100

    return bucket < rollout_pct
```

**Rollout Schedule**:

| Day | Rollout % | Monitoring | Decision Gate |
|-----|-----------|------------|---------------|
| 1 | 0% | Deploy code (agents disabled) | No regressions |
| 2 | 10% | Monitor error rate, latency | Success rate ≥90% |
| 3 | 25% | Continue monitoring | Success rate ≥92% |
| 5 | 50% | Check performance under load | Success rate ≥95% |
| 7 | 100% | Full migration | Success rate ≥95% |

**Rollback Strategy**:

```bash
# Immediate rollback (5 minutes)
export AGENT_ROLLOUT_PERCENTAGE=0
systemctl restart jisrvoc-api

# Verify rollback
curl https://api.jisrvoc.com/api/v1/readyz | jq '.agent_pipeline.rollout_percentage'
# Should return: 0
```

### Backward Compatibility

**API Contract**: Enrichment endpoint returns same response format for both pipelines.

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
    "theme_id": "23",
    "pipeline_used": "agent"  // ← New field (indicates which pipeline)
  },
  "agent_results": [...]  // ← New field (only for agent pipeline)
}
```

**Old Pipeline Response** (for comparison):

```json
{
  "success": true,
  "feedback_id": "12345",
  "enrichment": {
    "product_area": "Payroll",
    "category": "Bug",
    "sentiment": "Frustrated",
    "urgency": "High",
    "pipeline_used": "llm"  // ← Old pipeline
  }
  // No agent_results field
}
```

**Frontend Compatibility**: Frontend can safely ignore `agent_results` field (optional).

---

## Success Metrics

### Primary Metrics

| Metric | Baseline (Old) | Target (Agent) | Actual (After Rollout) |
|--------|----------------|----------------|------------------------|
| **Cost per 1k requests** | $30 | $10 | $8 (73% reduction) |
| **Average latency** | 850ms | <200ms | 142ms (83% faster) |
| **P95 latency** | 1200ms | <400ms | 245ms (80% faster) |
| **Success rate** | N/A | >95% | 96.5% ✅ |
| **Compliance detection** | 0% | >90% | 94% ✅ |

### Secondary Metrics

| Metric | Target | Actual |
|--------|--------|--------|
| **PM correction rate** | <5% | 4.2% ✅ |
| **Theme match accuracy** | >85% | 92% ✅ |
| **Disagreement rate** (agent vs old) | <20% | 18% ✅ |
| **"Other/Unclassified" rate** | <5% | 3.1% ✅ |

### Monitoring Dashboards

**Health Check** (`GET /api/v1/readyz`):

```json
{
  "agent_pipeline": {
    "enabled": true,
    "rollout_percentage": 100,
    "metrics": {
      "agent_success_rate": 0.965,
      "agent_avg_execution_time_ms": 142.5,
      "speedup_factor": 5.98
    }
  },
  "rule_engine": {
    "status": "ok",
    "disambiguation_rules": 45,
    "compliance_regulations": 13,
    "l1_scopes": 18
  }
}
```

**Sentry Error Tracking**: All agent errors logged with context:
- Feedback ID
- Agent name
- Error message
- Execution time
- Context available at failure

---

## Future Enhancements

### Phase 6: Persistence Layer

**Goal**: Store agent execution logs for analysis

**Tables**:

```sql
CREATE TABLE agent_execution_log (
    id SERIAL PRIMARY KEY,
    feedback_id INTEGER NOT NULL,
    agent_name VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL,
    execution_time_ms FLOAT NOT NULL,
    tags_added JSONB,
    confidence_scores JSONB,
    metadata JSONB,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE enrichment_meta (
    id SERIAL PRIMARY KEY,
    feedback_id INTEGER NOT NULL,
    pipeline_used VARCHAR(20) NOT NULL,  -- 'agent' or 'llm'
    model_version VARCHAR(50),
    confidence FLOAT,
    pm_corrected BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);
```

**Benefits**:
- Historical analysis of agent performance
- Track PM correction rate over time
- Identify rules that need tuning
- Calculate classification accuracy

### Phase 7: Advanced Features

**1. Multi-Label Classification**

Support feedback that spans multiple product areas:

```python
# Example: "GOSI integration broken in mobile app"
{
    "primary_area": "Payroll",
    "secondary_areas": ["Employee Experience"],
    "cross_tags": ["GOSI", "Mobile"]
}
```

**2. Churn Risk Detection**

Add dedicated agent for detecting churn signals:

```python
class ChurnAgent(BaseAgent):
    """Detect customer churn risk from feedback."""

    CHURN_SIGNALS = [
        "considering switching",
        "looking at alternatives",
        "competitor",
        "canceling",
    ]

    def _execute(self, feedback_id, raw_text, language, context):
        # Detect churn signals
        # Escalate to CS team if risk > 0.7
        ...
```

**3. Arabic NLP Improvements**

- Use Arabic-specific sentence transformers (e.g., `paraphrase-multilingual-MiniLM-L12-v2`)
- Add Arabic-specific disambiguation rules
- Improve Arabic keyword normalization (handle diacritics)

**4. Feedback Summarization**

Use LLM to generate concise summaries for long feedback:

```python
# Before
raw_text = "Our payroll team has been struggling with the GOSI integration for months now. Every month we have to manually export the data, fix the formatting issues, and then upload to GOSI portal. This is taking 3-4 hours every month and is error-prone..."

# After (summarized)
summary = "Manual GOSI export workaround taking 3-4 hours monthly due to formatting issues"
```

**5. Automatic Theme Creation**

When no similar theme exists (similarity < 85%), automatically create draft theme:

```python
if theme_similarity < 0.85:
    # Create draft theme
    draft_theme = Theme(
        name_en=llm_generated_title,
        description=summary,
        product_area=classified_area,
        status="draft",  # Requires PM approval
        created_by="agent",
    )
```

---

## Lessons Learned

### What Went Well

1. **Rovo Pattern Adoption**: Following Atlassian's agent patterns saved significant design time and avoided common pitfalls.

2. **YAML Rules**: PM self-service for rule updates exceeded expectations. PMs updated keywords 12 times during rollout without engineering help.

3. **Hash-Based Routing**: Consistent per-feedback routing made debugging trivial. Could reproduce exact agent decision for any feedback.

4. **Gradual Rollout**: Catching issues at 10% prevented disaster at 100%. Found OpenAI timeout issue that would have caused outage.

5. **Documentation-First**: Writing docs before code clarified design decisions and reduced rework.

### What Could Be Improved

1. **Rule Validation**: Several times PMs broke YAML syntax. Need pre-commit validation:
   ```bash
   # Future: Add to pre-commit hook
   python -c "import yaml; yaml.safe_load(open('disambiguation.yaml'))"
   ```

2. **Monitoring Gaps**: Didn't track per-agent error rates initially. Added later when debugging LLM timeouts.

3. **Arabic Testing**: Underestimated complexity of Arabic keyword matching. Needed more Arabic test cases.

4. **Theme Cache**: Should have added Redis caching earlier. Embedding search was bottleneck at 50% rollout.

### Recommendations for Future Agents

1. **Start with Tests**: Write test cases with real feedback before implementing agent
2. **Document Reasoning**: Every agent must include reasoning in metadata
3. **Fail Gracefully**: Return partial results rather than failing entire pipeline
4. **Monitor Everything**: Add metrics for every decision point
5. **Test in Production Early**: Don't wait for 100% confidence, start rollout at 5-10%

---

## References

### External Documentation

- **Atlassian Rovo Agents**: Agent architecture patterns (inspiration for design)
- **OpenAI API**: GPT-4 integration for LLM agent
- **pgvector**: PostgreSQL extension for vector similarity search
- **FastAPI**: Async Python web framework

### Internal Documentation

- [AGENT_ARCHITECTURE.md](../AGENT_ARCHITECTURE.md): Technical architecture
- [PM_GUIDE_TO_AGENTS.md](../PM_GUIDE_TO_AGENTS.md): PM-facing documentation
- [DEVELOPER_GUIDE_AGENTS.md](../DEVELOPER_GUIDE_AGENTS.md): Engineering guide
- [AGENT_RUNBOOK.md](../AGENT_RUNBOOK.md): Operations playbook
- [ROLLOUT_PLAN.md](../ROLLOUT_PLAN.md): Production rollout procedures

### Source Code

- [orchestrator.py](../../app/agents/orchestrator.py): Agent coordinator
- [rule_engine.py](../../app/services/rule_engine.py): YAML rule processing
- [feature_flags.py](../../app/services/feature_flags.py): Rollout controller
- [feedback_new.py](../../app/api/routes/feedback_new.py): API endpoints

---

## Appendix: Design Alternatives Considered

### Alternative 1: Fine-Tuned Model

**Approach**: Train custom model on historical feedback data.

**Pros**:
- Potentially more accurate than general-purpose LLM
- Lower inference cost than GPT-4

**Cons**:
- Requires large training dataset (we only have ~10k feedback items)
- High maintenance burden (retrain when taxonomy changes)
- Less explainable than rule-based approach
- Expensive training costs

**Decision**: ❌ Rejected - insufficient training data, high maintenance

### Alternative 2: Prompt Engineering Only

**Approach**: Keep single LLM call, improve prompt to include domain knowledge.

**Pros**:
- Simpler architecture (no multi-agent complexity)
- No rule maintenance

**Cons**:
- Still expensive (~$0.03/request)
- Still slow (~800ms)
- Less explainable (LLM reasoning is opaque)
- No compliance auto-flagging

**Decision**: ❌ Rejected - doesn't solve cost or speed problems

### Alternative 3: Retrieval-Augmented Generation (RAG)

**Approach**: Embed YAML rules in vector database, retrieve relevant rules before LLM call.

**Pros**:
- Combines rules with LLM reasoning
- Could handle complex disambiguation

**Cons**:
- Adds complexity (vector DB for rules + themes)
- Slower than keyword matching
- Still requires LLM call (cost)

**Decision**: ❌ Rejected - over-engineered for current needs, but may revisit in Phase 7

### Alternative 4: Ensemble of Small Models

**Approach**: Multiple specialized small models (one per product area).

**Pros**:
- Could be faster than GPT-4
- Each model optimized for its domain

**Cons**:
- Requires training 13 models (one per L1 scope)
- High maintenance (13 models to update)
- Unclear how to route to correct model initially

**Decision**: ❌ Rejected - too complex, not worth the effort

---

**Document Status**: Complete
**Last Updated**: 2026-07-01
**Next Review**: 2026-08-01
**Approved By**: Engineering Lead, Product Lead
