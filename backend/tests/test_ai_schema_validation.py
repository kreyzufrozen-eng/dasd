"""Stage 5: LeadAnalysis Pydantic schema validation."""
import pytest
from pydantic import ValidationError

from app.ai.json_utils import extract_json_object
from app.schemas.ai_analysis import LeadAnalysis


def test_valid_full_payload_parses():
    payload = {
        "is_lead": True,
        "lead_probability": 0.94,
        "lead_type": "website_development",
        "services": ["web_design", "website_development"],
        "project_description": "Нужен лендинг для стоматологии",
        "business_niche": "dentistry",
        "budget": {"mentioned": True, "min": 50000, "max": 100000, "currency": "RUB"},
        "urgency": "high",
        "project_complexity": "medium",
        "intent": "looking_for_contractor",
        "estimated_value": "high",
        "summary": "Клиника ищет разработчика лендинга.",
        "reasoning_short": "Прямой запрос с бюджетом.",
        "positive_signals": ["direct request", "budget mentioned"],
        "negative_signals": [],
        "confidence": 0.9,
    }
    analysis = LeadAnalysis.model_validate(payload)
    assert analysis.is_lead is True
    assert analysis.budget.min == 50000
    assert analysis.services == ["web_design", "website_development"]


def test_minimal_payload_uses_defaults():
    analysis = LeadAnalysis.model_validate({"is_lead": False, "lead_probability": 0.1})
    assert analysis.services == []
    assert analysis.budget.mentioned is False
    assert analysis.urgency == "low"
    assert analysis.intent == "unrelated"


@pytest.mark.parametrize("field,value", [("urgency", "extreme"), ("project_complexity", "huge"), ("estimated_value", "massive")])
def test_invalid_level_enum_rejected(field, value):
    payload = {"is_lead": True, "lead_probability": 0.5, field: value}
    with pytest.raises(ValidationError):
        LeadAnalysis.model_validate(payload)


def test_invalid_intent_rejected():
    payload = {"is_lead": True, "lead_probability": 0.5, "intent": "wants_a_pony"}
    with pytest.raises(ValidationError):
        LeadAnalysis.model_validate(payload)


def test_probability_out_of_range_rejected():
    with pytest.raises(ValidationError):
        LeadAnalysis.model_validate({"is_lead": True, "lead_probability": 1.5})
    with pytest.raises(ValidationError):
        LeadAnalysis.model_validate({"is_lead": True, "lead_probability": -0.1})


def test_missing_required_field_rejected():
    with pytest.raises(ValidationError):
        LeadAnalysis.model_validate({"lead_probability": 0.5})  # missing is_lead


# --- JSON extraction from raw LLM output ---

def test_extract_json_object_plain():
    raw = '{"is_lead": true, "lead_probability": 0.5}'
    assert extract_json_object(raw) == raw


def test_extract_json_object_from_markdown_fence():
    raw = '```json\n{"is_lead": true, "lead_probability": 0.5}\n```'
    result = extract_json_object(raw)
    assert result == '{"is_lead": true, "lead_probability": 0.5}'


def test_extract_json_object_with_surrounding_text():
    raw = 'Вот результат:\n{"is_lead": false, "lead_probability": 0.1}\nНадеюсь, помогло.'
    result = extract_json_object(raw)
    assert result == '{"is_lead": false, "lead_probability": 0.1}'


def test_extract_json_object_handles_nested_braces():
    raw = '{"is_lead": true, "budget": {"mentioned": true, "min": 1}}'
    result = extract_json_object(raw)
    assert result == raw
