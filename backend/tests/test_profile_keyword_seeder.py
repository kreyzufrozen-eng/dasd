"""Этап 3: ensure_keywords_seeded — backfills a profile's own keyword
list from the global catalog so profiles that predate SearchProfileKeyword
(or were created without onboarding) still work in the pipeline."""
import pytest

from app.models.enums import KeywordCategory
from app.models.search_profile import SearchProfile
from app.models.user import User
from app.repositories.keyword_repository import KeywordRepository
from app.repositories.search_profile_keyword_repository import SearchProfileKeywordRepository
from app.services.profile_keyword_seeder import ensure_keywords_seeded


async def _make_profile(db_session) -> SearchProfile:
    user = User(email="seed-test@example.com", password_hash="x")
    db_session.add(user)
    await db_session.flush()
    profile = SearchProfile(user_id=user.id, name="Test")
    db_session.add(profile)
    await db_session.flush()
    return profile


@pytest.mark.asyncio
async def test_seeds_from_global_catalog_when_profile_has_none(db_session):
    keyword_repo = KeywordRepository(db_session)
    await keyword_repo.create(
        keyword="нужен сайт", category=KeywordCategory.DIRECT_INTENT.value, weight=2.0
    )
    await keyword_repo.create(
        keyword="лендинг", category=KeywordCategory.PROJECT_TYPE.value, weight=1.5
    )

    profile = await _make_profile(db_session)

    await ensure_keywords_seeded(db_session, profile.id)

    spk_repo = SearchProfileKeywordRepository(db_session)
    seeded = await spk_repo.list_for_profile(profile.id)
    assert {k.text for k in seeded} == {"нужен сайт", "лендинг"}
    assert all(k.keyword_id is not None for k in seeded)


@pytest.mark.asyncio
async def test_does_not_reseed_a_profile_that_already_has_keywords(db_session):
    keyword_repo = KeywordRepository(db_session)
    await keyword_repo.create(
        keyword="нужен сайт", category=KeywordCategory.DIRECT_INTENT.value, weight=2.0
    )
    profile = await _make_profile(db_session)

    spk_repo = SearchProfileKeywordRepository(db_session)
    await spk_repo.create(
        search_profile_id=profile.id,
        text="уникальная фраза только для профиля",
        category=KeywordCategory.DIRECT_INTENT.value,
        weight=1.0,
        enabled=True,
    )

    await ensure_keywords_seeded(db_session, profile.id)

    seeded = await spk_repo.list_for_profile(profile.id)
    assert len(seeded) == 1
    assert seeded[0].text == "уникальная фраза только для профиля"


@pytest.mark.asyncio
async def test_noop_when_global_catalog_is_empty(db_session):
    profile = await _make_profile(db_session)
    await ensure_keywords_seeded(db_session, profile.id)

    spk_repo = SearchProfileKeywordRepository(db_session)
    assert await spk_repo.list_for_profile(profile.id) == []
