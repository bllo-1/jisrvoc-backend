"""Vertex AI provider implementation (Phase 4)."""

from typing import Any

from app.ai.llm_provider import BaseLLMProvider, LLMProviderError


class VertexAIProvider(BaseLLMProvider):
    """
    Vertex AI provider (stub for Phase 4 implementation).

    Will be fully implemented when migrating to GCP Dammam.
    """

    def __init__(self):
        """Initialize Vertex AI provider."""
        # Phase 4: Initialize Vertex AI client
        # from google.cloud import aiplatform
        # aiplatform.init(project=settings.gcp_project_id, location=settings.gcp_region)
        raise LLMProviderError(
            "Vertex AI provider not yet implemented. "
            "Use OpenAI provider for testing phase. "
            "Full implementation in Phase 4."
        )

    async def generate_completion(
        self,
        prompt: str,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 500,
    ) -> str:
        """Generate completion using Gemini (Phase 4)."""
        raise NotImplementedError("Vertex AI implementation pending Phase 4")

    async def generate_embedding(
        self,
        text: str,
        model: str | None = None,
    ) -> list[float]:
        """Generate embedding using Vertex AI (Phase 4)."""
        raise NotImplementedError("Vertex AI implementation pending Phase 4")

    async def generate_structured_output(
        self,
        prompt: str,
        model: str | None = None,
        response_schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Generate structured output using Gemini (Phase 4)."""
        raise NotImplementedError("Vertex AI implementation pending Phase 4")
