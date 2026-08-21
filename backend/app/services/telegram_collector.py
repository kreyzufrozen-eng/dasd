"""TelegramCollectorService: SOURCE -> COLLECT RAW ITEM -> DEDUPLICATION.

Ties a TelegramSourceAdapter to persistence: fetches new messages, drops
duplicates, persists new RawItem rows, and advances the source's
last_external_id watermark. Stops at "RawItem persisted" — keyword
filtering / AI analysis / scoring is Stage 7's job (kept separate so this
stays testable and reusable for any future source type, not just Telegram).
"""
import datetime as dt
from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.source import Source
from app.repositories.raw_item_repository import RawItemRepository
from app.repositories.source_repository import SourceRepository
from app.services.duplicate_detection import DuplicateDetectionService, compute_content_hash
from app.sources.base import BaseSourceAdapter

logger = get_logger(__name__)


class TelegramCollectorService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.source_repo = SourceRepository(session)
        self.raw_item_repo = RawItemRepository(session)
        self.dedup_service = DuplicateDetectionService(self.raw_item_repo)

    async def collect_from_source(self, source: Source, adapter: BaseSourceAdapter) -> int:
        """Fetch, dedup, and persist new items for one source.

        Caller owns the transaction (commit/rollback) — this only flushes,
        so callers can batch multiple sources in one transaction or isolate
        each source per-transaction as they prefer.
        """
        items = await adapter.fetch_new_items()
        persisted = 0
        max_external_id = self._to_int_or_none(source.last_external_id)

        for dto in items:
            content_hash = compute_content_hash(dto.text)

            if await self.dedup_service.is_duplicate(source.id, dto.external_id, content_hash):
                logger.info(
                    "Skipping duplicate raw item: source_id=%s external_id=%s",
                    source.id,
                    dto.external_id,
                )
                continue

            try:
                retention_days = get_settings().RAW_ITEM_RETENTION_DAYS
                await self.raw_item_repo.create(
                    source_id=source.id,
                    external_id=dto.external_id,
                    author_name=dto.author_name,
                    author_username=dto.author_username,
                    text=dto.text,
                    url=dto.url,
                    published_at=dto.published_at,
                    content_hash=content_hash,
                    metadata_=dto.metadata,
                    retention_until=dt.datetime.now(dt.timezone.utc)
                    + dt.timedelta(days=retention_days),
                )
                persisted += 1
            except IntegrityError:
                # Race condition: another worker persisted the same item
                # between our dedup check and this insert. Not a bug — log
                # and move on, never crash the whole collection cycle.
                await self.session.rollback()
                logger.warning(
                    "Race condition on insert (already exists): source_id=%s external_id=%s",
                    source.id,
                    dto.external_id,
                )
                continue

            candidate_id = self._to_int_or_none(dto.external_id)
            if candidate_id is not None and (max_external_id is None or candidate_id > max_external_id):
                max_external_id = candidate_id

        update_kwargs: dict = {"last_checked_at": dt.datetime.now(dt.timezone.utc)}
        if max_external_id is not None and str(max_external_id) != source.last_external_id:
            update_kwargs["last_external_id"] = str(max_external_id)
        await self.source_repo.update(source, **update_kwargs)

        logger.info(
            "Collected %d new raw item(s) from source id=%s (%s)",
            persisted,
            source.id,
            source.external_identifier,
        )
        return persisted

    @staticmethod
    def _to_int_or_none(value) -> Optional[int]:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
