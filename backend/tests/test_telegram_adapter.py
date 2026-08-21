"""Stage 6: TelegramSourceAdapter — fetch/dedup-watermark logic, isolated
from real Telegram via fake TelegramClient/Message stand-ins."""
import datetime as dt
from dataclasses import dataclass, field
from typing import Any, Optional

import pytest
from telethon.errors import FloodWaitError, RPCError

from app.models.enums import SourceType
from app.models.source import Source
from app.sources.telegram_adapter import TelegramSourceAdapter
from app.sources.telegram_client import create_telegram_client, is_source_allowed
from app.core.config import Settings


@dataclass
class FakeSender:
    username: Optional[str] = None
    first_name: str = ""
    last_name: str = ""
    title: Optional[str] = None


@dataclass
class FakeMessage:
    id: int
    message: str
    date: dt.datetime = field(default_factory=lambda: dt.datetime.now(dt.timezone.utc))
    sender: Optional[FakeSender] = None
    sender_error: bool = False

    async def get_sender(self):
        if self.sender_error:
            raise RuntimeError("simulated sender lookup failure")
        return self.sender


class FakeTelegramClient:
    def __init__(self, messages: list[FakeMessage], raise_error: Optional[Exception] = None) -> None:
        self._messages = messages
        self._raise_error = raise_error
        self.last_call_kwargs: dict = {}

    async def iter_messages(self, identifier: str, min_id: int = 0, reverse: bool = True, limit: int = 200):
        self.last_call_kwargs = {"identifier": identifier, "min_id": min_id, "reverse": reverse, "limit": limit}
        if self._raise_error is not None:
            raise self._raise_error
        for m in self._messages:
            if m.id > min_id:
                yield m


def make_source(**overrides) -> Source:
    defaults = dict(
        id=1, name="Chan", type=SourceType.TELEGRAM.value, external_identifier="test_channel",
        is_active=True, last_external_id=None,
    )
    defaults.update(overrides)
    return Source(**defaults)


@pytest.mark.asyncio
async def test_fetch_new_items_returns_dtos_with_sender_info():
    messages = [
        FakeMessage(id=1, message="Нужен сайт", sender=FakeSender(username="ivan", first_name="Ivan", last_name="P")),
    ]
    client = FakeTelegramClient(messages)
    source = make_source()
    adapter = TelegramSourceAdapter(client, source)

    items = await adapter.fetch_new_items()

    assert len(items) == 1
    assert items[0].external_id == "1"
    assert items[0].text == "Нужен сайт"
    assert items[0].author_username == "ivan"
    assert items[0].author_name == "Ivan P"
    assert items[0].url == "https://t.me/test_channel/1"


@pytest.mark.asyncio
async def test_fetch_skips_empty_text_messages():
    messages = [FakeMessage(id=1, message=""), FakeMessage(id=2, message="   "), FakeMessage(id=3, message="реальный текст")]
    client = FakeTelegramClient(messages)
    adapter = TelegramSourceAdapter(client, make_source())

    items = await adapter.fetch_new_items()

    assert len(items) == 1
    assert items[0].external_id == "3"


@pytest.mark.asyncio
async def test_fetch_uses_last_external_id_as_min_id():
    client = FakeTelegramClient([FakeMessage(id=10, message="msg")])
    source = make_source(last_external_id="5")
    adapter = TelegramSourceAdapter(client, source)

    await adapter.fetch_new_items()

    assert client.last_call_kwargs["min_id"] == 5


@pytest.mark.asyncio
async def test_fetch_with_no_external_identifier_returns_empty():
    client = FakeTelegramClient([FakeMessage(id=1, message="msg")])
    source = make_source(external_identifier=None)
    adapter = TelegramSourceAdapter(client, source)

    items = await adapter.fetch_new_items()

    assert items == []


@pytest.mark.asyncio
async def test_sender_resolution_failure_does_not_crash_fetch():
    messages = [FakeMessage(id=1, message="Нужен сайт", sender_error=True)]
    client = FakeTelegramClient(messages)
    adapter = TelegramSourceAdapter(client, make_source())

    items = await adapter.fetch_new_items()

    assert len(items) == 1
    assert items[0].author_name is None
    assert items[0].author_username is None


@pytest.mark.asyncio
async def test_flood_wait_error_is_caught_and_returns_partial_results():
    client = FakeTelegramClient([], raise_error=FloodWaitError(request=None))
    adapter = TelegramSourceAdapter(client, make_source())

    items = await adapter.fetch_new_items()  # must not raise

    assert items == []


@pytest.mark.asyncio
async def test_generic_rpc_error_is_caught_not_raised():
    client = FakeTelegramClient([], raise_error=RPCError(request=None, message="boom", code=400))
    adapter = TelegramSourceAdapter(client, make_source())

    items = await adapter.fetch_new_items()  # must not raise

    assert items == []


# --- telegram_client helpers ---

def test_create_telegram_client_raises_without_credentials():
    settings = Settings(TELEGRAM_API_ID=None, TELEGRAM_API_HASH=None)
    with pytest.raises(ValueError):
        create_telegram_client(settings)


def test_is_source_allowed_matches_allowlist():
    settings = Settings(TELEGRAM_ALLOWED_SOURCES="chan_one, @chan_two")
    assert is_source_allowed("chan_one", settings) is True
    assert is_source_allowed("chan_two", settings) is True  # @ stripped both sides
    assert is_source_allowed("chan_three", settings) is False


def test_is_source_allowed_empty_allowlist_denies_everything():
    settings = Settings(TELEGRAM_ALLOWED_SOURCES="")
    assert is_source_allowed("anything", settings) is False


def test_is_source_allowed_is_case_insensitive():
    # Telegram usernames are case-insensitive (t.me/SomeChan == t.me/somechan),
    # so a DB entry and an .env entry that differ only in case must still match.
    settings = Settings(TELEGRAM_ALLOWED_SOURCES="Well_paid_Job,xCareers")
    assert is_source_allowed("well_paid_job", settings) is True
    assert is_source_allowed("WELL_PAID_JOB", settings) is True
    assert is_source_allowed("xcareers", settings) is True
    assert is_source_allowed("XCareers", settings) is True
