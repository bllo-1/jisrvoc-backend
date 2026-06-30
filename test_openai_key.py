"""
Quick test script to verify OpenAI API key is working.
Run: python test_openai_key.py
"""
import asyncio
import sys
from app.core.config import settings
from app.ai.providers.openai_provider import OpenAIProvider, LLMAuthenticationError


async def test_openai_connection():
    """Test that OpenAI API key is configured and working."""
    print("=" * 60)
    print("Testing OpenAI API Key Configuration")
    print("=" * 60)

    # Check if key is loaded
    if not settings.openai_api_key:
        print("❌ FAIL: OPENAI_API_KEY not found in environment")
        print("   Make sure .env file has OPENAI_API_KEY set")
        return False

    # Mask the key for security
    key_preview = settings.openai_api_key[:10] + "..." + settings.openai_api_key[-4:]
    print(f"✓ API key loaded: {key_preview}")

    # Try to initialize provider
    try:
        provider = OpenAIProvider()
        print(f"✓ Provider initialized")
        print(f"  Default model: {provider.default_model}")
        print(f"  Embedding model: {provider.embedding_model}")
    except LLMAuthenticationError as e:
        print(f"❌ FAIL: {e}")
        return False

    # Test a simple completion
    print("\n" + "-" * 60)
    print("Testing API call with simple prompt...")
    print("-" * 60)

    try:
        result = await provider.generate_completion(
            prompt="Say 'Hello from OpenAI!' and nothing else.",
            max_tokens=20,
            temperature=0
        )
        print(f"✓ API call successful!")
        print(f"  Response: {result}")

    except Exception as e:
        print(f"❌ FAIL: API call failed")
        print(f"   Error: {e}")
        print("\n💡 Common issues:")
        print("   - Invalid or expired API key")
        print("   - Network connectivity issues")
        print("   - OpenAI service outage")
        print("   - Wrong API key format (make sure it starts with 'sk-')")
        return False

    print("\n" + "=" * 60)
    print("✅ All tests passed! OpenAI integration is working.")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success = asyncio.run(test_openai_connection())
    sys.exit(0 if success else 1)
