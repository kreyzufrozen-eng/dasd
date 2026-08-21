"""Этап 3: build_system_prompt — profile-parameterized AI prompt."""
from app.ai.prompts import build_system_prompt
from app.models.search_profile import SearchProfile


def _profile(**overrides) -> SearchProfile:
    defaults = dict(
        user_id=1,
        name="Test",
        profession=None,
        profession_description=None,
        services=[],
        target_clients=None,
        preferred_niches=[],
        excluded_niches=[],
        ai_profile_context=None,
    )
    defaults.update(overrides)
    return SearchProfile(**defaults)


def test_includes_profession_and_services():
    profile = _profile(
        profession="Дизайнер карточек маркетплейсов",
        services=["дизайн карточек", "инфографика"],
    )
    prompt = build_system_prompt(profile)
    assert "Дизайнер карточек маркетплейсов" in prompt
    assert "дизайн карточек" in prompt
    assert "инфографика" in prompt


def test_includes_profession_description_and_ai_context():
    profile = _profile(
        profession="Веб-дизайнер",
        profession_description="Делаю лендинги и корпоративные сайты",
        ai_profile_context="Ищет заказы от 30000 рублей, не интересны мелкие правки",
    )
    prompt = build_system_prompt(profile)
    assert "Делаю лендинги и корпоративные сайты" in prompt
    assert "не интересны мелкие правки" in prompt


def test_includes_excluded_niches_as_additional_exclusion():
    profile = _profile(profession="Разработчик", excluded_niches=["казино", "крипта"])
    prompt = build_system_prompt(profile)
    assert "казино" in prompt
    assert "крипта" in prompt


def test_degrades_gracefully_with_bare_minimum_profile():
    """A profile created via the API without onboarding (only name/
    profession set) must still produce a usable, non-empty prompt."""
    profile = _profile(profession="Таргетолог")
    prompt = build_system_prompt(profile)
    assert "Таргетолог" in prompt
    assert len(prompt) > 200


def test_json_contract_present_and_unchanged_shape():
    profile = _profile(profession="Веб-дизайнер", services=["веб-дизайн"])
    prompt = build_system_prompt(profile)
    assert '"is_lead": true' in prompt
    assert '"intent_score": 0' in prompt
    assert '"is_self_advertising": false' in prompt
