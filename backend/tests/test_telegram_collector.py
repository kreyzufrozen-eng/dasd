"""Stage 6: TelegramCollectorService — collect -> dedup -> persist -> watermark."""
import datetime as dt
from typing import Optional

import pytest

from app.models.enums import SourceType
from app.repositories.raw_item_repository import RawItemRepository
from app.repositories.source_repository import SourceRepository
from app.services.telegram_collector import TelegramCollectorService
from app.sources.base import BaseSourceAdapter, RawItemDTO


class FakeAdapter(BaseSourceAdapter):
    def __init__(self, items: list[RawItemDTO]) -> None:
        self._items = items

    async def fetch_new_items(self) -> list[RawItemDTO]:
        return self._items


@pytest.mark.asyncio
async def test_collect_persists_new_items_and_advances_watermark(db_session):
    source_repo = SourceRepository(db_session)
    source = await source_repo.create(
        name="Chan", type=SourceType.TELEGRAM.value, external_identifier="chan"
    )

    items = [
        RawItemDTO(external_id="10", text="Нужен сайт, бюджет 50к"),
        RawItemDTO(external_id="11", text="Ищу веб дизайнера"),
    ]
    adapter = FakeAdapter(items)
    collector = TelegramCollectorService(db_session)

    count = await collector.collect_from_source(source, adapter)
    await db_session.commit()

    assert count == 2

    raw_repo = RawItemRepository(db_session)
    stored = await raw_repo.get_by_source_and_external_id(source.id, "11")
    assert stored is not None
    assert stored.text == "Ищу веб дизайнера"

    refreshed_source = await source_repo.get(source.id)
    assert refreshed_source.last_external_id == "11"
    assert refreshed_source.last_checked_at is not None


@pytest.mark.asyncio
async def test_collect_skips_duplicates(db_session):
    source_repo = SourceRepository(db_session)
    raw_repo = RawItemRepository(db_session)
    source = await source_repo.create(
        name="Chan", type=SourceType.TELEGRAM.value, external_identifier="chan2"
    )
    # Pre-existing item that the "fetch" will also return (simulating overlap).
    await raw_repo.create(
        source_id=source.id, external_id="1", text="already stored", content_hash="irrelevant"
    )

    items = [
        RawItemDTO(external_id="1", text="already stored"),  # duplicate by source+external_id
        RawItemDTO(external_id="2", text="new item"),
    ]
    collector = TelegramCollectorService(db_session)

    count = await collector.collect_from_source(source, FakeAdapter(items))
    await db_session.commit()

    assert count == 1  # only the genuinely new one


@pytest.mark.asyncio
async def test_collect_with_no_new_items_still_updates_last_checked_at(db_session):
    source_repo = SourceRepository(db_session)
    source = await source_repo.create(
        name="Chan", type=SourceType.TELEGRAM.value, external_identifier="chan3"
    )
    collector = TelegramCollectorService(db_session)

    count = await collector.collect_from_source(source, FakeAdapter([]))
    await db_session.commit()

    assert count == 0
    refreshed = await source_repo.get(source.id)
    assert refreshed.last_checked_at is not None
    assert refreshed.last_external_id is None


@pytest.mark.asyncio
async def test_collect_watermark_tracks_highest_external_id_even_out_of_order(db_session):
    source_repo = SourceRepository(db_session)
    source = await source_repo.create(
        name="Chan", type=SourceType.TELEGRAM.value, external_identifier="chan4"
    )
    items = [
        RawItemDTO(external_id="5", text="a"),
        RawItemDTO(external_id="20", text="b"),
        RawItemDTO(external_id="8", text="c"),
    ]
    collector = TelegramCollectorService(db_session)

    await collector.collect_from_source(source, FakeAdapter(items))
    await db_session.commit()

    refreshed = await source_repo.get(source.id)
    assert refreshed.last_external_id == "20"
