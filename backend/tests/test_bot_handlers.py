"""Stage 8: bot command + callback handlers, against a shared in-memory
SQLite DB (StaticPool so every session opened by the handler — they each
open their own, matching production behavior — sees the same data)."""
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.bot import handlers as handlers_module
from app.bot.keyboards import LeadAction
from app.db.base import Base
from app.models.enums import LeadStatus, SourceType
from app.models.search_profile import SearchProfile
from app.models.user import User
from app.repositories.lead_repository import LeadRepository
from app.repositories.source_repository import SourceRepository


@pytest_asyncio.fixture
async def patched_sessionmaker(monkeypatch):
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        future=True,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    sessionmaker = async_sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(handlers_module, "AsyncSessionLocal", sessionmaker)

    yield sessionmaker

    await engine.dispose()


@pytest_asyncio.fixture
async def search_profile_id(patched_sessionmaker) -> int:
    """cmd_leads/cmd_hot resolve SearchProfileRepository.get_primary() —
    seed the profile they'll find, same as pipeline_worker.py does in
    production (see PROJECT_AUDIT.md Stage 1 notes)."""
    async with patched_sessionmaker() as session:
        user = User(email="bot-owner@example.com", password_hash="x", is_admin=True)
        session.add(user)
        await session.flush()
        profile = SearchProfile(user_id=user.id, name="Test profile")
        session.add(profile)
        await session.commit()
        return profile.id


class FakeMessage:
    def __init__(self) -> None:
        self.answer = AsyncMock()


class FakeCallbackMessage:
    def __init__(self) -> None:
        self.edit_reply_markup = AsyncMock()


class FakeCallbackQuery:
    def __init__(self) -> None:
        self.message = FakeCallbackMessage()
        self.answer = AsyncMock()


async def _seed_lead(sessionmaker, search_profile_id: int, score: int = 75) -> int:
    async with sessionmaker() as session:
        source_repo = SourceRepository(session)
        lead_repo = LeadRepository(session)
        source = await source_repo.create(
            name="Chan", type=SourceType.TELEGRAM.value, external_identifier="c"
        )
        from app.repositories.raw_item_repository import RawItemRepository

        raw_repo = RawItemRepository(session)
        raw_item = await raw_repo.create(
            source_id=source.id, external_id="1", text="нужен сайт", content_hash="h"
        )
        lead = await lead_repo.create(
            raw_item_id=raw_item.id,
            search_profile_id=search_profile_id,
            lead_score=score,
            services=[],
            positive_signals=[],
            negative_signals=[],
        )
        await session.commit()
        return lead.id


@pytest.mark.asyncio
async def test_cmd_leads_with_no_leads(patched_sessionmaker, search_profile_id):
    message = FakeMessage()
    await handlers_module.cmd_leads(message)
    assert "пока нет" in message.answer.await_args.args[0]


@pytest.mark.asyncio
async def test_cmd_leads_lists_seeded_lead(patched_sessionmaker, search_profile_id):
    lead_id = await _seed_lead(patched_sessionmaker, search_profile_id, score=75)
    message = FakeMessage()
    await handlers_module.cmd_leads(message)
    text = message.answer.await_args.args[0]
    assert f"#{lead_id}" in text
    assert "75/100" in text


@pytest.mark.asyncio
async def test_cmd_hot_filters_by_threshold(patched_sessionmaker, search_profile_id):
    await _seed_lead(patched_sessionmaker, search_profile_id, score=30)  # below default threshold
    hot_id = await _seed_lead(patched_sessionmaker, search_profile_id, score=80)
    message = FakeMessage()
    await handlers_module.cmd_hot(message)
    text = message.answer.await_args.args[0]
    assert f"#{hot_id}" in text
    assert "80/100" in text
    assert "30/100" not in text


@pytest.mark.asyncio
async def test_cmd_stats_reports_counts(patched_sessionmaker, search_profile_id):
    await _seed_lead(patched_sessionmaker, search_profile_id, score=75)
    message = FakeMessage()
    await handlers_module.cmd_stats(message)
    text = message.answer.await_args.args[0]
    assert "Всего лидов: 1" in text


@pytest.mark.asyncio
async def test_callback_good_creates_feedback_and_updates_status(patched_sessionmaker, search_profile_id):
    lead_id = await _seed_lead(patched_sessionmaker, search_profile_id, score=75)
    callback = FakeCallbackQuery()
    callback_data = LeadAction(action="good", lead_id=lead_id)

    await handlers_module.handle_lead_action(callback, callback_data)

    callback.answer.assert_awaited_once()
    async with patched_sessionmaker() as session:
        lead_repo = LeadRepository(session)
        lead = await lead_repo.get(lead_id)
        assert lead.status == LeadStatus.INTERESTED.value

        from app.repositories.lead_feedback_repository import LeadFeedbackRepository

        feedback_repo = LeadFeedbackRepository(session)
        entries = await feedback_repo.list_for_lead(lead_id)
        assert len(entries) == 1
        assert entries[0].feedback_type == "good"


@pytest.mark.asyncio
async def test_callback_client_marks_converted(patched_sessionmaker, search_profile_id):
    lead_id = await _seed_lead(patched_sessionmaker, search_profile_id, score=75)
    callback = FakeCallbackQuery()
    callback_data = LeadAction(action="client", lead_id=lead_id)

    await handlers_module.handle_lead_action(callback, callback_data)

    async with patched_sessionmaker() as session:
        lead_repo = LeadRepository(session)
        lead = await lead_repo.get(lead_id)
        assert lead.status == LeadStatus.CONVERTED.value


@pytest.mark.asyncio
async def test_callback_for_missing_lead_shows_alert(patched_sessionmaker):
    callback = FakeCallbackQuery()
    callback_data = LeadAction(action="good", lead_id=9999)

    await handlers_module.handle_lead_action(callback, callback_data)

    callback.answer.assert_awaited_once_with("Лид не найден", show_alert=True)
