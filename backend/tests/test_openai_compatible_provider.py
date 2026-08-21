"""Stage 5: OpenAICompatibleProvider retry/repair loop on invalid JSON.

_call_completion (the actual HTTP call) is monkeypatched so these tests
never hit the network — they only exercise the parse/validate/retry logic.
"""
from unittest.mock import AsyncMock

import pytest

from app.ai.exceptions import AIResponseValidationError
from app.ai.openai_compatible_provider import OpenAICompatibleProvider


def make_provider(max_retries: int = 2) -> OpenAICompatibleProvider:
    return OpenAICompatibleProvider(
        base_url="https://fake-ai.example.com/v1",
        api_key="fake-key",
        model="fake-model",
        max_retries=max_retries,
    )


@pytest.mark.asyncio
async def test_valid_first_response_succeeds_without_retry():
    provider = make_provider()
    provider._call_completion = AsyncMock(
        return_value='{"is_lead": true, "lead_probability": 0.8}'
    )
    result = await provider.analyze_lead("нужен сайт", system_prompt="test system prompt")
    assert result.is_lead is True
    provider._call_completion.assert_awaited_once()


@pytest.mark.asyncio
async def test_json_wrapped_in_markdown_fence_is_extracted():
    provider = make_provider()
    provider._call_completion = AsyncMock(
        return_value='```json\n{"is_lead": false, "lead_probability": 0.1}\n```'
    )
    result = await provider.analyze_lead("случайный текст", system_prompt="test system prompt")
    assert result.is_lead is False


@pytest.mark.asyncio
async def test_invalid_json_then_valid_json_succeeds_on_retry():
    provider = make_provider(max_retries=2)
    provider._call_completion = AsyncMock(
        side_effect=[
            "this is not json at all",
            '{"is_lead": true, "lead_probability": 0.6}',
        ]
    )
    result = await provider.analyze_lead("нужен сайт", system_prompt="test system prompt")
    assert result.is_lead is True
    assert provider._call_completion.await_count == 2


@pytest.mark.asyncio
async def test_persistently_invalid_json_raises_after_max_retries():
    provider = make_provider(max_retries=1)  # 1 retry => 2 total attempts
    provider._call_completion = AsyncMock(return_value="still not json")
    with pytest.raises(AIResponseValidationError):
        await provider.analyze_lead("нужен сайт", system_prompt="test system prompt")
    assert provider._call_completion.await_count == 2


@pytest.mark.asyncio
async def test_schema_violation_triggers_retry_not_crash():
    provider = make_provider(max_retries=1)
    provider._call_completion = AsyncMock(
        side_effect=[
            '{"is_lead": true, "lead_probability": 5.0}',  # out of [0,1] range
            '{"is_lead": true, "lead_probability": 0.5}',
        ]
    )
    result = await provider.analyze_lead("нужен сайт", system_prompt="test system prompt")
    assert result.lead_probability == 0.5


def test_missing_base_url_raises_at_construction():
    with pytest.raises(ValueError):
        OpenAICompatibleProvider(base_url="", api_key="x", model="m")
