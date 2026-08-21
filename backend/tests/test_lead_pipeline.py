"""Stage 7 / Этап 3: LeadPipelineService — RawItem -> Filter -> AI -> Score -> Save Lead,
now scoped per-SearchProfile (own keywords, own AI prompt, own scoring)."""
import datetime as dt
from typing import Any, Optional

import pytest

from app.ai.base import AIProvider
from app.ai.exceptions import AIResponseValidationError
from app.core.config import Settings
from app.models.enums import KeywordCategory, SourceType
from app.models.search_profile import SearchProfile
from app.models.search_profile_keyword import SearchProfileKeyword
from app.models.user import User
from app.repositories.lead_repository import LeadRepository
from app.repositories.raw_item_repository import RawItemRepository
from app.repositories.search_profile_keyword_repository import SearchProfileKeywordRepository
from app.repositories.source_repository import SourceRepository
from app.schemas.ai_analysis import BudgetInfo, LeadAnalysis
from app.services.keyword_filter import KeywordFilter
from app.services.lead_pipeline import LeadPipelineService


async def _make_search_profile(db_session, services: Optional[list[str]] = None) -> SearchProfile:
    user = User(email=f"u{id(db_session)}-{dt.datetime.now().timestamp()}@example.com", password_hash="x")
    db_session.add(user)
    await db_session.flush()
    profile = SearchProfile(
        user_id=user.id, name="Test profile", services=services or ["website_development", "web_design"]
    )
    db_session.add(profile)
    await db_session.flush()
    return profile


class StubAIProvider(AIProvider):
    """Configurable fake — either returns a canned LeadAnalysis or raises."""

    def __init__(self, response: Optional[LeadAnalysis] = None, error: Optional[Exception] = None) -> None:
        self.response = response
        self.error = error
        self.calls: list[str] = []

    async def analyze_lead(
        self, text: str, system_prompt: str, context: Optional[dict[str, Any]] = None
    ) -> LeadAnalysis:
        self.calls.append(text)
        if self.error is not None:
            raise self.error
        assert self.response is not None
        return self.response

    async def generate_profile_draft(self, description: str):  # pragma: no cover - unused here
        raise NotImplementedError


def make_keyword_filter(*keywords: str) -> KeywordFilter:
    entries = [
        SearchProfileKeyword(
            search_profile_id=0, text=kw, category=KeywordCategory.DIRECT_INTENT.value, weight=1.0, enabled=True
        )
        for kw in keywords
    ]
    return KeywordFilter(entries)


@pytest.fixture
def settings() -> Settings:
    return Settings(AI_PROVIDER="mock")


@pytest.mark.asyncio
async def test_item_filtered_out_by_keywords_skips_ai_entirely(db_session, settings):
    source_repo = SourceRepository(db_session)
    raw_repo = RawItemRepository(db_session)
    source = await source_repo.create(name="Chan", type=SourceType.TELEGRAM.value, external_identifier="c")
    raw_item = await raw_repo.create(
        source_id=source.id, external_id="1", text="случайный текст ни о чём", content_hash="h1"
    )

    profile = await _make_search_profile(db_session)
    stub_ai = StubAIProvider(response=LeadAnalysis(is_lead=True, lead_probability=0.9))
    pipeline = LeadPipelineService(db_session, stub_ai, settings)
    kf = make_keyword_filter("нужен сайт")

    result = await pipeline.process_raw_item(raw_item, search_profile=profile, keyword_filter=kf)

    assert result.passed_keyword_filter is False
    assert result.lead is None
    assert stub_ai.calls == []  # AI must never be called


@pytest.mark.asyncio
async def test_matching_item_creates_lead_with_correct_score(db_session, settings):
    source_repo = SourceRepository(db_session)
    raw_repo = RawItemRepository(db_session)
    source = await source_repo.create(name="Chan", type=SourceType.TELEGRAM.value, external_identifier="c2")
    now = dt.datetime.now(dt.timezone.utc)
    raw_item = await raw_repo.create(
        source_id=source.id,
        external_id="2",
        text="Нужен сайт для стоматологии",
        content_hash="h2",
        author_username="ivan_p",
        published_at=now,
    )

    analysis = LeadAnalysis(
        is_lead=True,
        lead_probability=0.9,
        lead_type="website_development",
        services=["website_development", "web_design"],
        project_description="Клиника ищет разработчика лендинга с адаптивным дизайном",
        business_niche="dentistry",
        budget=BudgetInfo(mentioned=True, min=50000, max=100000, currency="RUB"),
        urgency="high",
        project_complexity="medium",
        intent="looking_for_contractor",
        estimated_value="high",
        summary="Клиника ищет подрядчика для лендинга.",
        reasoning_short="Прямой запрос с бюджетом.",
        positive_signals=["direct request", "budget mentioned"],
        negative_signals=[],
        confidence=0.9,
    )
    # services must match the profile's own list — Этап 3's scoring checks
    # analysis.services against search_profile.services, not a hardcoded set.
    profile = await _make_search_profile(db_session, services=["website_development", "web_design"])
    stub_ai = StubAIProvider(response=analysis)
    pipeline = LeadPipelineService(db_session, stub_ai, settings)
    kf = make_keyword_filter("нужен сайт")

    result = await pipeline.process_raw_item(raw_item, search_profile=profile, keyword_filter=kf)
    await db_session.commit()

    assert result.passed_keyword_filter is True
    assert result.lead is not None
    assert stub_ai.calls == ["Нужен сайт для стоматологии"]

    # direct_intent(30) + concrete_description(15) + niche(10) + budget(15)
    # + high_urgency(10) + matches_services(10) + contact(5) + fresh(5) = 100
    assert result.scoring.score == 100
    assert result.lead.lead_score == 100
    assert result.lead.status == "new"
    assert result.lead.business_niche == "dentistry"
    assert result.lead.currency == "RUB"
    assert result.lead.reasoning == "Прямой запрос с бюджетом."

    lead_repo = LeadRepository(db_session)
    persisted = await lead_repo.get_by_raw_item_and_profile(raw_item.id, profile.id)
    assert persisted is not None
    assert persisted.id == result.lead.id


@pytest.mark.asyncio
async def test_ai_validation_error_is_caught_and_no_lead_created(db_session, settings):
    source_repo = SourceRepository(db_session)
    raw_repo = RawItemRepository(db_session)
    source = await source_repo.create(name="Chan", type=SourceType.TELEGRAM.value, external_identifier="c3")
    raw_item = await raw_repo.create(
        source_id=source.id, external_id="3", text="нужен сайт срочно", content_hash="h3"
    )

    profile = await _make_search_profile(db_session)
    stub_ai = StubAIProvider(error=AIResponseValidationError("AI returned garbage"))
    pipeline = LeadPipelineService(db_session, stub_ai, settings)
    kf = make_keyword_filter("нужен сайт")

    result = await pipeline.process_raw_item(raw_item, search_profile=profile, keyword_filter=kf)
    await db_session.commit()

    assert result.lead is None
    assert result.ai_error == "AI returned garbage"

    lead_repo = LeadRepository(db_session)
    assert await lead_repo.get_by_raw_item_and_profile(raw_item.id, profile.id) is None


@pytest.mark.asyncio
async def test_reprocessing_raw_item_with_existing_lead_does_not_call_ai(db_session, settings):
    source_repo = SourceRepository(db_session)
    raw_repo = RawItemRepository(db_session)
    lead_repo = LeadRepository(db_session)
    source = await source_repo.create(name="Chan", type=SourceType.TELEGRAM.value, external_identifier="c4")
    raw_item = await raw_repo.create(
        source_id=source.id, external_id="4", text="нужен сайт", content_hash="h4"
    )
    profile = await _make_search_profile(db_session)
    existing_lead = await lead_repo.create(
        raw_item_id=raw_item.id,
        search_profile_id=profile.id,
        services=[],
        positive_signals=[],
        negative_signals=[],
        lead_score=42,
    )

    stub_ai = StubAIProvider(response=LeadAnalysis(is_lead=True, lead_probability=0.5))
    pipeline = LeadPipelineService(db_session, stub_ai, settings)
    kf = make_keyword_filter("нужен сайт")

    result = await pipeline.process_raw_item(raw_item, search_profile=profile, keyword_filter=kf)

    assert result.lead is not None
    assert result.lead.id == existing_lead.id
    assert stub_ai.calls == []


@pytest.mark.asyncio
async def test_build_keyword_filter_pulls_profiles_own_keywords(db_session, settings):
    profile = await _make_search_profile(db_session)
    spk_repo = SearchProfileKeywordRepository(db_session)
    await spk_repo.create(
        search_profile_id=profile.id,
        text="нужен лендинг",
        category=KeywordCategory.DIRECT_INTENT.value,
        weight=1.0,
        enabled=True,
    )
    # A different profile's keyword must NOT leak into this one's filter.
    other_profile = await _make_search_profile(db_session)
    await spk_repo.create(
        search_profile_id=other_profile.id,
        text="совсем другой текст",
        category=KeywordCategory.DIRECT_INTENT.value,
        weight=1.0,
        enabled=True,
    )

    stub_ai = StubAIProvider(response=LeadAnalysis(is_lead=True, lead_probability=0.5))
    pipeline = LeadPipelineService(db_session, stub_ai, settings)

    kf = await pipeline.build_keyword_filter(profile.id)

    assert kf.should_pass_to_ai("нужен лендинг для магазина") is True
    assert kf.should_pass_to_ai("совсем другой текст") is False
