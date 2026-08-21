"""Stage 5: MockAIProvider deterministic heuristics."""
import pytest

from app.ai.mock_provider import MockAIProvider


@pytest.fixture
def provider() -> MockAIProvider:
    return MockAIProvider()


@pytest.mark.asyncio
async def test_direct_intent_message_is_lead(provider):
    result = await provider.analyze_lead("Всем привет! Нужен сайт для стоматологии, бюджет 100 тыс руб, срочно", system_prompt="test")
    assert result.is_lead is True
    assert result.intent == "looking_for_contractor"
    assert result.urgency == "high"
    assert result.budget.mentioned is True


@pytest.mark.asyncio
async def test_job_seeker_message_is_not_lead(provider):
    result = await provider.analyze_lead("Ищу работу frontend разработчиком, готов работать удалённо, вот моё резюме", system_prompt="test")
    assert result.is_lead is False
    assert "job-seeking" in result.negative_signals[0]


@pytest.mark.asyncio
async def test_self_advertising_message_is_not_lead(provider):
    result = await provider.analyze_lead("Разрабатываю сайты на заказ, предлагаю услуги веб-дизайна, пишите в лс", system_prompt="test")
    assert result.is_lead is False


@pytest.mark.asyncio
async def test_unrelated_message_is_not_lead(provider):
    result = await provider.analyze_lead("Кто-нибудь знает хороший рецепт борща?", system_prompt="test")
    assert result.is_lead is False
    assert result.lead_probability < 0.2


@pytest.mark.asyncio
async def test_result_always_validates_against_schema(provider):
    # LeadAnalysis() being returned at all means it already passed validation
    # at construction time (Pydantic validates on init) — this is a smoke check.
    for text in ["нужен сайт", "ищу работу", "предлагаю услуги", "случайный текст"]:
        result = await provider.analyze_lead(text, system_prompt="test")
        assert 0.0 <= result.lead_probability <= 1.0
        assert 0.0 <= result.confidence <= 1.0
