"""Stage 6: DuplicateDetectionService — both required checks."""
import pytest

from app.models.enums import SourceType
from app.repositories.raw_item_repository import RawItemRepository
from app.repositories.source_repository import SourceRepository
from app.services.duplicate_detection import DuplicateDetectionService, compute_content_hash


def test_compute_content_hash_normalizes_whitespace():
    h1 = compute_content_hash("нужен   сайт\nдля бизнеса")
    h2 = compute_content_hash("  нужен сайт для бизнеса  ")
    assert h1 == h2


def test_compute_content_hash_is_case_sensitive():
    h1 = compute_content_hash("Нужен сайт")
    h2 = compute_content_hash("нужен сайт")
    assert h1 != h2


def test_compute_content_hash_differs_for_different_text():
    assert compute_content_hash("нужен сайт") != compute_content_hash("нужен лендинг")


@pytest.mark.asyncio
async def test_is_duplicate_by_source_and_external_id(db_session):
    source_repo = SourceRepository(db_session)
    raw_repo = RawItemRepository(db_session)
    dedup = DuplicateDetectionService(raw_repo)

    source = await source_repo.create(
        name="Chan", type=SourceType.TELEGRAM.value, external_identifier="chan"
    )
    await raw_repo.create(
        source_id=source.id, external_id="msg-1", text="text a", content_hash="hash-a"
    )

    assert await dedup.is_duplicate(source.id, "msg-1", "some-other-hash") is True
    assert await dedup.is_duplicate(source.id, "msg-2", "some-other-hash") is False


@pytest.mark.asyncio
async def test_is_duplicate_by_content_hash_across_sources(db_session):
    source_repo = SourceRepository(db_session)
    raw_repo = RawItemRepository(db_session)
    dedup = DuplicateDetectionService(raw_repo)

    source_a = await source_repo.create(
        name="A", type=SourceType.TELEGRAM.value, external_identifier="a"
    )
    source_b = await source_repo.create(
        name="B", type=SourceType.TELEGRAM.value, external_identifier="b"
    )
    await raw_repo.create(
        source_id=source_a.id, external_id="msg-1", text="forwarded text", content_hash="shared-hash"
    )

    # Same content reposted to a different source/channel is still a duplicate.
    assert await dedup.is_duplicate(source_b.id, "msg-99", "shared-hash") is True


@pytest.mark.asyncio
async def test_not_duplicate_when_neither_check_matches(db_session):
    source_repo = SourceRepository(db_session)
    raw_repo = RawItemRepository(db_session)
    dedup = DuplicateDetectionService(raw_repo)

    source = await source_repo.create(
        name="Chan", type=SourceType.TELEGRAM.value, external_identifier="chan"
    )
    assert await dedup.is_duplicate(source.id, "brand-new", "brand-new-hash") is False
