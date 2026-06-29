# Claude Skills for JisrVoC Backend

This directory contains Claude Code skills that provide context, workflows, and best practices for developing the JisrVoC backend.

## What are Claude Skills?

Skills are structured instructions that Claude Code loads on-demand to help with specific tasks. They use **progressive disclosure** - only the metadata loads initially (~100 tokens), with full instructions loading only when needed.

## Available Skills

### 🏗️ Foundation Skills

#### `project-context`
**Always load first.** Comprehensive overview of JisrVoC backend architecture, tech stack (FastAPI, SQLAlchemy, PostgreSQL), directory structure, and development conventions.

**Use when**: Starting any backend task, onboarding new developers, or needing architecture reference.

```bash
# How Claude uses it:
"I'm working on the backend, let me load the project-context skill first..."
```

### 🚀 Deployment & Infrastructure

#### `railway-deployment`
Deploy backend to Railway with environment variables, health checks, log monitoring, and rollback procedures.

**Use when**: Deploying code changes, troubleshooting deployment failures, setting up new Railway services.

#### `database-migrations`
Create and apply Alembic migrations for schema changes with testing and rollback strategies.

**Use when**: Adding tables/columns, modifying schema, deploying database changes to production.

### 🔌 Integration Skills

#### `connector-development`
Build HubSpot and Zendesk connectors with OAuth flows, rate limiting, pagination, and data synchronization patterns.

**Use when**: Implementing external API integrations, handling OAuth, managing rate limits, syncing data.

#### `ai-pipeline`
Integrate OpenAI/Vertex AI for text classification, embeddings, sentiment analysis, and theme generation with cost optimization.

**Use when**: Implementing AI enrichment, generating embeddings, classifying feedback, switching LLM providers.

### 🔄 Workflow Skills

#### `mock-to-real-data`
Transition from `USE_MOCK_DATA=true` to real database and API integrations with incremental rollout and testing procedures.

**Use when**: Switching from MVP mock data to production data, Phase 1 implementation, testing real data flows.

## How to Use Skills

### In Conversation with Claude

Simply mention the task, and Claude will automatically load relevant skills:

```
You: "I need to deploy the backend to Railway"
Claude: "I'll use the railway-deployment skill..."
[Loads skill and follows deployment workflow]

You: "Help me build the HubSpot connector"
Claude: "I'll use the connector-development skill..."
[Loads skill and guides through OAuth, rate limiting, etc.]
```

### Explicit Skill Loading

You can also explicitly request a skill:

```
You: "Load the project-context skill"
Claude: [Loads skill and provides architecture overview]

You: "Use the database-migrations skill to help me add a new table"
Claude: [Loads skill and guides through migration creation]
```

## Skill Structure

Each skill follows this pattern:

```
skills/
└── skill-name/
    ├── SKILL.md           # Main instructions (loaded on-demand)
    ├── REFERENCE.md       # Additional documentation (optional)
    └── scripts/           # Executable scripts (optional)
        └── script.sh
```

### YAML Frontmatter

Every skill has metadata for discovery:

```yaml
---
name: skill-identifier
description: Brief one-line description for Claude to understand when to use this skill
---
```

## Development Workflow Example

Here's how skills work together during development:

### Phase 0: Architecture Decision
```
You: "I want to understand the backend architecture"
→ Claude loads `project-context` skill
→ Explains three-layer pattern, tech stack, conventions
```

### Phase 1: Building Connector
```
You: "Let's build the HubSpot connector"
→ Claude loads `connector-development` skill
→ Guides through OAuth, rate limiting, data transformation
→ Creates app/connectors/hubspot.py following patterns
```

### Phase 1: Database Setup
```
You: "We need to add an embeddings column"
→ Claude loads `database-migrations` skill
→ Creates Alembic migration
→ Tests upgrade/downgrade locally
→ Deploys to Railway
```

### Phase 1: Deployment
```
You: "Deploy the changes to Railway"
→ Claude loads `railway-deployment` skill
→ Runs pre-flight checks
→ Commits and pushes code
→ Monitors deployment logs
→ Verifies health checks
```

### Phase 1: Data Transition
```
You: "Switch from mock data to real data"
→ Claude loads `mock-to-real-data` skill
→ Guides through incremental rollout
→ Tests each endpoint
→ Monitors for issues
```

## Best Practices

### 1. Load Project Context First
Always start sessions by loading `project-context` to ensure Claude understands the architecture.

### 2. Use Skills for Complex Tasks
Skills are most valuable for multi-step workflows like deployments, migrations, and integrations.

### 3. Combine Skills
Skills reference each other - Claude will load multiple skills if a task requires it.

### 4. Keep Skills Updated
As the project evolves, update skills to reflect new patterns, tools, and conventions.

## Customizing Skills

Skills are markdown files - you can edit them to:
- Add project-specific conventions
- Document new patterns
- Include team-specific workflows
- Add troubleshooting tips from real issues

## Progressive Disclosure Benefits

**Token Efficiency**: Six backend skills = ~600 tokens of metadata, but 20,000+ tokens of detailed guidance available on-demand.

**Context Preservation**: Claude doesn't waste context on unused skills - only loads what's needed for the current task.

**Scalability**: Can add unlimited reference materials without impacting Claude's ability to load skills.

## Related Documentation

- `/BACKEND_PLAN.md` - Complete implementation roadmap (Phases 0-5)
- `/app/core/config.py` - Environment configuration
- `/railway.json` - Railway deployment configuration
- `/alembic.ini` - Database migration configuration

## Support

For questions about skills or to suggest improvements:
1. Update the skill file directly
2. Document learnings from real issues
3. Share patterns that worked well

## Skill Development Guide

Want to create new skills? Follow this template:

```markdown
---
name: skill-identifier
description: Brief description for discovery
---

# Skill Title

## When to Use This Skill
[Describe scenarios where this skill applies]

## Prerequisites
- [ ] Checklist of requirements

## Workflow

### Step 1: [Action]
[Detailed instructions with code examples]

### Step 2: [Next Action]
[More instructions]

## Common Issues & Solutions
[Troubleshooting guide]

## Success Criteria
- [ ] Verification checklist

## Related Skills
- Link to related skills
```

---

**Current Status**: 6 skills covering deployment, development, integrations, and workflows.

**Next Steps**: Skills will expand as we implement Phases 1-5, adding patterns for clustering, theme generation, and production deployment.
