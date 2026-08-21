"""Factory: picks the concrete AIProvider based on AI_PROVIDER env var.

Adding Claude/Gemini/local-model providers later means adding one more
`elif` branch here (and a new provider class) — nothing else in the app
needs to change since everything depends on the AIProvider ABC.
"""
from app.ai.base import AIProvider
from app.ai.mock_provider import MockAIProvider
from app.ai.openai_compatible_provider import OpenAICompatibleProvider
from app.core.config import Settings


def get_ai_provider(settings: Settings) -> AIProvider:
    provider = settings.AI_PROVIDER.lower()

    if provider == "mock":
        return MockAIProvider()

    if provider == "openai_compatible":
        return OpenAICompatibleProvider(
            base_url=settings.AI_BASE_URL or "",
            api_key=settings.AI_API_KEY,
            model=settings.AI_MODEL,
            timeout_seconds=settings.AI_REQUEST_TIMEOUT_SECONDS,
            max_retries=settings.AI_MAX_RETRIES,
        )

    raise ValueError(
        f"Unknown AI_PROVIDER={settings.AI_PROVIDER!r}. Supported: 'mock', 'openai_compatible'."
    )
