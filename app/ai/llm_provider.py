"""LLM provider abstraction layer for OpenAI and Vertex AI."""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any


class LLMProvider(str, Enum):
    """Supported LLM providers."""
    OPENAI = "openai"
    VERTEX_AI = "vertex_ai"


class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    async def generate_completion(
        self,
        prompt: str,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 500,
    ) -> str:
        """
        Generate text completion from prompt.

        Args:
            prompt: The input prompt
            model: Model identifier (provider-specific)
            temperature: Sampling temperature (0-2)
            max_tokens: Maximum tokens to generate

        Returns:
            Generated text completion

        Raises:
            LLMProviderError: If generation fails
        """
        pass

    @abstractmethod
    async def generate_embedding(
        self,
        text: str,
        model: str | None = None,
    ) -> list[float]:
        """
        Generate embedding vector for text.

        Args:
            text: Input text to embed
            model: Embedding model identifier

        Returns:
            Embedding vector (dimensions depend on model)

        Raises:
            LLMProviderError: If embedding generation fails
        """
        pass

    @abstractmethod
    async def generate_structured_output(
        self,
        prompt: str,
        model: str | None = None,
        response_schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Generate structured JSON output.

        Args:
            prompt: Input prompt
            model: Model identifier
            response_schema: Optional JSON schema for validation

        Returns:
            Parsed JSON dictionary

        Raises:
            LLMProviderError: If generation or parsing fails
        """
        pass


class LLMProviderError(Exception):
    """Base exception for LLM provider errors."""
    pass


class LLMRateLimitError(LLMProviderError):
    """Rate limit exceeded."""
    pass


class LLMAuthenticationError(LLMProviderError):
    """Authentication failed."""
    pass


def create_llm_provider(provider_type: LLMProvider) -> BaseLLMProvider:
    """
    Factory function to create LLM provider instances.

    Args:
        provider_type: The provider to instantiate

    Returns:
        Configured LLM provider instance

    Raises:
        ValueError: If provider type is unknown
    """
    if provider_type == LLMProvider.OPENAI:
        from app.ai.providers.openai_provider import OpenAIProvider
        return OpenAIProvider()
    elif provider_type == LLMProvider.VERTEX_AI:
        from app.ai.providers.vertex_ai_provider import VertexAIProvider
        return VertexAIProvider()
    else:
        raise ValueError(f"Unknown LLM provider: {provider_type}")
