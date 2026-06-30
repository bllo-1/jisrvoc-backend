"""Tests for classification pipeline."""

import pytest
from unittest.mock import AsyncMock

from app.services.classification_pipeline import ClassificationPipeline, ClassificationResult
from app.ai.llm_provider import BaseLLMProvider


@pytest.fixture
def mock_llm_provider():
    """Mock LLM provider for testing."""
    provider = AsyncMock(spec=BaseLLMProvider)
    return provider


@pytest.fixture
def classification_pipeline(mock_llm_provider):
    """Classification pipeline with mock provider."""
    return ClassificationPipeline(llm_provider=mock_llm_provider)


@pytest.mark.asyncio
async def test_classify_feedback_bug_report(mock_llm_provider, classification_pipeline):
    """Test classifying a bug report."""
    # Mock LLM response
    mock_llm_provider.generate_structured_output.return_value = {
        "sentiment": "negative",
        "sentiment_score": -0.6,
        "category": "bug",
        "category_confidence": 0.95,
        "product_area": "mobile",
        "topics": ["crash", "login", "mobile"],
        "summary": "User reports app crashes when logging in on mobile devices."
    }

    # Call pipeline
    result = await classification_pipeline.classify_feedback(
        title="App crashes on login",
        content="The mobile app crashes every time I try to log in. This is very frustrating and blocking my work.",
        source="hubspot",
    )

    # Verify result
    assert isinstance(result, ClassificationResult)
    assert result.sentiment == "negative"
    assert result.sentiment_score == -0.6
    assert result.category == "bug"
    assert result.category_confidence == 0.95
    assert result.product_area == "mobile"
    assert "crash" in result.topics
    assert "login" in result.topics
    assert len(result.summary) > 0

    # Verify LLM was called correctly
    mock_llm_provider.generate_structured_output.assert_called_once()
    call_args = mock_llm_provider.generate_structured_output.call_args
    prompt = call_args.kwargs["prompt"]
    assert "App crashes on login" in prompt
    assert "mobile app crashes" in prompt


@pytest.mark.asyncio
async def test_classify_feedback_feature_request(mock_llm_provider, classification_pipeline):
    """Test classifying a feature request."""
    mock_llm_provider.generate_structured_output.return_value = {
        "sentiment": "neutral",
        "sentiment_score": 0.2,
        "category": "feature_request",
        "category_confidence": 0.9,
        "product_area": "api",
        "topics": ["bulk import", "csv", "api"],
        "summary": "User requests ability to bulk import data via CSV or API."
    }

    result = await classification_pipeline.classify_feedback(
        title="Need bulk import feature",
        content="Would love to see a way to import data in bulk, either via CSV upload or API.",
        source="zendesk",
    )

    assert result.sentiment == "neutral"
    assert result.category == "feature_request"
    assert result.product_area == "api"
    assert "bulk import" in result.topics


@pytest.mark.asyncio
async def test_classify_feedback_praise(mock_llm_provider, classification_pipeline):
    """Test classifying positive feedback."""
    mock_llm_provider.generate_structured_output.return_value = {
        "sentiment": "positive",
        "sentiment_score": 0.9,
        "category": "praise",
        "category_confidence": 0.98,
        "product_area": "ui",
        "topics": ["design", "ease of use", "onboarding"],
        "summary": "User loves the new onboarding flow and finds the UI very intuitive."
    }

    result = await classification_pipeline.classify_feedback(
        title="Love the new onboarding!",
        content="The new onboarding flow is amazing! Very intuitive and easy to use. Great work on the UI redesign.",
    )

    assert result.sentiment == "positive"
    assert result.sentiment_score > 0.5
    assert result.category == "praise"


@pytest.mark.asyncio
async def test_classify_feedback_invalid_schema(mock_llm_provider, classification_pipeline):
    """Test handling of invalid classification schema."""
    # Missing required field 'sentiment'
    mock_llm_provider.generate_structured_output.return_value = {
        "category": "bug",
        "summary": "Test",
    }

    with pytest.raises(Exception):  # Pydantic validation error
        await classification_pipeline.classify_feedback(
            title="Test",
            content="Test content",
        )
