"""Classification Pipeline - AI-powered feedback classification service.

Uses LLM provider abstraction to classify feedback into:
- Sentiment (positive/negative/neutral/mixed) with score
- Category (bug/feature_request/question/complaint/praise)
- Product area (billing/auth/api/ui/etc)
- Topics/themes (list of keywords)
- Summary (1-2 sentence summary)
"""

from typing import Any
from pydantic import BaseModel, Field

from app.ai.llm_provider import BaseLLMProvider


class ClassificationResult(BaseModel):
    """Structured result from classification pipeline."""
    sentiment: str = Field(..., description="positive, negative, neutral, or mixed")
    sentiment_score: float = Field(..., ge=-1.0, le=1.0, description="Score from -1.0 (negative) to 1.0 (positive)")
    category: str = Field(..., description="bug, feature_request, question, complaint, or praise")
    category_confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score 0.0-1.0")
    product_area: str | None = Field(None, description="Product area if detected: billing, auth, api, ui, etc")
    topics: list[str] = Field(default_factory=list, description="List of key topics/themes")
    summary: str = Field(..., max_length=500, description="1-2 sentence summary")


class ClassificationPipeline:
    """AI-powered classification pipeline for customer feedback."""

    def __init__(self, llm_provider: BaseLLMProvider):
        """Initialize pipeline with LLM provider.

        Args:
            llm_provider: LLM provider instance (OpenAI or Vertex AI)
        """
        self.llm_provider = llm_provider

    async def classify_feedback(
        self,
        title: str,
        content: str,
        source: str | None = None,
        model: str | None = None,
    ) -> ClassificationResult:
        """Classify a feedback item using AI.

        Args:
            title: Feedback title
            content: Feedback content/body
            source: Source system (hubspot, zendesk, etc) for context
            model: Optional model override

        Returns:
            ClassificationResult with sentiment, category, topics, and summary

        Raises:
            ValueError: If LLM response is invalid
            LLMProviderError: If LLM API call fails
        """
        # Build the classification prompt
        prompt = self._build_prompt(title, content, source)

        # Call LLM with structured output
        classification_data = await self.llm_provider.generate_structured_output(
            prompt=prompt,
            model=model,
        )

        # Validate and create result
        result = ClassificationResult(**classification_data)

        return result

    def _build_prompt(self, title: str, content: str, source: str | None) -> str:
        """Build the classification prompt."""
        source_context = f"\nSource: {source}" if source else ""

        return f"""You are an expert at analyzing customer feedback for a B2B SaaS product.

Your task is to classify this feedback into structured categories to help the product team understand customer sentiment and prioritize work.

Feedback Title: {title}

Feedback Content:
{content}{source_context}

Classify this feedback and respond with JSON matching this schema:
{{
  "sentiment": "positive" | "negative" | "neutral" | "mixed",
  "sentiment_score": <float from -1.0 to 1.0>,
  "category": "bug" | "feature_request" | "question" | "complaint" | "praise",
  "category_confidence": <float from 0.0 to 1.0>,
  "product_area": <string or null>,
  "topics": [<list of 2-5 key topics/themes>],
  "summary": "<1-2 sentence summary>"
}}

Guidelines:
- sentiment_score: -1.0 = very negative, 0.0 = neutral, 1.0 = very positive
- category_confidence: How confident you are in the category classification
- product_area: Only set if clearly mentioned (e.g., "billing", "auth", "api", "ui", "mobile", "integration")
- topics: 2-5 key themes/topics from the feedback (e.g., ["performance", "mobile", "integration"])
- summary: Concise 1-2 sentence summary of the feedback"""
