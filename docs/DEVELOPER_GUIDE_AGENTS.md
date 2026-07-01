# Developer Guide: Agent System

**Audience**: Software Engineers
**Purpose**: Build new agents, test, debug, and optimize
**Last Updated**: 2026-07-01

---

## Table of Contents

1. [Creating a New Agent](#creating-a-new-agent)
2. [BaseAgent API](#baseagent-api)
3. [Testing Patterns](#testing-patterns)
4. [Debugging Agent Decisions](#debugging-agent-decisions)
5. [Performance Optimization](#performance-optimization)
6. [Common Pitfalls](#common-pitfalls)

---

## Creating a New Agent

### Step 1: Design Your Agent

Before coding, answer these questions:

**Purpose**: What problem does this agent solve?
- ❌ Bad: "Process feedback"
- ✅ Good: "Extract pricing objections from negative sentiment feedback"

**Inputs**: What context does it need from previous agents?
- Example: `context["sentiment"]`, `context["product_area"]`

**Outputs**: What does it add to the enrichment?
- Example: `tags_added=["pricing_objection"]`, `metadata={"price_mentioned": "$500"}`

**Dependencies**: What external services does it need?
- Examples: OpenAI API, database, Redis, external API

**Performance Target**: How fast must it be?
- Rule of thumb: <100ms for rule-based, <300ms for LLM-based

### Step 2: Create Agent Class

**File**: `app/agents/my_new_agent.py`

```python
"""
MyNewAgent: Extract pricing objections from feedback.

Purpose:
    Identifies when customers mention pricing as a barrier or objection.

Responsibilities:
    - Detect pricing-related keywords
    - Extract mentioned prices
    - Flag pricing objections for sales team review

Inputs:
    - context["sentiment"]: Must be negative/neutral
    - context["product_area"]: Any area
    - raw_text: Full feedback content

Outputs:
    - tags_added: ["pricing_objection"]
    - metadata["price_mentioned"]: Extracted price (e.g., "$500")
    - metadata["objection_type"]: "too_expensive" | "missing_feature" | "competitor_cheaper"
"""

import logging
import re
from typing import Dict, Any, Optional
from .base_agent import BaseAgent, AgentResult, AgentStatus

logger = logging.getLogger(__name__)


class MyNewAgent(BaseAgent):
    """Extract pricing objections from negative feedback."""

    def __init__(self):
        """Initialize agent with pricing keyword patterns."""
        super().__init__(name="my_new_agent")

        # Pricing keywords (English + Arabic)
        self.pricing_keywords = {
            "en": ["expensive", "costly", "price", "pricing", "cost", "cheap", "afford"],
            "ar": ["غالي", "سعر", "تكلفة", "رخيص"],
        }

        # Price extraction pattern
        self.price_pattern = re.compile(r"\$?\d+(?:,\d{3})*(?:\.\d{2})?(?:\s*(?:SAR|USD|SR))?")

    async def _execute(
        self,
        feedback_id: str,
        raw_text: str,
        language: str,
        context: Dict[str, Any],
    ) -> AgentResult:
        """
        Main execution logic.

        Args:
            feedback_id: Unique feedback identifier
            raw_text: Full feedback text
            language: "EN" or "AR"
            context: Accumulated context from previous agents

        Returns:
            AgentResult with pricing objection data
        """
        try:
            # Check prerequisites
            sentiment = context.get("sentiment", "").lower()
            if sentiment not in ["negative", "neutral", "frustrated"]:
                # Skip processing for positive sentiment
                return AgentResult(
                    agent_name=self.name,
                    status=AgentStatus.SKIPPED,
                    metadata={"reason": "Positive sentiment, no pricing objection expected"},
                    execution_time_ms=0.5,
                )

            # Detect pricing keywords
            keywords = self.pricing_keywords.get(language.lower(), self.pricing_keywords["en"])
            text_lower = raw_text.lower()

            matched_keywords = [kw for kw in keywords if kw in text_lower]

            if not matched_keywords:
                # No pricing keywords found
                return AgentResult(
                    agent_name=self.name,
                    status=AgentStatus.SUCCESS,
                    tags_added=[],
                    metadata={"has_pricing_objection": False},
                    execution_time_ms=2.0,
                )

            # Extract mentioned prices
            prices = self.price_pattern.findall(raw_text)

            # Determine objection type
            objection_type = self._classify_objection_type(raw_text, matched_keywords)

            # Build result
            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.SUCCESS,
                tags_added=["pricing_objection", f"objection:{objection_type}"],
                confidence_scores={"pricing_objection": 0.85},
                metadata={
                    "has_pricing_objection": True,
                    "matched_keywords": matched_keywords,
                    "prices_mentioned": prices,
                    "objection_type": objection_type,
                    "reasoning": f"Detected pricing objection ({objection_type}): matched keywords {matched_keywords}",
                },
                execution_time_ms=5.0,
            )

        except Exception as e:
            logger.error(
                f"Agent {self.name} failed",
                extra={"feedback_id": feedback_id, "error": str(e)},
                exc_info=True,
            )

            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.ERROR,
                error_message=str(e),
                execution_time_ms=1.0,
            )

    def _classify_objection_type(self, text: str, keywords: list) -> str:
        """
        Classify the type of pricing objection.

        Args:
            text: Raw feedback text
            keywords: Matched pricing keywords

        Returns:
            Objection type: "too_expensive" | "missing_feature" | "competitor_cheaper"
        """
        text_lower = text.lower()

        # Check for competitor mentions
        if any(comp in text_lower for comp in ["competitor", "alternative", "other system"]):
            return "competitor_cheaper"

        # Check for missing feature complaints
        if any(word in text_lower for word in ["should include", "missing", "need", "want"]):
            return "missing_feature"

        # Default: too expensive
        return "too_expensive"
```

### Step 3: Register in Orchestrator

**File**: `app/agents/orchestrator.py`

```python
from .my_new_agent import MyNewAgent

class AgentOrchestrator:
    def __init__(
        self,
        rule_engine: RuleEngine,
        theme_repository: ThemeRepository,
    ):
        self.agents = {
            "triage": TriageAgent(rule_engine),
            "llm": LLMAgent(),
            "my_new_agent": MyNewAgent(),  # ← Add here
            "embedding": EmbeddingAgent(theme_repository),
        }
```

**Execution Order Matters!**

Agents run in dictionary insertion order (Python 3.7+):
1. `triage` → Product area classification
2. `llm` → Sentiment/urgency
3. `my_new_agent` → Can use sentiment from LLM agent
4. `embedding` → Theme matching

If your agent needs `sentiment`, place it **after** `llm` agent.

### Step 4: Add Unit Tests

**File**: `tests/agents/test_my_new_agent.py`

```python
import pytest
from app.agents.my_new_agent import MyNewAgent
from app.agents.base_agent import AgentStatus


@pytest.mark.asyncio
class TestMyNewAgent:
    """Test suite for MyNewAgent."""

    @pytest.fixture
    def agent(self):
        """Create agent instance."""
        return MyNewAgent()

    async def test_detects_pricing_objection(self, agent):
        """Test that agent detects pricing objections."""
        # Arrange
        feedback_id = "123"
        raw_text = "Your system is too expensive at $5000 per month"
        language = "EN"
        context = {"sentiment": "Negative"}

        # Act
        result = await agent.execute(feedback_id, raw_text, language, context)

        # Assert
        assert result.status == AgentStatus.SUCCESS
        assert "pricing_objection" in result.tags_added
        assert result.metadata["has_pricing_objection"] is True
        assert "$5000" in result.metadata["prices_mentioned"]
        assert result.metadata["objection_type"] == "too_expensive"

    async def test_skips_positive_sentiment(self, agent):
        """Test that agent skips positive sentiment feedback."""
        # Arrange
        feedback_id = "124"
        raw_text = "Great value for the price!"
        language = "EN"
        context = {"sentiment": "Positive"}

        # Act
        result = await agent.execute(feedback_id, raw_text, language, context)

        # Assert
        assert result.status == AgentStatus.SKIPPED
        assert len(result.tags_added) == 0

    async def test_handles_no_pricing_keywords(self, agent):
        """Test that agent handles feedback without pricing keywords."""
        # Arrange
        feedback_id = "125"
        raw_text = "The interface is confusing"
        language = "EN"
        context = {"sentiment": "Negative"}

        # Act
        result = await agent.execute(feedback_id, raw_text, language, context)

        # Assert
        assert result.status == AgentStatus.SUCCESS
        assert result.metadata["has_pricing_objection"] is False

    async def test_classifies_competitor_objection(self, agent):
        """Test that agent identifies competitor pricing."""
        # Arrange
        feedback_id = "126"
        raw_text = "Competitor X offers this for half the price"
        language = "EN"
        context = {"sentiment": "Neutral"}

        # Act
        result = await agent.execute(feedback_id, raw_text, language, context)

        # Assert
        assert result.status == AgentStatus.SUCCESS
        assert result.metadata["objection_type"] == "competitor_cheaper"

    async def test_handles_arabic_keywords(self, agent):
        """Test Arabic pricing keyword detection."""
        # Arrange
        feedback_id = "127"
        raw_text = "النظام غالي جداً"  # "The system is very expensive"
        language = "AR"
        context = {"sentiment": "Negative"}

        # Act
        result = await agent.execute(feedback_id, raw_text, language, context)

        # Assert
        assert result.status == AgentStatus.SUCCESS
        assert result.metadata["has_pricing_objection"] is True
        assert "غالي" in result.metadata["matched_keywords"]

    async def test_handles_exception_gracefully(self, agent, monkeypatch):
        """Test error handling."""
        # Arrange
        def mock_classify(*args):
            raise ValueError("Simulated error")

        monkeypatch.setattr(agent, "_classify_objection_type", mock_classify)

        # Act
        result = await agent.execute("128", "test", "EN", {"sentiment": "Negative"})

        # Assert
        assert result.status == AgentStatus.ERROR
        assert "Simulated error" in result.error_message
```

### Step 5: Add Integration Test

**File**: `tests/integration/test_agent_pipeline.py`

```python
@pytest.mark.asyncio
async def test_new_agent_in_pipeline(db_session, rule_engine, theme_repository):
    """Test that new agent integrates correctly in full pipeline."""
    # Arrange
    orchestrator = AgentOrchestrator(
        rule_engine=rule_engine,
        theme_repository=theme_repository,
    )

    feedback_id = "999"
    raw_text = "Your pricing is too high compared to competitors"
    language = "EN"

    # Act
    success, enrichment, agent_results = await orchestrator.enrich_feedback(
        feedback_id=feedback_id,
        raw_text=raw_text,
        language=language,
    )

    # Assert
    assert success is True

    # Find new agent result
    my_new_agent_result = next(
        (r for r in agent_results if r.agent_name == "my_new_agent"),
        None,
    )

    assert my_new_agent_result is not None
    assert my_new_agent_result.status == AgentStatus.SUCCESS
    assert "pricing_objection" in my_new_agent_result.tags_added
```

### Step 6: Update Documentation

Add your agent to:

1. **Architecture doc** (`AGENT_ARCHITECTURE.md`):
   - Add agent to component list
   - Describe agent purpose and inputs/outputs

2. **PM guide** (`PM_GUIDE_TO_AGENTS.md`):
   - Add section on interpreting agent logs
   - Add common patterns PMs should recognize

3. **This guide** (you're reading it!):
   - Add example if it demonstrates new pattern

---

## BaseAgent API

### Abstract Base Class

**File**: [`app/agents/base_agent.py`](../app/agents/base_agent.py)

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Any, Optional, List
from enum import Enum
import time


class AgentStatus(Enum):
    """Agent execution status."""
    SUCCESS = "success"
    ERROR = "error"
    SKIPPED = "skipped"


@dataclass
class AgentResult:
    """Result from a single agent execution."""
    agent_name: str
    status: AgentStatus
    tags_added: List[str] = None
    confidence_scores: Dict[str, float] = None
    metadata: Dict[str, Any] = None
    error_message: Optional[str] = None
    execution_time_ms: float = 0.0

    def __post_init__(self):
        """Initialize mutable defaults."""
        if self.tags_added is None:
            self.tags_added = []
        if self.confidence_scores is None:
            self.confidence_scores = {}
        if self.metadata is None:
            self.metadata = {}


class BaseAgent(ABC):
    """
    Abstract base class for all agents.

    Subclasses must implement _execute() method.
    """

    def __init__(self, name: str):
        """
        Initialize agent.

        Args:
            name: Unique agent identifier
        """
        self.name = name

    async def execute(
        self,
        feedback_id: str,
        raw_text: str,
        language: str,
        context: Dict[str, Any],
    ) -> AgentResult:
        """
        Execute agent with timing and error handling.

        This method wraps _execute() with:
        - Execution time tracking
        - Error handling
        - Logging

        Args:
            feedback_id: Unique feedback identifier
            raw_text: Full feedback content
            language: "EN" or "AR"
            context: Accumulated context from previous agents

        Returns:
            AgentResult with status, tags, and metadata
        """
        start_time = time.time()

        try:
            result = await self._execute(feedback_id, raw_text, language, context)
            result.execution_time_ms = (time.time() - start_time) * 1000
            return result

        except Exception as e:
            execution_time_ms = (time.time() - start_time) * 1000
            return AgentResult(
                agent_name=self.name,
                status=AgentStatus.ERROR,
                error_message=str(e),
                execution_time_ms=execution_time_ms,
            )

    @abstractmethod
    async def _execute(
        self,
        feedback_id: str,
        raw_text: str,
        language: str,
        context: Dict[str, Any],
    ) -> AgentResult:
        """
        Agent-specific execution logic.

        Subclasses must implement this method.

        Args:
            feedback_id: Unique feedback identifier
            raw_text: Full feedback content
            language: "EN" or "AR"
            context: Accumulated context from previous agents

        Returns:
            AgentResult with status, tags, and metadata

        Raises:
            Exception: Any error during execution (caught by execute())
        """
        pass
```

### Agent Lifecycle

```
┌──────────────────────────────────────────────────┐
│         AgentOrchestrator.enrich_feedback()      │
└───────────────────┬──────────────────────────────┘
                    │
        ┌───────────┼───────────┐
        ▼           ▼           ▼
   ┌────────┐  ┌────────┐  ┌────────┐
   │ Triage │  │  LLM   │  │Embedding│
   │ Agent  │  │ Agent  │  │ Agent  │
   └────────┘  └────────┘  └────────┘
        │           │           │
        │   execute(feedback_id, raw_text, language, context)
        │           │           │
        ├───────────┼───────────┤
        │   Timing, error handling, logging
        │           │           │
        ▼           ▼           ▼
   ┌────────┐  ┌────────┐  ┌────────┐
   │_execute│  │_execute│  │_execute│
   │(impl)  │  │(impl)  │  │(impl)  │
   └────────┘  └────────┘  └────────┘
        │           │           │
        └───────────┼───────────┘
                    ▼
          AgentResult returned
                    │
        ┌───────────┼───────────┐
        │  Add to context         │
        │  context.update(result) │
        └─────────────────────────┘
```

### Context Accumulation Pattern

```python
# Initial context (empty)
context = {}

# After Triage Agent
result = await triage_agent.execute(..., context)
context.update(result.metadata)
# context = {"product_area": "Payroll", "confidence": 0.95}

# After LLM Agent (adds to context)
result = await llm_agent.execute(..., context)
context.update(result.metadata)
# context = {"product_area": "Payroll", "confidence": 0.95,
#            "sentiment": "Negative", "urgency": "High"}

# After MyNewAgent (uses sentiment from context)
result = await my_new_agent.execute(..., context)
context.update(result.metadata)
# context = {..., "has_pricing_objection": True, "objection_type": "too_expensive"}
```

---

## Testing Patterns

### Unit Testing Best Practices

#### 1. Test Success Path

```python
async def test_agent_success(agent):
    """Test normal successful execution."""
    result = await agent.execute("123", "test feedback", "EN", {})
    assert result.status == AgentStatus.SUCCESS
    assert len(result.tags_added) > 0
```

#### 2. Test Skip Conditions

```python
async def test_agent_skips_when_missing_context(agent):
    """Test agent skips when prerequisites not met."""
    result = await agent.execute("123", "test", "EN", {})  # Empty context
    assert result.status == AgentStatus.SKIPPED
    assert "reason" in result.metadata
```

#### 3. Test Error Handling

```python
async def test_agent_handles_exception(agent, monkeypatch):
    """Test error handling."""
    def mock_method(*args):
        raise ValueError("Test error")

    monkeypatch.setattr(agent, "_some_method", mock_method)

    result = await agent.execute("123", "test", "EN", {})
    assert result.status == AgentStatus.ERROR
    assert "Test error" in result.error_message
```

#### 4. Test Edge Cases

```python
@pytest.mark.parametrize("text,expected_tags", [
    ("", []),  # Empty text
    ("   ", []),  # Whitespace only
    ("a" * 10000, ["long_text"]),  # Very long text
    ("مرحبا", ["arabic"]),  # Non-ASCII
])
async def test_agent_edge_cases(agent, text, expected_tags):
    """Test edge cases."""
    result = await agent.execute("123", text, "EN", {})
    assert set(result.tags_added) == set(expected_tags)
```

### Integration Testing

```python
@pytest.mark.asyncio
async def test_full_pipeline(db_session):
    """Test complete pipeline with all agents."""
    # Arrange
    orchestrator = AgentOrchestrator(...)
    feedback_id = "123"
    raw_text = "GOSI integration broken"

    # Act
    success, enrichment, agent_results = await orchestrator.enrich_feedback(
        feedback_id=feedback_id,
        raw_text=raw_text,
        language="EN",
    )

    # Assert
    assert success is True
    assert len(agent_results) == 3  # triage, llm, embedding

    # Verify all agents succeeded
    for result in agent_results:
        assert result.status in [AgentStatus.SUCCESS, AgentStatus.SKIPPED]

    # Verify enrichment has required fields
    assert "product_area" in enrichment
    assert "sentiment" in enrichment
    assert "theme_id" in enrichment or "theme_decision" in enrichment
```

### Performance Testing

```python
import pytest
import asyncio


@pytest.mark.asyncio
async def test_agent_latency(agent):
    """Test agent completes within performance target."""
    start = time.time()

    result = await agent.execute("123", "test feedback", "EN", {})

    elapsed_ms = (time.time() - start) * 1000

    # Rule-based agents should be <50ms
    assert elapsed_ms < 50.0
    assert result.execution_time_ms < 50.0


@pytest.mark.asyncio
async def test_pipeline_latency():
    """Test full pipeline completes within target."""
    orchestrator = AgentOrchestrator(...)

    start = time.time()

    success, enrichment, agent_results = await orchestrator.enrich_feedback(
        feedback_id="123",
        raw_text="Test feedback",
        language="EN",
    )

    elapsed_ms = (time.time() - start) * 1000

    # Full pipeline should be <400ms
    assert elapsed_ms < 400.0

    # Log per-agent timing
    for result in agent_results:
        print(f"{result.agent_name}: {result.execution_time_ms}ms")
```

### Mocking External Dependencies

```python
import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def mock_openai():
    """Mock OpenAI API."""
    mock = AsyncMock()
    mock.chat.completions.create = AsyncMock(return_value={
        "choices": [{"message": {"content": "Mocked response"}}]
    })
    return mock


@pytest.mark.asyncio
async def test_llm_agent_with_mock(mock_openai, monkeypatch):
    """Test LLM agent with mocked API."""
    monkeypatch.setattr("openai.AsyncOpenAI", lambda: mock_openai)

    agent = LLMAgent()
    result = await agent.execute("123", "test", "EN", {})

    assert result.status == AgentStatus.SUCCESS
    mock_openai.chat.completions.create.assert_called_once()
```

---

## Debugging Agent Decisions

### Step 1: Enable Debug Logging

**File**: `.env` or deployment config

```bash
LOG_LEVEL=DEBUG
```

This will log detailed agent execution:

```
2026-07-01 15:30:00 DEBUG Agent triage started: feedback_id=123
2026-07-01 15:30:00 DEBUG Matched keywords: ['GOSI', 'salary']
2026-07-01 15:30:00 DEBUG Classification: product_area=Payroll, confidence=0.95
2026-07-01 15:30:00 DEBUG Agent triage completed: 5.2ms
```

### Step 2: Add Breakpoints

```python
class MyNewAgent(BaseAgent):
    async def _execute(self, feedback_id, raw_text, language, context):
        # Add breakpoint for debugging
        import pdb; pdb.set_trace()

        # Or use ipdb for better experience
        # import ipdb; ipdb.set_trace()

        # Your logic here
        ...
```

Run with debugger:

```bash
python -m pytest tests/agents/test_my_new_agent.py::test_my_method -s
```

### Step 3: Inspect Agent Results in API Response

Call enrichment endpoint and examine `agent_results`:

```bash
curl -X POST "https://api.jisrvoc.com/api/v1/feedback/enrich?feedback_id=123" | jq '.agent_results'
```

Look for:
- `status`: SUCCESS, ERROR, or SKIPPED?
- `tags_added`: What tags did agent add?
- `confidence_scores`: How confident?
- `metadata.reasoning`: Why this decision?
- `execution_time_ms`: How long did it take?

### Step 4: Compare Expected vs Actual

```python
# tests/agents/test_my_new_agent.py

async def test_debug_agent_decision(agent):
    """Debug specific feedback item."""
    # Arrange
    feedback_id = "123"
    raw_text = "Your pricing is too high"
    language = "EN"
    context = {"sentiment": "Negative"}

    # Act
    result = await agent.execute(feedback_id, raw_text, language, context)

    # Debug: Print full result
    print(f"\nAgent Result:")
    print(f"  Status: {result.status}")
    print(f"  Tags: {result.tags_added}")
    print(f"  Confidence: {result.confidence_scores}")
    print(f"  Metadata: {result.metadata}")

    # Expected behavior
    expected_tags = ["pricing_objection"]
    expected_objection_type = "too_expensive"

    # Assert and show diff
    assert result.tags_added == expected_tags, \
        f"Expected {expected_tags}, got {result.tags_added}"
    assert result.metadata["objection_type"] == expected_objection_type, \
        f"Expected {expected_objection_type}, got {result.metadata['objection_type']}"
```

Run test with output:

```bash
pytest tests/agents/test_my_new_agent.py::test_debug_agent_decision -s
```

### Step 5: Use Validation Report

Compare agent results with old pipeline:

```bash
python scripts/compare_pipelines.py --feedback-id 123 --show-reasoning
```

Output shows side-by-side comparison:

```
Feedback ID: 123
Old Pipeline: Billing → Finance
Agent Pipeline: Payroll (95% confidence)

Agent Reasoning:
  Triage: Matched GOSI keyword → Payroll scope
  LLM: Bug report with high urgency
  Embedding: 92% similarity to theme #23

Disagreement: YES
Recommendation: Review manually
```

---

## Performance Optimization

### Optimization Checklist

#### 1. Profile Agent Execution

```python
import cProfile
import pstats

profiler = cProfile.Profile()
profiler.enable()

# Run agent
result = await agent.execute("123", "test", "EN", {})

profiler.disable()
stats = pstats.Stats(profiler)
stats.sort_stats("cumtime")
stats.print_stats(20)  # Top 20 slowest functions
```

#### 2. Add Caching

**Example: Cache theme embeddings**

```python
from functools import lru_cache

class EmbeddingAgent(BaseAgent):
    @lru_cache(maxsize=1000)
    def _get_theme_embedding(self, theme_id: str):
        """Cache theme embeddings to avoid repeated DB queries."""
        return self.theme_repository.get_embedding(theme_id)
```

**Example: Cache rule engine results**

```python
from app.core.cache import get_redis

class RuleEngine:
    def match_l1_scope(self, text: str, language: str):
        """Match with Redis caching."""
        cache_key = f"rule:l1_scope:{language}:{hash(text)}"

        # Check cache
        cached = get_redis().get(cache_key)
        if cached:
            return json.loads(cached)

        # Compute
        result = self._match_l1_scope_uncached(text, language)

        # Cache for 1 hour
        get_redis().setex(cache_key, 3600, json.dumps(result))

        return result
```

#### 3. Parallelize Independent Operations

```python
import asyncio

class MyNewAgent(BaseAgent):
    async def _execute(self, feedback_id, raw_text, language, context):
        """Run independent operations in parallel."""

        # These can run in parallel
        price_task = asyncio.create_task(self._extract_prices(raw_text))
        keyword_task = asyncio.create_task(self._match_keywords(raw_text, language))
        objection_task = asyncio.create_task(self._classify_objection(raw_text))

        # Wait for all
        prices, keywords, objection_type = await asyncio.gather(
            price_task,
            keyword_task,
            objection_task,
        )

        return AgentResult(...)
```

#### 4. Optimize Database Queries

**Bad**:

```python
# N+1 query problem
for theme_id in theme_ids:
    theme = await db.query(Theme).filter(Theme.id == theme_id).first()
    embeddings.append(theme.embedding)
```

**Good**:

```python
# Single query with IN clause
themes = await db.query(Theme).filter(Theme.id.in_(theme_ids)).all()
embeddings = [t.embedding for t in themes]
```

#### 5. Add Query Indexes

```sql
-- Add index for theme similarity search
CREATE INDEX idx_themes_embedding ON themes USING ivfflat (embedding vector_cosine_ops);

-- Add index for feedback source
CREATE INDEX idx_feedback_source ON feedback (source);
```

### Performance Targets

| Agent Type | Target Latency | Optimization Strategy |
|------------|----------------|----------------------|
| **Rule-based** (Triage) | <50ms | Cache rules, optimize regex |
| **LLM-based** (LLM) | <300ms | Batch requests, use cheaper model |
| **Vector search** (Embedding) | <100ms | Add pgvector index, cache embeddings |
| **Full pipeline** | <400ms | Parallelize agents, optimize bottleneck |

---

## Common Pitfalls

### Pitfall 1: Modifying Context Directly

**❌ Bad**:

```python
async def _execute(self, feedback_id, raw_text, language, context):
    # DON'T modify context directly
    context["product_area"] = "Payroll"

    return AgentResult(...)
```

**✅ Good**:

```python
async def _execute(self, feedback_id, raw_text, language, context):
    # Return metadata, orchestrator will update context
    return AgentResult(
        metadata={"product_area": "Payroll"},
        ...
    )
```

**Why**: Context is shared across agents. Direct mutation can cause race conditions and makes debugging harder.

### Pitfall 2: Not Handling Missing Context

**❌ Bad**:

```python
async def _execute(self, feedback_id, raw_text, language, context):
    sentiment = context["sentiment"]  # KeyError if sentiment missing!
    ...
```

**✅ Good**:

```python
async def _execute(self, feedback_id, raw_text, language, context):
    sentiment = context.get("sentiment")

    if not sentiment:
        return AgentResult(
            status=AgentStatus.SKIPPED,
            metadata={"reason": "Missing required context: sentiment"},
        )

    # Continue with processing
    ...
```

### Pitfall 3: Swallowing Exceptions

**❌ Bad**:

```python
async def _execute(self, feedback_id, raw_text, language, context):
    try:
        result = self._do_work(raw_text)
        return AgentResult(...)
    except Exception:
        # Silent failure - orchestrator won't know!
        return AgentResult(status=AgentStatus.SUCCESS)
```

**✅ Good**:

```python
async def _execute(self, feedback_id, raw_text, language, context):
    try:
        result = self._do_work(raw_text)
        return AgentResult(...)
    except Exception as e:
        # Let exception propagate - BaseAgent.execute() will handle
        raise
        # Or return ERROR status
        return AgentResult(
            status=AgentStatus.ERROR,
            error_message=str(e),
        )
```

### Pitfall 4: Blocking I/O in Async Function

**❌ Bad**:

```python
async def _execute(self, feedback_id, raw_text, language, context):
    # Blocking call in async function!
    result = requests.get("https://api.example.com/data")
    ...
```

**✅ Good**:

```python
import httpx

async def _execute(self, feedback_id, raw_text, language, context):
    # Use async HTTP client
    async with httpx.AsyncClient() as client:
        result = await client.get("https://api.example.com/data")
    ...
```

### Pitfall 5: Not Testing with Real Data

**❌ Bad**:

```python
async def test_agent():
    result = await agent.execute("123", "test", "EN", {})
    assert result.status == AgentStatus.SUCCESS
```

**✅ Good**:

```python
# Use real feedback samples from database
REAL_FEEDBACK_SAMPLES = [
    "GOSI integration broken",
    "Need help with leave management",
    "الرواتب لا تعمل",  # Arabic example
]

@pytest.mark.parametrize("raw_text", REAL_FEEDBACK_SAMPLES)
async def test_agent_with_real_data(agent, raw_text):
    result = await agent.execute("123", raw_text, "EN", {})
    # Assert expected behavior for each sample
    ...
```

---

## Additional Resources

- **[Architecture Overview](AGENT_ARCHITECTURE.md)**: System architecture and agent flow
- **[PM Guide](PM_GUIDE_TO_AGENTS.md)**: How PMs read and update rules
- **[Operations Runbook](AGENT_RUNBOOK.md)**: Production troubleshooting
- **[BaseAgent Source](../app/agents/base_agent.py)**: Abstract base class implementation

---

**Questions?** Ask in #engineering-agents Slack channel.

**Document Status**: Complete
**Last Updated**: 2026-07-01
**Maintainer**: Engineering Team
