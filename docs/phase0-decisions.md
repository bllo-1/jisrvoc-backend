# Phase 0: Architecture Decisions

**Document Version**: 1.0
**Date**: 2026-06-29
**Status**: ✅ Approved
**Strategy**: Railway + OpenAI for testing → GCP Dammam + Vertex AI for production

---

## Overview

This document captures all critical architecture decisions made during Phase 0 of the JisrVoC (Jisr Voice of Customer) project. These decisions guide implementation through Phases 1-5 and establish the foundation for the AI-powered customer feedback analytics platform.

---

## Decision 1: Cloud Infrastructure & Data Residency

### Context

JisrVoC must:
- Comply with Saudi data residency requirements for production
- Support rapid development and testing during early phases
- Enable cost-effective experimentation with AI models
- Maintain deployment flexibility

### Decision

**Two-Phase Deployment Strategy**

#### Testing Phase (Phases 0-3): Railway
- **Platform**: Railway.app
- **Region**: Multi-region (US/EU)
- **Database**: Railway PostgreSQL
- **Rationale**:
  - Fast deployment (GitHub auto-deploy)
  - Low operational overhead
  - No long-term commitment
  - Good for MVP validation
  - Cost-effective for testing ($20-50/month)

#### Production Phase (Phase 4+): GCP Dammam
- **Platform**: Google Cloud Platform
- **Region**: `me-central1` (Dammam, Saudi Arabia)
- **Database**: Cloud SQL PostgreSQL
- **Compute**: Cloud Run (serverless containers)
- **Rationale**:
  - Meets Saudi data residency requirements
  - Native Vertex AI integration (no cross-region API calls)
  - Enterprise-grade security and compliance
  - Scalable infrastructure

### Migration Path

```
Phase 0-3: Railway (Testing)
├─ Validate product-market fit
├─ Test AI models and prompts
├─ Iterate on features
└─ Use non-production customer data

Phase 4: Migration to GCP Dammam
├─ Week 1: Set up GCP infrastructure
├─ Week 2: Migrate database (export/import)
├─ Week 3: Deploy services to Cloud Run
├─ Week 4: DNS cutover + monitoring
└─ Production launch with real customer data
```

### Trade-offs

| Aspect | Railway (Testing) | GCP Dammam (Production) |
|--------|------------------|------------------------|
| Setup Time | 1 hour | 1 week |
| Data Residency | ❌ US/EU | ✅ Saudi Arabia |
| AI Integration | OpenAI API | Vertex AI (in-region) |
| Cost (estimated) | $50/month | $300-500/month |
| Scalability | Limited | High |
| Compliance | Not compliant | ✅ Compliant |

### Implementation Notes

- Keep infrastructure-as-code (Terraform) ready for GCP
- Design services to be cloud-agnostic (12-factor app)
- Document migration checklist in Phase 4
- Test database backup/restore procedures early

---

## Decision 2: LLM Provider & AI Strategy

### Context

JisrVoC requires LLMs for:
- Feedback classification (bug, feature, complaint, etc.)
- Text embeddings for semantic clustering
- Sentiment analysis
- Theme name generation
- Product bet recommendations

Key considerations:
- Cost per API call
- Latency requirements
- Data privacy and residency
- Model quality and multilingual support (Arabic + English)

### Decision

**Two-Phase AI Strategy**

#### Testing Phase: OpenAI API
- **Classification**: `gpt-4o-mini` (fast, cheap, good quality)
- **Embeddings**: `text-embedding-3-small` (512 dimensions, $0.02/1M tokens)
- **Theme Generation**: `gpt-4o` (better reasoning for creative tasks)
- **Rationale**:
  - Best-in-class models for rapid prototyping
  - Simple API, great documentation
  - Multilin gual support (Arabic + English)
  - Pay-as-you-go pricing
  - Can test different models easily

**Estimated Testing Costs**:
```
100,000 feedback items classified:
- Classification: 100k × $0.15/1M tokens ≈ $15
- Embeddings: 100k × $0.02/1M tokens ≈ $2
- Sentiment: 100k × $0.15/1M tokens ≈ $15
Total: ~$32/month for testing phase
```

#### Production Phase: GCP Vertex AI
- **Classification**: `gemini-2.0-flash-exp` (fast inference)
- **Embeddings**: `text-embedding-004` (768 dimensions, multilingual)
- **Theme Generation**: `gemini-2.0-flash-exp` (good balance)
- **Rationale**:
  - Data stays in Saudi region (me-central1)
  - Native GCP integration
  - Enterprise SLA and support
  - Competitive pricing
  - Strong multilingual capabilities

### LLM Provider Abstraction Layer

To enable seamless switching between providers, we implement an abstraction:

```python
# app/ai/llm_provider.py

class BaseLLMProvider(ABC):
    @abstractmethod
    async def generate_completion(prompt: str, model: str) -> str: ...

    @abstractmethod
    async def generate_embedding(text: str) -> list[float]: ...

    @abstractmethod
    async def generate_structured_output(prompt: str, schema: dict) -> dict: ...

class OpenAIProvider(BaseLLMProvider):
    # OpenAI implementation

class VertexAIProvider(BaseLLMProvider):
    # Vertex AI implementation

# Factory pattern for easy switching
def create_provider(provider_type: LLMProvider) -> BaseLLMProvider:
    if provider_type == LLMProvider.OPENAI:
        return OpenAIProvider()
    elif provider_type == LLMProvider.VERTEX_AI:
        return VertexAIProvider()
```

**Environment Configuration**:
```bash
# Testing (Railway)
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...

# Production (GCP)
LLM_PROVIDER=vertex_ai
GCP_PROJECT_ID=jisrvoc-production
GCP_REGION=me-central1
```

### Model Selection Guidelines

| Task | Testing (OpenAI) | Production (Vertex AI) | Notes |
|------|-----------------|----------------------|-------|
| Classification | gpt-4o-mini | gemini-2.0-flash-exp | Speed matters |
| Embeddings | text-embedding-3-small | text-embedding-004 | Clustering quality |
| Sentiment | gpt-4o-mini | gemini-2.0-flash-exp | Simple task |
| Theme Names | gpt-4o | gemini-2.0-flash-exp | Creative task |
| Bet Generation | gpt-4o | gemini-2.0-flash-exp | Strategic reasoning |

### Multilingual Considerations

Both OpenAI and Vertex AI models support Arabic and English:
- Embeddings are language-agnostic (semantic similarity works cross-language)
- Classification prompts should include examples in both languages
- Theme generation should detect input language and respond accordingly

### Migration Plan

1. **Phase 1-3**: Use OpenAI exclusively
2. **Phase 4 Week 1**: Implement Vertex AI provider
3. **Phase 4 Week 2**: Test Vertex AI with subset of data
4. **Phase 4 Week 3**: Compare quality (classification accuracy, embedding similarity)
5. **Phase 4 Week 4**: Switch to Vertex AI in production

---

## Decision 3: HubSpot Integration & Field Mapping

### Context

HubSpot serves as the primary CRM and ticketing system. We need to:
- Sync support tickets from HubSpot → JisrVoC
- Map HubSpot fields to JisrVoC internal schema
- Handle custom properties
- Support bidirectional sync (write-back in Phase 4)

### Decision

**HubSpot Connector with Field Mapping Configuration**

#### Required HubSpot Objects
1. **Tickets** (primary source of feedback)
2. **Contacts** (customer information)
3. **Companies** (B2B account data)

#### Field Mapping: HubSpot Tickets → JisrVoC Feedback

| HubSpot Field | JisrVoC Field | Type | Notes |
|---------------|---------------|------|-------|
| `id` | `external_id` | string | Unique identifier |
| `subject` | `title` | string | Ticket subject line |
| `content` | `content` | text | Full ticket description |
| `hs_ticket_priority` | `priority` | enum | HIGH, MEDIUM, LOW |
| `hs_ticket_category` | `category_hint` | string | Used for classification |
| `createdate` | `created_at` | datetime | Ticket creation time |
| `hs_lastmodifieddate` | `updated_at` | datetime | Last update time |
| `source_type` | `source_channel` | enum | Email, Chat, Form, Phone |
| `hs_pipeline_stage` | `status` | enum | Open, In Progress, Closed |

#### Custom Properties (Company-Specific)

```json
{
  "custom_field_mapping": {
    "product_area": "hs_custom_product_module",
    "customer_tier": "hs_customer_segment",
    "renewal_date": "hs_renewal_date",
    "arr_value": "hs_arr"
  }
}
```

**Configuration file**: `app/connectors/hubspot_mapping.json`

#### Contact & Company Mapping

**HubSpot Contact → JisrVoC Customer**:
```
email → email
firstname + lastname → name
company → company_name
hs_customer_tier → tier
createdate → first_seen_at
```

**HubSpot Company → JisrVoC Company**:
```
domain → domain
name → company_name
industry → industry
annualrevenue → arr
hs_num_decision_makers → decision_maker_count
```

### OAuth Scopes Required

```
crm.objects.contacts.read
crm.objects.companies.read
tickets
```

### Sync Strategy

**Initial Sync**: Pull last 90 days of tickets
**Incremental Sync**: Every 6 hours, pull tickets updated since last sync
**Rate Limit**: 10 requests/second (Professional tier)

### Implementation Notes

See: `.claude/skills/connector-development/SKILL.md` for implementation patterns.

---

## Decision 4: Zendesk Integration & Field Mapping

### Context

Zendesk is the secondary support ticket source. Many customers use both HubSpot (sales CRM) and Zendesk (support tickets).

### Decision

**Zendesk Connector with Incremental Export API**

#### Field Mapping: Zendesk Tickets → JisrVoC Feedback

| Zendesk Field | JisrVoC Field | Type | Notes |
|---------------|---------------|------|-------|
| `id` | `external_id` | integer | Unique identifier |
| `subject` | `title` | string | Ticket subject |
| `description` | `content` | text | First comment (ticket body) |
| `priority` | `priority` | enum | urgent, high, normal, low |
| `type` | `category_hint` | enum | problem, incident, question, task |
| `status` | `status` | enum | new, open, pending, solved, closed |
| `created_at` | `created_at` | datetime | Ticket creation |
| `updated_at` | `updated_at` | datetime | Last update |
| `channel` | `source_channel` | enum | web, email, chat, voice, api |
| `tags` | `tags` | array | Product/team tags |
| `satisfaction_rating.score` | `satisfaction_score` | enum | good, bad |

#### User & Organization Mapping

**Zendesk User → JisrVoC Customer**:
```
id → external_id
email → email
name → name
organization_id → company_external_id
role → role (end-user, agent, admin)
```

**Zendesk Organization → JisrVoC Company**:
```
id → external_id
name → company_name
domain_names[0] → domain
```

### API Strategy

**Use Incremental Ticket Export**:
```
GET /api/v2/incremental/tickets.json?start_time={unix_timestamp}
```
- More efficient than paginating all tickets
- Returns tickets updated since timestamp
- 1000 tickets per request

### Rate Limits

- **Standard Plan**: 200 requests/minute (global)
- **Implementation**: Token bucket rate limiter at 180 req/min (safety buffer)

### Sync Strategy

**Initial Sync**: Pull last 30 days
**Incremental Sync**: Every 6 hours
**Comment Handling**: Fetch first comment only (ticket description), skip internal notes

---

## Decision 5: Feature Request Tool (Canny vs Jira)

### Context

Need to capture feature requests from customers and link them to product bets. Two options:
1. **Canny**: Purpose-built for customer feature requests (public roadmap, voting)
2. **Jira**: General project management (more complex, engineering-focused)

### Decision

**Start with Canny, defer Jira to Phase 5 (V2)**

#### Rationale for Canny

**Pros**:
- Simple API (RESTful, well-documented)
- Built for customer-facing feature requests
- Public roadmap feature (customers can vote)
- Easier to integrate with feedback themes
- Better UX for non-technical stakeholders

**Cons**:
- Limited to feature requests (no bug tracking)
- Less flexible than Jira
- Additional tool in stack

#### Rationale Against Jira (for now)

- More complex API (requires understanding of projects, issue types, workflows)
- Overhead of configuration (custom fields, workflows, permissions)
- Engineering-focused (less customer-friendly)
- Can add later if Canny insufficient

### Canny Integration Plan

**Phase 1**: Read-only integration
- Sync existing feature requests → JisrVoC database
- Display in "Product Bets" view
- Link themes to feature requests

**Phase 4**: Bidirectional sync
- Auto-create Canny posts from high-confidence themes
- Update Canny status when bets ship
- Sync votes/comments back to JisrVoC

### Field Mapping: Canny Post → JisrVoC Bet

| Canny Field | JisrVoC Field | Notes |
|-------------|---------------|-------|
| `id` | `external_id` | Unique identifier |
| `title` | `title` | Feature request title |
| `details` | `description` | Detailed description |
| `score` | `customer_demand_score` | Vote score |
| `status` | `status` | planned, in progress, complete |
| `board.name` | `product_area` | Which product |
| `created` | `created_at` | Creation time |

### API Scope

```
read:posts
read:boards
write:posts (Phase 4)
```

### Jira Deferral

If Canny proves insufficient in Phase 3-4, we can add Jira in Phase 5 (V2):
- Use Jira for internal engineering tasks
- Use Canny for customer-facing roadmap
- Sync between Canny ↔ Jira ↔ JisrVoC

---

## Decision 6: Customer Identity Resolution

### Context

Customers appear across multiple systems:
- HubSpot contacts
- Zendesk users
- Canny voters/commenters
- Different email addresses, name variations

Need to resolve these into single unified customer profiles.

### Decision

**Email Domain Matching for B2B, with Manual Merge UI**

#### Primary Strategy: Email Domain (B2B Focus)

For B2B customers, match by company domain:

```
john@acme.com (HubSpot)
jane@acme.com (Zendesk)
→ Both belong to "Acme Corp"
```

**Implementation**:
```python
def resolve_customer_identity(email: str, name: str) -> Customer:
    domain = extract_domain(email)  # "acme.com"

    # Find or create company by domain
    company = Company.find_or_create(domain=domain)

    # Find existing customer in company
    customer = Customer.find_by_email_or_name(
        email=email,
        name=name,
        company_id=company.id
    )

    return customer
```

#### Fallback Strategy: Fuzzy Name Match

For generic domains (gmail.com, outlook.com):
- Use fuzzy name matching (Levenshtein distance)
- Confidence threshold: 85%
- Flag low-confidence matches for manual review

#### Manual Merge UI (Phase 3)

Build admin interface to:
- View potential duplicate customers
- Manually merge profiles
- Set merge rules (e.g., always merge john.doe / johndoe)

### Edge Cases

1. **Multiple Roles**: Person changes companies
   - Solution: Track customer-company relationships with date ranges

2. **Name Variations**: "John Smith" vs "J. Smith" vs "Smith, John"
   - Solution: Normalize names, use fuzzy matching

3. **Shared Email**: support@company.com used by multiple people
   - Solution: Flag as shared account, track by ticket metadata

### Data Model

```python
class Customer(Base):
    id: int
    primary_email: str
    alternative_emails: list[str]  # All known emails
    name: str
    company_id: int
    external_ids: dict  # {"hubspot": "123", "zendesk": "456"}
    merged_from: list[int]  # IDs of merged customers

class Company(Base):
    id: int
    domain: str  # Primary matching key for B2B
    name: str
    industry: str
```

### Implementation Priority

- **Phase 1**: Basic email matching
- **Phase 2**: Domain-based company matching
- **Phase 3**: Manual merge UI + fuzzy matching

---

## Decision 7: Write-Back Strategy (Phase 4)

### Context

After analyzing feedback, we want to push insights back to source systems:
- Update HubSpot tickets with theme tags
- Create Canny posts for high-demand themes
- Add notes to customer records

### Decision

**Start with HubSpot Notes, Add Canny Auto-Creation in Phase 4**

#### Phase 1-3: Read-Only
- No write-back yet
- Focus on data collection and analysis

#### Phase 4: HubSpot Notes
- Post theme summaries as HubSpot notes on tickets
- Tag tickets with theme names (custom property)
- Safe, auditable, reversible

**Example Note**:
```
🤖 JisrVoC Analysis

This ticket is part of theme: "Mobile App Login Issues"
- 47 similar feedback items
- High priority (urgency score: 8.5/10)
- Affecting Enterprise customers

Recommended Action: Investigate authentication flow on iOS 17+

Generated on 2026-06-30
```

#### Phase 4: Canny Auto-Creation
- Auto-create Canny posts for themes with:
  - 20+ feedback items
  - 3+ customers affected
  - Confidence score > 0.85
- Include:
  - Theme description
  - Customer quotes (anonymized)
  - Business impact

### Safety Measures

1. **Dry-Run Mode**: Preview changes before writing
2. **Rate Limiting**: Max 10 writes/minute
3. **Audit Log**: Track all write-back operations
4. **Rollback**: Keep original data, mark as "enriched by JisrVoC"

### Future: Bidirectional Sync (Phase 5)

- Sync HubSpot ticket status → JisrVoC
- Sync Canny votes → Customer demand score
- Handle conflicts (last-write-wins with timestamp)

---

## Implementation Checklist

### Phase 0 (This Document)
- [x] Document all architecture decisions
- [x] Define testing → production migration path
- [x] Establish LLM provider strategy
- [x] Map external system fields
- [ ] Review and approve decisions

### Phase 1 (Foundation)
- [ ] Implement LLM provider abstraction
- [ ] Build HubSpot connector with field mapping
- [ ] Build Zendesk connector with field mapping
- [ ] Implement customer identity resolution
- [ ] Set up OpenAI API integration

### Phase 4 (Loop Closure)
- [ ] Implement HubSpot write-back (notes)
- [ ] Implement Canny auto-creation
- [ ] Add write-back audit logging

### Phase 4 (Production Migration)
- [ ] Set up GCP Dammam infrastructure
- [ ] Implement Vertex AI provider
- [ ] Migrate database to Cloud SQL
- [ ] Deploy to Cloud Run
- [ ] Update DNS

---

## Appendix: Configuration Files

### Environment Variables (Testing)

```bash
# Railway Environment
USE_MOCK_DATA=false
DATABASE_URL=postgresql+asyncpg://...

# LLM
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...

# HubSpot
HUBSPOT_API_KEY=pat-na1-...

# Zendesk
ZENDESK_EMAIL=admin@company.com
ZENDESK_API_TOKEN=...
ZENDESK_SUBDOMAIN=company

# Canny
CANNY_API_KEY=...
```

### Environment Variables (Production)

```bash
# GCP Environment
USE_MOCK_DATA=false
DATABASE_URL=postgresql+asyncpg://...

# LLM
LLM_PROVIDER=vertex_ai
GCP_PROJECT_ID=jisrvoc-production
GCP_REGION=me-central1

# Same connector credentials
HUBSPOT_API_KEY=...
ZENDESK_EMAIL=...
# ... etc
```

---

## Review & Approval

**Decision Owner**: Technical Lead
**Reviewed By**: Product, Engineering
**Approved**: 2026-06-29
**Next Review**: After Phase 3 completion

**Changelog**:
- 2026-06-29: Initial version, all 7 decisions documented
