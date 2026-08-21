"""Stage 5: AIProvider factory selection."""
import pytest

from app.ai.factory import get_ai_provider
from app.ai.mock_provider import MockAIProvider
from app.ai.openai_compatible_provider import OpenAICompatibleProvider
from app.core.config import Settings


def test_factory_returns_mock_provider_by_default():
    settings = Settings(AI_PROVIDER="mock")
    provider = get_ai_provider(settings)
    assert isinstance(provider, MockAIProvider)


def test_factory_returns_openai_compatible_provider():
    settings = Settings(
        AI_PROVIDER="openai_compatible",
        AI_BASE_URL="https://api.openai.com/v1",
        AI_API_KEY="sk-test",
        AI_MODEL="gpt-4o-mini",
    )
    provider = get_ai_provider(settings)
    assert isinstance(provider, OpenAICompatibleProvider)
    assert provider.model == "gpt-4o-mini"


def test_factory_raises_on_unknown_provider():
    settings = Settings(AI_PROVIDER="something_else")
    with pytest.raises(ValueError):
        get_ai_provider(settings)
