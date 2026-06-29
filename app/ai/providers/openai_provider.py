"""OpenAI provider implementation."""

import json
from typing import Any

from openai import AsyncOpenAI

from app.ai.llm_provider import (
    BaseLLMProvider,
    LLMProviderError,
    LLMRateLimitError,
    LLMAuthenticationError,
)
from app.core.config import settings


class OpenAIProvider(BaseLLMProvider):
    """OpenAI API provider implementation."""

    def __init__(self):
        """Initialize OpenAI client."""
        if not settings.openai_api_key:
            raise LLMAuthenticationError("OPENAI_API_KEY not configured")

        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.default_model = "gpt-4o-mini"
        self.embedding_model = "text-embedding-3-small"

    async def generate_completion(
        self,
        prompt: str,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 500,
    ) -> str:
        """Generate text completion using OpenAI Chat Completions API."""
        try:
            response = await self.client.chat.completions.create(
                model=model or self.default_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            error_msg = str(e)
            if "rate_limit" in error_msg.lower():
                raise LLMRateLimitError(f"OpenAI rate limit exceeded: {error_msg}")
            elif "authentication" in error_msg.lower() or "api_key" in error_msg.lower():
                raise LLMAuthenticationError(f"OpenAI authentication failed: {error_msg}")
            else:
                raise LLMProviderError(f"OpenAI completion failed: {error_msg}")

    async def generate_embedding(
        self,
        text: str,
        model: str | None = None,
    ) -> list[float]:
        """Generate text embedding using OpenAI Embeddings API."""
        try:
            # Truncate text to reasonable length (OpenAI has 8192 token limit)
            # Rough approximation: 4 characters ≈ 1 token
            max_chars = 32000
            text = text[:max_chars]

            response = await self.client.embeddings.create(
                model=model or self.embedding_model,
                input=text,
            )
            return response.data[0].embedding
        except Exception as e:
            error_msg = str(e)
            if "rate_limit" in error_msg.lower():
                raise LLMRateLimitError(f"OpenAI rate limit exceeded: {error_msg}")
            else:
                raise LLMProviderError(f"OpenAI embedding failed: {error_msg}")

    async def generate_structured_output(
        self,
        prompt: str,
        model: str | None = None,
        response_schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Generate structured JSON output using OpenAI."""
        try:
            response = await self.client.chat.completions.create(
                model=model or self.default_model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
            )

            content = response.choices[0].message.content or "{}"
            return json.loads(content)
        except json.JSONDecodeError as e:
            raise LLMProviderError(f"Failed to parse OpenAI JSON response: {e}")
        except Exception as e:
            error_msg = str(e)
            if "rate_limit" in error_msg.lower():
                raise LLMRateLimitError(f"OpenAI rate limit exceeded: {error_msg}")
            else:
                raise LLMProviderError(f"OpenAI structured output failed: {error_msg}")
