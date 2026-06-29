---
name: llm-integration-workflow
description: Integrate OpenAI/Vertex AI for classification, embeddings, sentiment analysis, and theme generation with cost optimization and error handling
---

# AI/LLM Integration Pipeline

## When to Use This Skill

Use this skill when:
- Implementing text classification for feedback
- Generating embeddings for semantic search and clustering
- Performing sentiment analysis
- Building AI-powered theme generation
- Migrating from OpenAI to Vertex AI (testing → production)

## Overview

JisrVoC uses LLMs to enrich customer feedback with:
1. **Classification**: Categorize feedback (bug, feature request, complaint, etc.)
2. **Embeddings**: Vector representations for clustering similar feedback
3. **Sentiment**: Analyze emotional tone (positive, negative, neutral)
4. **Theme Generation**: Create human-readable theme names from clusters

**Testing Phase**: OpenAI API (gpt-4o-mini, text-embedding-3-small)
**Production**: GCP Vertex AI (Gemini 2.0 Flash, text-embedding-004)

## Architecture Pattern: LLM Provider Abstraction

Create a provider-agnostic interface to support multiple LLM backends:

```python
# app/ai/llm_provider.py

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any

class LLMProvider(str, Enum):
    OPENAI = "openai"
    VERTEX_AI = "vertex_ai"

class BaseLLMProvider(ABC):
    """Abstract base for LLM providers."""

    @abstractmethod
    async def generate_completion(
        self,
        prompt: str,
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 500
    ) -> str:
        """Generate text completion."""
        pass

    @abstractmethod
    async def generate_embedding(
        self,
        text: str,
        model: str | None = None
    ) -> list[float]:
        """Generate text embedding."""
        pass

    @abstractmethod
    async def generate_structured_output(
        self,
        prompt: str,
        model: str,
        response_schema: dict[str, Any]
    ) -> dict[str, Any]:
        """Generate structured JSON output."""
        pass

class LLMFactory:
    """Factory for creating LLM providers."""

    @staticmethod
    def create(provider: LLMProvider) -> BaseLLMProvider:
        if provider == LLMProvider.OPENAI:
            from app.ai.providers.openai_provider import OpenAIProvider
            return OpenAIProvider()
        elif provider == LLMProvider.VERTEX_AI:
            from app.ai.providers.vertex_ai_provider import VertexAIProvider
            return VertexAIProvider()
        else:
            raise ValueError(f"Unknown provider: {provider}")
```

## OpenAI Provider Implementation

```python
# app/ai/providers/openai_provider.py

from openai import AsyncOpenAI
from app.ai.llm_provider import BaseLLMProvider
from app.core.config import settings

class OpenAIProvider(BaseLLMProvider):
    """OpenAI API provider."""

    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.default_model = "gpt-4o-mini"
        self.embedding_model = "text-embedding-3-small"

    async def generate_completion(
        self,
        prompt: str,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 500
    ) -> str:
        """Generate text completion using Chat Completions API."""
        response = await self.client.chat.completions.create(
            model=model or self.default_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens
        )
        return response.choices[0].message.content

    async def generate_embedding(
        self,
        text: str,
        model: str | None = None
    ) -> list[float]:
        """Generate text embedding."""
        # Truncate text to 8192 tokens (OpenAI limit)
        text = text[:32000]  # Rough approximation (4 chars = 1 token)

        response = await self.client.embeddings.create(
            model=model or self.embedding_model,
            input=text
        )
        return response.data[0].embedding

    async def generate_structured_output(
        self,
        prompt: str,
        model: str | None = None,
        response_schema: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Generate structured JSON output using function calling."""
        response = await self.client.chat.completions.create(
            model=model or self.default_model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        content = response.choices[0].message.content
        return json.loads(content)
```

## Vertex AI Provider Implementation

```python
# app/ai/providers/vertex_ai_provider.py

from google.cloud import aiplatform
from vertexai.language_models import TextEmbeddingModel, TextGenerationModel
from app.ai.llm_provider import BaseLLMProvider
from app.core.config import settings

class VertexAIProvider(BaseLLMProvider):
    """Google Vertex AI provider."""

    def __init__(self):
        # Initialize Vertex AI
        aiplatform.init(
            project=settings.gcp_project_id,
            location=settings.gcp_region  # "me-central1" for Dammam
        )
        self.default_model = "gemini-2.0-flash-exp"
        self.embedding_model = "text-embedding-004"

    async def generate_completion(
        self,
        prompt: str,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 500
    ) -> str:
        """Generate text completion using Gemini."""
        model_instance = TextGenerationModel.from_pretrained(
            model or self.default_model
        )
        response = await model_instance.predict_async(
            prompt,
            temperature=temperature,
            max_output_tokens=max_tokens
        )
        return response.text

    async def generate_embedding(
        self,
        text: str,
        model: str | None = None
    ) -> list[float]:
        """Generate text embedding."""
        model_instance = TextEmbeddingModel.from_pretrained(
            model or self.embedding_model
        )
        embeddings = await model_instance.get_embeddings_async([text])
        return embeddings[0].values

    async def generate_structured_output(
        self,
        prompt: str,
        model: str | None = None,
        response_schema: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Generate structured JSON output."""
        # Add JSON instruction to prompt
        structured_prompt = f"{prompt}\n\nRespond with valid JSON only."
        response = await self.generate_completion(structured_prompt, model)
        return json.loads(response)
```

## Enrichment Pipeline

### 1. Text Classification

```python
# app/ai/classification.py

from app.ai.llm_provider import LLMFactory, LLMProvider
from app.core.config import settings

class FeedbackClassifier:
    """Classify feedback into categories."""

    CATEGORIES = [
        "bug_report",
        "feature_request",
        "complaint",
        "praise",
        "question",
        "other"
    ]

    def __init__(self):
        self.provider = LLMFactory.create(settings.llm_provider)

    async def classify(self, feedback_text: str) -> dict[str, Any]:
        """Classify feedback text."""
        prompt = f"""Analyze this customer feedback and classify it.

Feedback: "{feedback_text}"

Classify into one of these categories:
- bug_report: Technical issue or malfunction
- feature_request: Request for new functionality
- complaint: Expression of dissatisfaction
- praise: Positive feedback or appreciation
- question: Question or request for information
- other: Doesn't fit other categories

Also rate the urgency (low/medium/high) and identify affected product area.

Respond with JSON:
{{
  "category": "bug_report",
  "urgency": "high",
  "product_area": "authentication",
  "confidence": 0.95,
  "reasoning": "Brief explanation"
}}"""

        response = await self.provider.generate_structured_output(
            prompt=prompt,
            model=settings.classification_model
        )
        return response

# Usage in service
async def enrich_feedback_with_classification(
    feedback_id: int,
    db: AsyncSession
):
    """Enrich feedback with AI classification."""
    feedback = await feedback_repo.get_by_id(db, feedback_id)

    classifier = FeedbackClassifier()
    classification = await classifier.classify(feedback.content)

    # Store classification
    feedback.category = classification["category"]
    feedback.urgency = classification["urgency"]
    feedback.product_area = classification["product_area"]
    feedback.classification_metadata = classification

    await db.commit()
```

### 2. Sentiment Analysis

```python
# app/ai/sentiment.py

class SentimentAnalyzer:
    """Analyze sentiment of feedback."""

    def __init__(self):
        self.provider = LLMFactory.create(settings.llm_provider)

    async def analyze(self, feedback_text: str) -> dict[str, Any]:
        """Analyze sentiment."""
        prompt = f"""Analyze the sentiment of this customer feedback.

Feedback: "{feedback_text}"

Provide:
1. Overall sentiment (positive/negative/neutral/mixed)
2. Sentiment score (-1.0 to 1.0)
3. Key emotions detected
4. Tone (professional, frustrated, excited, etc.)

Respond with JSON:
{{
  "sentiment": "negative",
  "score": -0.6,
  "emotions": ["frustration", "disappointment"],
  "tone": "frustrated",
  "confidence": 0.88
}}"""

        return await self.provider.generate_structured_output(prompt)
```

### 3. Embedding Generation

```python
# app/ai/embeddings.py

import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession
from app.ai.llm_provider import LLMFactory

class EmbeddingService:
    """Generate and store embeddings."""

    def __init__(self):
        self.provider = LLMFactory.create(settings.llm_provider)

    async def generate_for_feedback(
        self,
        feedback_id: int,
        db: AsyncSession
    ):
        """Generate embedding for feedback."""
        feedback = await feedback_repo.get_by_id(db, feedback_id)

        # Combine title and content for richer embedding
        text = f"{feedback.title}\n\n{feedback.content}"

        # Generate embedding
        embedding_vector = await self.provider.generate_embedding(text)

        # Store in database (use pgvector extension)
        feedback.embedding = embedding_vector
        await db.commit()

    async def batch_generate(
        self,
        feedback_ids: list[int],
        db: AsyncSession,
        batch_size: int = 50
    ):
        """Generate embeddings in batches for cost efficiency."""
        for i in range(0, len(feedback_ids), batch_size):
            batch = feedback_ids[i:i + batch_size]
            for feedback_id in batch:
                await self.generate_for_feedback(feedback_id, db)
            await asyncio.sleep(1)  # Rate limiting

    async def find_similar(
        self,
        query_embedding: list[float],
        db: AsyncSession,
        limit: int = 10,
        threshold: float = 0.7
    ) -> list[Feedback]:
        """Find similar feedback using cosine similarity."""
        # Use pgvector's cosine distance operator
        from sqlalchemy import text

        result = await db.execute(
            text("""
                SELECT id, title, content,
                       1 - (embedding <=> :query_embedding) AS similarity
                FROM feedback
                WHERE 1 - (embedding <=> :query_embedding) > :threshold
                ORDER BY embedding <=> :query_embedding
                LIMIT :limit
            """),
            {
                "query_embedding": query_embedding,
                "threshold": threshold,
                "limit": limit
            }
        )
        return result.fetchall()
```

### 4. Theme Generation

```python
# app/ai/theme_generator.py

class ThemeGenerator:
    """Generate theme names and descriptions from feedback clusters."""

    def __init__(self):
        self.provider = LLMFactory.create(settings.llm_provider)

    async def generate_theme(
        self,
        feedback_samples: list[dict[str, str]],
        cluster_size: int
    ) -> dict[str, Any]:
        """Generate theme from feedback cluster."""
        # Take top 5-10 representative samples
        samples_text = "\n\n".join([
            f"- {f['title']}: {f['content'][:200]}"
            for f in feedback_samples[:10]
        ])

        prompt = f"""Analyze these {cluster_size} customer feedback items that were clustered together.

Sample feedback:
{samples_text}

Generate a theme that captures the common issue or request:
1. Theme name (2-6 words, clear and specific)
2. Description (1-2 sentences explaining the theme)
3. Category (bug, feature, usability, performance, etc.)
4. Recommended action (what should the team do?)

Respond with JSON:
{{
  "name": "Mobile App Crashes on Login",
  "description": "Users experiencing crashes when...",
  "category": "bug",
  "recommended_action": "Investigate authentication flow...",
  "confidence": 0.92
}}"""

        return await self.provider.generate_structured_output(prompt)
```

## Cost Optimization

### 1. Caching Strategy

```python
# app/ai/cache.py

from functools import wraps
import hashlib
import json
from redis import Redis

redis_client = Redis.from_url(settings.redis_url)

def cache_llm_response(ttl: int = 3600):
    """Cache LLM responses to reduce API costs."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Create cache key from function args
            key_data = f"{func.__name__}:{json.dumps(args)}:{json.dumps(kwargs)}"
            cache_key = f"llm:{hashlib.md5(key_data.encode()).hexdigest()}"

            # Check cache
            cached = redis_client.get(cache_key)
            if cached:
                return json.loads(cached)

            # Generate response
            result = await func(*args, **kwargs)

            # Store in cache
            redis_client.setex(cache_key, ttl, json.dumps(result))

            return result
        return wrapper
    return decorator

# Usage
class FeedbackClassifier:
    @cache_llm_response(ttl=86400)  # Cache for 24 hours
    async def classify(self, feedback_text: str):
        # Classification logic...
        pass
```

### 2. Batch Processing

```python
# Process feedback in batches during off-peak hours
async def batch_enrich_feedback(
    start_date: datetime,
    end_date: datetime,
    db: AsyncSession
):
    """Batch enrich feedback created in date range."""
    feedback_items = await feedback_repo.get_by_date_range(
        db, start_date, end_date
    )

    classifier = FeedbackClassifier()
    sentiment_analyzer = SentimentAnalyzer()
    embedding_service = EmbeddingService()

    for feedback in feedback_items:
        # Skip if already enriched
        if feedback.classification_metadata:
            continue

        # Classify
        classification = await classifier.classify(feedback.content)
        feedback.classification_metadata = classification

        # Sentiment
        sentiment = await sentiment_analyzer.analyze(feedback.content)
        feedback.sentiment_metadata = sentiment

        # Embedding
        await embedding_service.generate_for_feedback(feedback.id, db)

        await db.commit()
```

### 3. Model Selection by Task

```python
# app/core/config.py

class Settings(BaseSettings):
    # Use cheaper models for simple tasks
    classification_model: str = "gpt-4o-mini"  # Fast, cheap for classification
    embedding_model: str = "text-embedding-3-small"  # 512 dimensions, cheaper
    theme_generation_model: str = "gpt-4o"  # More capable for creative tasks
    sentiment_model: str = "gpt-4o-mini"  # Simple task
```

## Error Handling and Retries

```python
from tenacity import retry, stop_after_attempt, wait_exponential
from openai import RateLimitError, APIError

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=retry_if_exception_type((RateLimitError, APIError))
)
async def call_llm_with_retry(provider: BaseLLMProvider, prompt: str):
    """Call LLM with automatic retry on transient errors."""
    try:
        return await provider.generate_completion(prompt)
    except RateLimitError as e:
        logger.warning(f"Rate limit hit, retrying: {e}")
        raise
    except Exception as e:
        logger.error(f"LLM call failed: {e}")
        raise
```

## Multilingual Support (Arabic + English)

```python
class MultilingualEmbeddingService:
    """Generate embeddings for multilingual text."""

    async def generate(self, text: str, language: str = "auto") -> list[float]:
        """Generate embedding with language detection."""
        # For OpenAI: text-embedding-3-* models support 100+ languages
        # For Vertex AI: text-embedding-004 supports multilingual

        # Optional: Detect language
        if language == "auto":
            language = self._detect_language(text)

        # Generate embedding (models handle multilingual automatically)
        embedding = await self.provider.generate_embedding(text)

        return embedding

    def _detect_language(self, text: str) -> str:
        """Detect text language."""
        import langdetect
        try:
            return langdetect.detect(text)
        except:
            return "en"
```

## Testing AI Pipeline

```python
# tests/ai/test_classification.py

import pytest
from app.ai.classification import FeedbackClassifier

@pytest.mark.asyncio
async def test_classify_bug_report():
    """Test classifying bug report."""
    classifier = FeedbackClassifier()

    feedback = "The app crashes every time I try to log in on iOS 17."

    result = await classifier.classify(feedback)

    assert result["category"] == "bug_report"
    assert result["urgency"] in ["medium", "high"]
    assert result["confidence"] > 0.7

@pytest.mark.asyncio
async def test_classify_feature_request():
    """Test classifying feature request."""
    classifier = FeedbackClassifier()

    feedback = "It would be great to have dark mode support."

    result = await classifier.classify(feedback)

    assert result["category"] == "feature_request"
    assert "theme" in result["product_area"].lower() or "ui" in result["product_area"].lower()
```

## Deployment Checklist

- [ ] Environment variables set (OPENAI_API_KEY or GCP credentials)
- [ ] Redis cache configured for LLM response caching
- [ ] pgvector extension installed for embedding storage
- [ ] Background job scheduled for batch enrichment
- [ ] Rate limiting configured
- [ ] Error monitoring (Sentry) enabled
- [ ] Cost alerts configured (OpenAI/GCP billing)

## Success Criteria

AI pipeline is production-ready when:
- [ ] Classification accuracy > 85% on validation set
- [ ] Embeddings enable meaningful similarity search
- [ ] Sentiment analysis matches human judgment
- [ ] Theme generation produces actionable insights
- [ ] API costs within budget ($X/month)
- [ ] 99% of requests succeed (with retries)
- [ ] Latency < 2 seconds per enrichment

## Related Skills

- `jisrvoc-backend-context` - Backend architecture
- `connector-development` - Fetch feedback to enrich
- `mock-to-real-data` - Switch to real enrichment pipeline

## References

- **OpenAI API**: https://platform.openai.com/docs/
- **Vertex AI**: https://cloud.google.com/vertex-ai/docs
- **pgvector**: https://github.com/pgvector/pgvector
- **Multilingual Embeddings**: https://platform.openai.com/docs/guides/embeddings
