"""Stage 2: CRUD verification for every repository against the real ORM
models (via in-memory SQLite), including relationships and dedup lookups.
"""
import datetime as dt

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.enums import KeywordCategory, LeadFeedbackType, LeadStatus, SourceType
from app.models.search_profile import SearchProfile
from app.models.user import User
from app.repositories.keyword_repository import KeywordRepository
from app.repositories.lead_feedback_repository import LeadFeedbackRepository
from app.repositories.lead_repository import LeadRepository
from app.repositories.raw_item_repository import RawItemRepository
from app.repositories.source_repository import SourceRepository


async def _make_search_profile(db_session) -> int:
    user = User(email=f"u{id(db_session)}-{dt.datetime.now().timestamp()}@example.com", password_hash="x")
    db_session.add(user)
    await db_session.flush()
    profile = SearchProfile(user_id=user.id, name="Test profile")
    db_session.add(profile)
    await db_session.flush()
    return profile.id


@pytest.mark.asyncio
async def test_source_crud(db_session):
    repo = SourceRepository(db_session)

    source = await repo.create(
        name="Test Channel",
        type=SourceType.TELEGRAM.value,
        url="https://t.me/test_channel",
        external_identifier="test_channel",
    )
    assert source.id is not None
    assert source.is_active is True

    fetched = await repo.get(source.id)
    assert fetched is not None
    assert fetched.name == "Test Channel"

    found = await repo.get_by_type_and_identifier(SourceType.TELEGRAM.value, "test_channel")
    assert found is not None
    assert found.id == source.id

    updated = await repo.update(source, is_active=False)
    assert updated.is_active is False

    active = await repo.list_active()
    assert all(s.is_active for s in active)
    assert source.id not in [s.id for s in active]

    await repo.delete(source)
    assert await repo.get(source.id) is None


@pytest.mark.asyncio
async def test_raw_item_dedup_lookups(db_session):
    source_repo = SourceRepository(db_session)
    raw_repo = RawItemRepository(db_session)

    source = await source_repo.create(
        name="Chan", type=SourceType.TELEGRAM.value, external_identifier="chan"
    )

    item = await raw_repo.create(
        source_id=source.id,
        external_id="msg-1",
        text="Нужен сайт для стоматологии",
        content_hash="hash-abc",
    )
    assert item.id is not None

    by_external = await raw_repo.get_by_source_and_external_id(source.id, "msg-1")
    assert by_external is not None
    assert by_external.id == item.id

    by_hash = await raw_repo.get_by_content_hash("hash-abc")
    assert by_hash is not None
    assert by_hash.id == item.id

    assert await raw_repo.get_by_source_and_external_id(source.id, "does-not-exist") is None

    # Dedup constraint: same source_id + external_id must be rejected at the DB level.
    with pytest.raises(IntegrityError):
        await raw_repo.create(
            source_id=source.id,
            external_id="msg-1",
            text="duplicate",
            content_hash="hash-different",
        )
    await db_session.rollback()


@pytest.mark.asyncio
async def test_lead_lifecycle_and_search_filters(db_session):
    source_repo = SourceRepository(db_session)
    raw_repo = RawItemRepository(db_session)
    lead_repo = LeadRepository(db_session)

    source = await source_repo.create(
        name="Chan", type=SourceType.TELEGRAM.value, external_identifier="chan2"
    )
    item = await raw_repo.create(
        source_id=source.id,
        external_id="msg-2",
        text="Ищу разработчика для лендинга, бюджет 100к",
        content_hash="hash-xyz",
    )
    profile_id = await _make_search_profile(db_session)

    lead = await lead_repo.create(
        raw_item_id=item.id,
        search_profile_id=profile_id,
        is_lead=True,
        lead_probability=0.92,
        lead_score=75,
        lead_type="website_development",
        services=["web_design", "website_development"],
        business_niche="beauty",
        positive_signals=["direct request"],
        negative_signals=[],
        status=LeadStatus.NEW.value,
    )
    assert lead.id is not None

    fetched_by_raw = await lead_repo.get_by_raw_item_and_profile(item.id, profile_id)
    assert fetched_by_raw is not None
    assert fetched_by_raw.id == lead.id

    # search: score filter
    results = await lead_repo.search(search_profile_id=profile_id, score_min=60)
    assert any(r.id == lead.id for r in results)

    results = await lead_repo.search(search_profile_id=profile_id, score_min=90)
    assert all(r.id != lead.id for r in results)

    # search: status filter
    results = await lead_repo.search(search_profile_id=profile_id, status=LeadStatus.NEW.value)
    assert any(r.id == lead.id for r in results)

    # search: source_id filter (join through raw_items)
    results = await lead_repo.search(search_profile_id=profile_id, source_id=source.id)
    assert any(r.id == lead.id for r in results)

    # search: date range filter
    now = dt.datetime.now(dt.timezone.utc)
    results = await lead_repo.search(
        search_profile_id=profile_id,
        date_from=now - dt.timedelta(days=1),
        date_to=now + dt.timedelta(days=1),
    )
    assert any(r.id == lead.id for r in results)

    # status update via generic update()
    updated = await lead_repo.update(lead, status=LeadStatus.CONTACTED.value)
    assert updated.status == LeadStatus.CONTACTED.value

    # (raw_item_id, search_profile_id) must be unique — a second Lead for the
    # same RawItem + profile pair is rejected.
    with pytest.raises(IntegrityError):
        await lead_repo.create(
            raw_item_id=item.id,
            search_profile_id=profile_id,
            services=[],
            positive_signals=[],
            negative_signals=[],
        )
    await db_session.rollback()


@pytest.mark.asyncio
async def test_lead_feedback_crud(db_session):
    source_repo = SourceRepository(db_session)
    raw_repo = RawItemRepository(db_session)
    lead_repo = LeadRepository(db_session)
    feedback_repo = LeadFeedbackRepository(db_session)

    source = await source_repo.create(
        name="Chan", type=SourceType.TELEGRAM.value, external_identifier="chan3"
    )
    item = await raw_repo.create(
        source_id=source.id, external_id="msg-3", text="text", content_hash="hash-3"
    )
    profile_id = await _make_search_profile(db_session)
    lead = await lead_repo.create(
        raw_item_id=item.id,
        search_profile_id=profile_id,
        services=[],
        positive_signals=[],
        negative_signals=[],
    )

    feedback = await feedback_repo.create(
        lead_id=lead.id, feedback_type=LeadFeedbackType.GOOD.value
    )
    assert feedback.id is not None

    entries = await feedback_repo.list_for_lead(lead.id)
    assert len(entries) == 1
    assert entries[0].feedback_type == LeadFeedbackType.GOOD.value


@pytest.mark.asyncio
async def test_keyword_crud_and_uniqueness(db_session):
    repo = KeywordRepository(db_session)

    kw = await repo.create(
        keyword="нужен сайт", category=KeywordCategory.DIRECT_INTENT.value, weight=2.0
    )
    assert kw.id is not None
    assert kw.is_active is True

    found = await repo.get_by_keyword_and_category(
        "нужен сайт", KeywordCategory.DIRECT_INTENT.value
    )
    assert found is not None
    assert found.id == kw.id

    active = await repo.list_active(category=KeywordCategory.DIRECT_INTENT.value)
    assert any(k.id == kw.id for k in active)

    updated = await repo.update(kw, is_active=False)
    assert updated.is_active is False

    active_after = await repo.list_active(category=KeywordCategory.DIRECT_INTENT.value)
    assert all(k.id != kw.id for k in active_after)

    # uniqueness on (keyword, category)
    with pytest.raises(IntegrityError):
        await repo.create(
            keyword="нужен сайт", category=KeywordCategory.DIRECT_INTENT.value, weight=1.0
        )
    await db_session.rollback()
